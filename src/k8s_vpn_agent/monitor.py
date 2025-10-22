#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K8s VPN Agent - 헬스체크 및 모니터링 모듈

이 모듈은 다음 기능을 제공합니다:
- 노드 상태 지속 모니터링
- VPN 연결 상태 체크
- Kubelet 상태 확인
- 컨테이너 런타임 상태 확인
- 네트워크 연결성 모니터링
- 메트릭 수집 및 리포트 생성
"""

import time
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

from .logger import get_logger
from .network import NetworkChecker


class HealthChecker:
    """시스템 헬스체크를 수행하는 클래스"""
    
    def __init__(self, config: Dict, log_dir: str = "/var/log/k8s-vpn-agent"):
        """
        Args:
            config: 설정 딕셔너리
            log_dir: 로그 디렉토리 경로
        """
        self.config = config
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)
        self.network_mgr = NetworkChecker()
        
    def check_all(self) -> Dict:
        """모든 헬스체크 수행
        
        Returns:
            Dict: 헬스체크 결과
        """
        self.logger.info("전체 헬스체크 시작")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {
                "vpn": self.check_vpn_connection(),
                "network": self.check_network_connectivity(),
                "kubelet": self.check_kubelet_status(),
                "containerd": self.check_containerd_status(),
                "node_ready": self.check_node_ready_status(),
            },
            "overall_status": "healthy"
        }
        
        # 전체 상태 판단
        failed_checks = [k for k, v in results["checks"].items() if not v.get("healthy", False)]
        if failed_checks:
            results["overall_status"] = "unhealthy"
            results["failed_checks"] = failed_checks
            
        self.logger.info(f"헬스체크 완료: {results['overall_status']}")
        return results
    
    def check_vpn_connection(self) -> Dict:
        """VPN 연결 상태 확인
        
        Returns:
            Dict: VPN 상태 정보
        """
        if not self.config.get("vpn", {}).get("enabled", False):
            return {
                "healthy": True,
                "status": "not_configured",
                "message": "VPN이 설정되지 않음"
            }
        
        try:
            # Tailscale 상태 확인
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                status_data = json.loads(result.stdout)
                backend_state = status_data.get("BackendState", "")
                
                is_healthy = backend_state == "Running"
                
                return {
                    "healthy": is_healthy,
                    "status": backend_state,
                    "peers": len(status_data.get("Peer", {})),
                    "message": "VPN 연결 정상" if is_healthy else f"VPN 상태: {backend_state}"
                }
            else:
                return {
                    "healthy": False,
                    "status": "error",
                    "message": f"VPN 상태 확인 실패: {result.stderr}"
                }
                
        except FileNotFoundError:
            return {
                "healthy": False,
                "status": "not_installed",
                "message": "Tailscale이 설치되지 않음"
            }
        except subprocess.TimeoutExpired:
            return {
                "healthy": False,
                "status": "timeout",
                "message": "VPN 상태 확인 시간 초과"
            }
        except Exception as e:
            self.logger.error(f"VPN 상태 확인 중 오류: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e)
            }
    
    def check_network_connectivity(self) -> Dict:
        """네트워크 연결성 확인
        
        Returns:
            Dict: 네트워크 상태 정보
        """
        master_ip = self.config.get("master", {}).get("ip")
        if not master_ip:
            return {
                "healthy": False,
                "status": "no_config",
                "message": "마스터 IP가 설정되지 않음"
            }
        
        # Ping 테스트
        ping_result = self.network_mgr.ping(master_ip, count=3)
        
        # API 서버 포트 체크
        api_port = 6443
        port_result = self.network_mgr.port_check(master_ip, api_port, timeout=5)
        
        is_healthy = ping_result and port_result
        
        return {
            "healthy": is_healthy,
            "master_ip": master_ip,
            "ping": "success" if ping_result else "failed",
            "api_server": "accessible" if port_result else "not_accessible",
            "message": "네트워크 연결 정상" if is_healthy else "마스터 노드와 통신 불가"
        }
    
    def check_kubelet_status(self) -> Dict:
        """Kubelet 서비스 상태 확인
        
        Returns:
            Dict: Kubelet 상태 정보
        """
        try:
            # systemctl status kubelet
            result = subprocess.run(
                ["systemctl", "is-active", "kubelet"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            is_active = result.returncode == 0 and result.stdout.strip() == "active"
            
            # 추가 정보 수집
            if is_active:
                # Kubelet 버전
                version_result = subprocess.run(
                    ["kubelet", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version = version_result.stdout.strip() if version_result.returncode == 0 else "unknown"
            else:
                version = "unknown"
            
            return {
                "healthy": is_active,
                "status": "active" if is_active else "inactive",
                "version": version,
                "message": "Kubelet 정상 작동" if is_active else "Kubelet이 실행되지 않음"
            }
            
        except Exception as e:
            self.logger.error(f"Kubelet 상태 확인 중 오류: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e)
            }
    
    def check_crio_status(self) -> Dict:
        """CRI-O 서비스 상태 확인
        
        Returns:
            Dict: CRI-O 상태 정보
        """
        try:
            # systemctl status crio
            result = subprocess.run(
                ["systemctl", "is-active", "crio"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            is_active = result.returncode == 0 and result.stdout.strip() == "active"
            
            # 추가 정보: crio 버전
            if is_active:
                version_result = subprocess.run(
                    ["crio", "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                version = version_result.stdout.strip().split('\n')[0] if version_result.returncode == 0 else "unknown"
            else:
                version = "unknown"
            
            return {
                "healthy": is_active,
                "status": "active" if is_active else "inactive",
                "version": version,
                "message": "CRI-O 정상 작동" if is_active else "CRI-O가 실행되지 않음"
            }
            
        except Exception as e:
            self.logger.error(f"CRI-O 상태 확인 중 오류: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e)
            }
    
    def check_containerd_status(self) -> Dict:
        """하위 호환성을 위한 래퍼 - CRI-O 상태 확인"""
        return self.check_crio_status()
    
    def check_node_ready_status(self) -> Dict:
        """Kubernetes 노드 Ready 상태 확인
        
        Returns:
            Dict: 노드 상태 정보
        """
        try:
            # kubectl get nodes 명령 실행
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=15
            )
            
            if result.returncode != 0:
                return {
                    "healthy": False,
                    "status": "kubectl_error",
                    "message": f"kubectl 실행 실패: {result.stderr}"
                }
            
            nodes_data = json.loads(result.stdout)
            
            # 현재 노드 찾기
            import socket
            hostname = socket.gethostname()
            
            current_node = None
            for node in nodes_data.get("items", []):
                if node["metadata"]["name"] == hostname:
                    current_node = node
                    break
            
            if not current_node:
                return {
                    "healthy": False,
                    "status": "not_found",
                    "message": f"노드를 찾을 수 없음: {hostname}"
                }
            
            # Ready 상태 확인
            conditions = current_node.get("status", {}).get("conditions", [])
            ready_condition = next((c for c in conditions if c["type"] == "Ready"), None)
            
            is_ready = ready_condition and ready_condition.get("status") == "True"
            
            return {
                "healthy": is_ready,
                "status": "Ready" if is_ready else "NotReady",
                "hostname": hostname,
                "node_info": current_node.get("status", {}).get("nodeInfo", {}),
                "message": "노드가 Ready 상태" if is_ready else "노드가 Ready 상태가 아님"
            }
            
        except FileNotFoundError:
            return {
                "healthy": False,
                "status": "kubectl_not_found",
                "message": "kubectl이 설치되지 않음"
            }
        except json.JSONDecodeError as e:
            return {
                "healthy": False,
                "status": "json_error",
                "message": f"JSON 파싱 오류: {e}"
            }
        except Exception as e:
            self.logger.error(f"노드 상태 확인 중 오류: {e}")
            return {
                "healthy": False,
                "status": "error",
                "message": str(e)
            }
    
    def save_health_report(self, results: Dict) -> Path:
        """헬스체크 결과를 파일로 저장
        
        Args:
            results: 헬스체크 결과
            
        Returns:
            Path: 저장된 파일 경로
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.log_dir / f"health_report_{timestamp}.json"
        
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"헬스 리포트 저장: {report_file}")
        return report_file


