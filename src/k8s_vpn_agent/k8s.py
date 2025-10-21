"""
Kubernetes 워커노드 조인 모듈
idempotent 및 롤백 지원
"""

import subprocess
import time
import os
import socket
from typing import Tuple, Optional, Dict
from rich.console import Console
from .logger import get_logger

console = Console()


class K8sManager:
    """Kubernetes 클러스터 관리 클래스"""
    
    def __init__(self, config: Dict, debug: bool = False):
        self.config = config
        self.debug = debug
        self.logger = get_logger()
        self.master_ip = config.get("master", {}).get("ip")
        self.api_endpoint = config.get("master", {}).get("api_endpoint")
        self.token = config.get("master", {}).get("token")
        self.ca_cert_hash = config.get("master", {}).get("ca_cert_hash")
        self.worker_hostname = config.get("worker", {}).get("hostname", "")
        self.node_labels = config.get("worker", {}).get("labels", [])
        self.node_taints = config.get("worker", {}).get("taints", [])
        self.idempotent = config.get("agent", {}).get("idempotent", True)
        self.original_state = None
    
    def save_state(self):
        """현재 상태 저장 (롤백용)"""
        try:
            self.original_state = {
                "is_joined": self.check_existing_membership(),
                "hostname": socket.gethostname()
            }
            self.logger.debug(f"Saved K8s state: {self.original_state}")
        except Exception as e:
            self.logger.error(f"Failed to save K8s state: {e}")
    
    def rollback(self) -> bool:
        """이전 상태로 롤백"""
        try:
            self.logger.info("Rolling back K8s configuration...")
            console.print("\n[yellow]K8s 설정 롤백 중...[/yellow]")
            
            if not self.original_state:
                self.logger.warning("No saved state to rollback")
                return True
            
            # 원래 조인되어 있지 않았다면 노드 리셋
            if not self.original_state.get("is_joined", False):
                success, msg = self.reset_node()
                if not success:
                    self.logger.error(f"Failed to reset node: {msg}")
                    return False
            
            # 호스트명 복원
            original_hostname = self.original_state.get("hostname")
            if original_hostname:
                try:
                    subprocess.run(
                        ["hostnamectl", "set-hostname", original_hostname],
                        check=True
                    )
                    self.logger.info(f"Hostname restored to {original_hostname}")
                except Exception as e:
                    self.logger.warning(f"Failed to restore hostname: {e}")
            
            self.logger.info("K8s rollback completed")
            console.print("[green]✓ K8s 롤백 완료[/green]")
            return True
        
        except Exception as e:
            self.logger.error(f"K8s rollback failed: {e}")
            console.print(f"[red]✗ K8s 롤백 실패: {e}[/red]")
            return False
    
    def check_dependencies(self) -> Tuple[bool, list]:
        """필수 구성요소 확인"""
        console.print("\n[cyan]Kubernetes 구성요소 확인 중...[/cyan]\n")
        self.logger.info("Checking K8s dependencies...")
        
        dependencies = ["kubeadm", "kubelet", "kubectl", "containerd"]
        missing = []
        
        for dep in dependencies:
            result = subprocess.run(
                ["which", dep],
                capture_output=True
            )
            
            if result.returncode == 0:
                try:
                    version_result = subprocess.run(
                        [dep, "--version"] if dep != "containerd" else ["containerd", "--version"],
                        capture_output=True,
                        text=True
                    )
                    version = version_result.stdout.strip().split('\n')[0]
                    console.print(f"  [green]✓[/green] {dep}: {version}")
                    self.logger.debug(f"{dep}: {version}")
                except:
                    console.print(f"  [green]✓[/green] {dep}: 설치됨")
                    self.logger.debug(f"{dep}: installed")
            else:
                console.print(f"  [red]✗[/red] {dep}: 설치되지 않음")
                self.logger.warning(f"{dep}: not installed")
                missing.append(dep)
        
        if missing:
            console.print(f"\n[red]다음 구성요소가 설치되지 않았습니다: {', '.join(missing)}[/red]")
            console.print("[yellow]install-dependencies.sh 스크립트를 먼저 실행하세요.[/yellow]")
            self.logger.error(f"Missing dependencies: {', '.join(missing)}")
            return False, missing
        
        console.print("\n[green]✓ 모든 필수 구성요소가 설치되어 있습니다.[/green]")
        self.logger.info("All dependencies are installed")
        return True, []
    
    def check_existing_membership(self) -> bool:
        """기존 클러스터 멤버십 확인"""
        is_member = os.path.exists("/etc/kubernetes/kubelet.conf")
        self.logger.debug(f"Node is cluster member: {is_member}")
        return is_member
    
    def reset_node(self) -> Tuple[bool, str]:
        """노드 초기화 (기존 클러스터에서 제거)"""
        console.print("\n[yellow]기존 클러스터 설정을 제거합니다...[/yellow]")
        self.logger.info("Resetting node...")
        
        try:
            # kubeadm reset
            result = subprocess.run(
                ["kubeadm", "reset", "-f"],
                capture_output=True,
                text=True
            )
            
            # CNI 설정 제거
            subprocess.run(["rm", "-rf", "/etc/cni/net.d"], check=False)
            
            # kubeconfig 제거
            subprocess.run(["rm", "-rf", "/root/.kube/config"], check=False)
            
            # iptables 규칙 정리
            subprocess.run(["iptables", "-F"], check=False)
            subprocess.run(["iptables", "-t", "nat", "-F"], check=False)
            
            console.print("[green]✓ 노드 초기화 완료[/green]")
            self.logger.info("Node reset completed")
            return True, "초기화 완료"
        
        except Exception as e:
            error_msg = f"초기화 실패: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def setup_hostname(self) -> Tuple[bool, str]:
        """호스트명 설정"""
        if not self.worker_hostname:
            current = socket.gethostname()
            self.worker_hostname = f"k8s-worker-{current}"
        
        try:
            current_hostname = subprocess.run(
                ["hostname"],
                capture_output=True,
                text=True
            ).stdout.strip()
            
            if current_hostname != self.worker_hostname:
                console.print(f"[cyan]호스트명을 {self.worker_hostname}로 변경합니다...[/cyan]")
                self.logger.info(f"Setting hostname to {self.worker_hostname}")
                
                subprocess.run(
                    ["hostnamectl", "set-hostname", self.worker_hostname],
                    check=True
                )
                
                # /etc/hosts 업데이트
                with open("/etc/hosts", "r") as f:
                    hosts = f.read()
                
                lines = hosts.split('\n')
                updated = False
                for i, line in enumerate(lines):
                    if line.startswith("127.0.1.1"):
                        lines[i] = f"127.0.1.1 {self.worker_hostname}"
                        updated = True
                        break
                
                if not updated:
                    lines.append(f"127.0.1.1 {self.worker_hostname}")
                
                with open("/etc/hosts", "w") as f:
                    f.write('\n'.join(lines))
                
                console.print(f"[green]✓ 호스트명 설정 완료: {self.worker_hostname}[/green]")
                self.logger.info(f"Hostname set to {self.worker_hostname}")
            
            return True, self.worker_hostname
        
        except Exception as e:
            error_msg = f"호스트명 설정 실패: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def configure_kubelet(self, node_ip: Optional[str] = None):
        """Kubelet 설정"""
        console.print("[cyan]Kubelet 설정 중...[/cyan]")
        self.logger.info("Configuring kubelet...")
        
        try:
            os.makedirs("/etc/default", exist_ok=True)
            
            kubelet_args = ""
            if node_ip:
                kubelet_args = f'KUBELET_EXTRA_ARGS="--node-ip={node_ip}"'
            
            with open("/etc/default/kubelet", "w") as f:
                f.write(kubelet_args + "\n")
            
            console.print("[green]✓ Kubelet 설정 완료[/green]")
            self.logger.info("Kubelet configured")
            return True, "설정 완료"
        
        except Exception as e:
            error_msg = f"Kubelet 설정 실패: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def join_cluster(self) -> Tuple[bool, str]:
        """클러스터에 조인 (idempotent)"""
        console.print("\n[bold cyan]클러스터 조인 시작...[/bold cyan]\n")
        self.logger.info("Starting cluster join...")
        
        # 상태 저장
        self.save_state()
        
        # 이미 조인되어 있는지 확인 (idempotent)
        if self.idempotent and self.check_existing_membership():
            console.print("[green]✓ 이미 클러스터에 조인되어 있습니다.[/green]")
            self.logger.info("Node already joined (idempotent)")
            return True, "이미 조인됨"
        
        # 조인 명령어 구성
        if not self.api_endpoint or not self.token or not self.ca_cert_hash:
            error_msg = "마스터 노드 정보가 불완전합니다 (api_endpoint, token, ca_cert_hash 필요)"
            self.logger.error(error_msg)
            return False, error_msg
        
        api_host = self.api_endpoint.replace("https://", "").replace("http://", "")
        
        join_cmd = [
            "kubeadm", "join", api_host,
            "--token", self.token,
            "--discovery-token-ca-cert-hash", self.ca_cert_hash
        ]
        
        # 노드 레이블 추가
        if self.node_labels:
            for label in self.node_labels:
                join_cmd.extend(["--node-labels", label])
        
        # 노드 테인트 추가
        if self.node_taints:
            taints_str = ",".join(self.node_taints)
            join_cmd.extend(["--register-with-taints", taints_str])
        
        console.print(f"[cyan]Join 명령어 실행 중...[/cyan]")
        self.logger.info(f"Executing join command: {' '.join(join_cmd)}")
        
        try:
            result = subprocess.run(
                join_cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                console.print("[bold green]✓ 클러스터 조인 성공![/bold green]\n")
                console.print(result.stdout)
                self.logger.info("Cluster join successful")
                
                # Kubelet 시작 대기
                console.print("\n[cyan]Kubelet 시작 대기 중...[/cyan]")
                time.sleep(5)
                
                # Kubelet 상태 확인
                kubelet_status = subprocess.run(
                    ["systemctl", "is-active", "kubelet"],
                    capture_output=True,
                    text=True
                )
                
                if kubelet_status.stdout.strip() == "active":
                    console.print("[green]✓ Kubelet 정상 실행 중[/green]")
                    self.logger.info("Kubelet is active")
                else:
                    console.print("[yellow]⚠ Kubelet 상태 확인 필요[/yellow]")
                    self.logger.warning("Kubelet status check needed")
                
                return True, "조인 완료"
            else:
                console.print("[bold red]✗ 클러스터 조인 실패[/bold red]\n")
                console.print(result.stderr)
                self.logger.error(f"Cluster join failed: {result.stderr}")
                
                # 일반적인 오류 원인 안내
                console.print("\n[yellow]다음 사항을 확인하세요:[/yellow]")
                console.print("  1. 토큰이 유효한지 확인 (마스터에서 'kubeadm token list')")
                console.print("  2. CA 인증서 해시가 올바른지 확인")
                console.print("  3. 마스터 노드 API 서버에 접근 가능한지 확인")
                console.print("  4. 방화벽 설정 확인 (6443, 10250 포트)")
                
                return False, result.stderr
        
        except subprocess.TimeoutExpired:
            error_msg = "조인 타임아웃 (120초)"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"조인 오류: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def verify_node_status(self) -> Dict:
        """노드 상태 확인"""
        console.print("\n[cyan]노드 상태 확인 중...[/cyan]\n")
        self.logger.info("Verifying node status...")
        
        results = {
            "kubelet": False,
            "kubelet_conf": False,
            "cni": False,
        }
        
        # Kubelet 실행 확인
        result = subprocess.run(
            ["systemctl", "is-active", "kubelet"],
            capture_output=True,
            text=True
        )
        results["kubelet"] = (result.stdout.strip() == "active")
        console.print(f"  {'✓' if results['kubelet'] else '✗'} Kubelet: {'실행 중' if results['kubelet'] else '중지됨'}")
        
        # Kubelet 설정 파일 확인
        results["kubelet_conf"] = os.path.exists("/etc/kubernetes/kubelet.conf")
        console.print(f"  {'✓' if results['kubelet_conf'] else '✗'} Kubelet 설정: {'존재함' if results['kubelet_conf'] else '없음'}")
        
        # CNI 설정 확인
        cni_exists = (
            os.path.exists("/etc/cni/net.d") and 
            len(os.listdir("/etc/cni/net.d")) > 0
        )
        results["cni"] = cni_exists
        console.print(f"  {'✓' if results['cni'] else '⚠'} CNI 설정: {'존재함' if results['cni'] else '대기 중 (마스터에서 CNI 플러그인 확인 필요)'}")
        
        console.print("\n[yellow]마스터 노드에서 다음 명령어로 노드 상태를 확인하세요:[/yellow]")
        console.print("[cyan]  kubectl get nodes[/cyan]")
        console.print("[cyan]  kubectl get nodes -o wide[/cyan]")
        
        self.logger.info(f"Node status: {results}")
        
        return results