class NodeMonitor:
    """노드를 지속적으로 모니터링하는 클래스"""
    
    def __init__(self, config: Dict, interval: int = 60):
        """
        Args:
            config: 설정 딕셔너리
            interval: 모니터링 간격 (초)
        """
        self.config = config
        self.interval = interval
        self.health_checker = HealthChecker(config)
        self.logger = get_logger(__name__)
        self.running = False
        
    def start_monitoring(self, duration: Optional[int] = None):
        """모니터링 시작
        
        Args:
            duration: 모니터링 지속 시간 (초). None이면 무한 실행
        """
        self.logger.info(f"모니터링 시작 (간격: {self.interval}초)")
        self.running = True
        
        start_time = time.time()
        check_count = 0
        
        try:
            while self.running:
                check_count += 1
                self.logger.info(f"헬스체크 #{check_count}")
                
                # 헬스체크 수행
                results = self.health_checker.check_all()
                
                # 결과 저장
                self.health_checker.save_health_report(results)
                
                # 경고 로그 (unhealthy인 경우)
                if results["overall_status"] == "unhealthy":
                    self.logger.warning(
                        f"시스템이 비정상 상태입니다. 실패한 체크: {results.get('failed_checks', [])}"
                    )
                
                # 지속 시간 체크
                if duration and (time.time() - start_time) >= duration:
                    self.logger.info(f"모니터링 종료 (총 {check_count}회 체크)")
                    break
                
                # 다음 체크까지 대기
                time.sleep(self.interval)
                
        except KeyboardInterrupt:
            self.logger.info("사용자에 의해 모니터링 중단")
        finally:
            self.running = False
    
    def stop_monitoring(self):
        """모니터링 중지"""
        self.logger.info("모니터링 중지 요청")
        self.running = False


def generate_health_summary(log_dir: str = "/var/log/k8s-vpn-agent") -> Dict:
    """최근 헬스 리포트들의 요약 생성
    
    Args:
        log_dir: 로그 디렉토리 경로
        
    Returns:
        Dict: 요약 정보
    """
    log_path = Path(log_dir)
    report_files = sorted(log_path.glob("health_report_*.json"), reverse=True)
    
    if not report_files:
        return {
            "status": "no_reports",
            "message": "헬스 리포트가 없습니다."
        }
    
    # 최근 10개 리포트 분석
    recent_reports = []
    for report_file in report_files[:10]:
        try:
            with open(report_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                recent_reports.append(data)
        except Exception as e:
            print(f"리포트 읽기 오류: {report_file} - {e}")
            continue
    
    if not recent_reports:
        return {
            "status": "error",
            "message": "유효한 헬스 리포트가 없습니다."
        }
    
    # 통계 계산
    total_checks = len(recent_reports)
    healthy_checks = sum(1 for r in recent_reports if r.get("overall_status") == "healthy")
    unhealthy_checks = total_checks - healthy_checks
    
    # 최근 상태
    latest = recent_reports[0]
    
    summary = {
        "latest_check": latest["timestamp"],
        "latest_status": latest["overall_status"],
        "total_checks": total_checks,
        "healthy_checks": healthy_checks,
        "unhealthy_checks": unhealthy_checks,
        "health_rate": round(healthy_checks / total_checks * 100, 2),
        "latest_details": latest["checks"],
    }
    
    if unhealthy_checks > 0:
        summary["warning"] = f"최근 {total_checks}번의 체크 중 {unhealthy_checks}번 비정상 감지"
    
    return summary

