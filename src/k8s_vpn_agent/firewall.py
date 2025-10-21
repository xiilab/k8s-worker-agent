"""
방화벽 자동 설정 모듈
UFW, firewalld, iptables 지원
"""

import subprocess
from typing import Tuple, List, Dict
from rich.console import Console
from .logger import get_logger

console = Console()


class FirewallManager:
    """방화벽 관리 클래스"""
    
    def __init__(self, config: Dict, debug: bool = False):
        self.config = config
        self.debug = debug
        self.logger = get_logger()
        self.enabled = config.get("enabled", True)
        self.vpn_port = config.get("vpn_port", 41641)
        self.k8s_api_port = config.get("k8s_api_port", 6443)
        self.kubelet_port = config.get("kubelet_port", 10250)
        self.nodeport_range = config.get("nodeport_range", "30000-32767")
        self.additional_ports = config.get("additional_ports", [])
        self.firewall_type = None
        self.original_rules = []
    
    def detect_firewall(self) -> str:
        """시스템의 방화벽 타입 감지"""
        if subprocess.run(["which", "ufw"], capture_output=True).returncode == 0:
            return "ufw"
        elif subprocess.run(["which", "firewall-cmd"], capture_output=True).returncode == 0:
            return "firewalld"
        elif subprocess.run(["which", "iptables"], capture_output=True).returncode == 0:
            return "iptables"
        else:
            return "none"
    
    def save_state(self):
        """현재 방화벽 규칙 저장 (롤백용)"""
        try:
            self.firewall_type = self.detect_firewall()
            self.logger.debug(f"Detected firewall: {self.firewall_type}")
            
            if self.firewall_type == "iptables":
                result = subprocess.run(
                    ["iptables-save"],
                    capture_output=True,
                    text=True
                )
                self.original_rules = result.stdout
                self.logger.debug("Saved iptables rules")
        except Exception as e:
            self.logger.error(f"Failed to save firewall state: {e}")
    
    def rollback(self) -> bool:
        """이전 방화벽 규칙으로 롤백"""
        try:
            self.logger.info("Rolling back firewall configuration...")
            console.print("\n[yellow]방화벽 설정 롤백 중...[/yellow]")
            
            if self.firewall_type == "iptables" and self.original_rules:
                # iptables 규칙 복원
                process = subprocess.Popen(
                    ["iptables-restore"],
                    stdin=subprocess.PIPE,
                    text=True
                )
                process.communicate(input=self.original_rules)
                self.logger.info("Firewall rules restored")
            
            console.print("[green]✓ 방화벽 롤백 완료[/green]")
            return True
        
        except Exception as e:
            self.logger.error(f"Firewall rollback failed: {e}")
            console.print(f"[red]✗ 방화벽 롤백 실패: {e}[/red]")
            return False
    
    def configure(self) -> Tuple[bool, str]:
        """방화벽 자동 설정"""
        if not self.enabled:
            console.print("[cyan]방화벽 설정을 건너뜁니다.[/cyan]")
            self.logger.info("Firewall configuration skipped")
            return True, "건너뜀"
        
        console.print("\n[bold cyan]방화벽 설정 중...[/bold cyan]\n")
        self.logger.info("Configuring firewall...")
        
        # 상태 저장
        self.save_state()
        
        # 방화벽 타입 감지
        self.firewall_type = self.detect_firewall()
        console.print(f"[cyan]감지된 방화벽: {self.firewall_type}[/cyan]")
        self.logger.info(f"Detected firewall: {self.firewall_type}")
        
        if self.firewall_type == "none":
            console.print("[yellow]⚠ 방화벽 관리 도구를 찾을 수 없습니다.[/yellow]")
            self.logger.warning("No firewall management tool found")
            return True, "방화벽 없음"
        
        try:
            if self.firewall_type == "ufw":
                return self._configure_ufw()
            elif self.firewall_type == "firewalld":
                return self._configure_firewalld()
            elif self.firewall_type == "iptables":
                return self._configure_iptables()
        
        except Exception as e:
            error_msg = f"방화벽 설정 실패: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def _configure_ufw(self) -> Tuple[bool, str]:
        """UFW 설정"""
        console.print("[cyan]UFW 방화벽 규칙 추가 중...[/cyan]")
        self.logger.info("Configuring UFW...")
        
        ports = [
            (self.vpn_port, "udp", "VPN (Tailscale/Headscale)"),
            (self.k8s_api_port, "tcp", "Kubernetes API"),
            (self.kubelet_port, "tcp", "Kubelet API"),
            (22, "tcp", "SSH"),
        ]
        
        for port, protocol, description in ports:
            subprocess.run(
                ["ufw", "allow", f"{port}/{protocol}"],
                capture_output=True
            )
            console.print(f"  ✓ {port}/{protocol} - {description}")
            self.logger.debug(f"Added UFW rule: {port}/{protocol}")
        
        # NodePort 범위
        start, end = self.nodeport_range.split("-")
        subprocess.run(
            ["ufw", "allow", f"{start}:{end}/tcp"],
            capture_output=True
        )
        console.print(f"  ✓ {self.nodeport_range}/tcp - NodePort range")
        self.logger.debug(f"Added UFW rule: {self.nodeport_range}/tcp")
        
        # 추가 포트
        for port_spec in self.additional_ports:
            subprocess.run(
                ["ufw", "allow", port_spec],
                capture_output=True
            )
            console.print(f"  ✓ {port_spec} - Additional port")
            self.logger.debug(f"Added UFW rule: {port_spec}")
        
        console.print("\n[green]✓ UFW 방화벽 설정 완료[/green]")
        self.logger.info("UFW configuration completed")
        return True, "UFW 설정 완료"
    
    def _configure_firewalld(self) -> Tuple[bool, str]:
        """firewalld 설정"""
        console.print("[cyan]firewalld 방화벽 규칙 추가 중...[/cyan]")
        self.logger.info("Configuring firewalld...")
        
        ports = [
            (self.vpn_port, "udp", "VPN"),
            (self.k8s_api_port, "tcp", "K8s API"),
            (self.kubelet_port, "tcp", "Kubelet"),
            (22, "tcp", "SSH"),
        ]
        
        for port, protocol, description in ports:
            subprocess.run(
                ["firewall-cmd", "--permanent", f"--add-port={port}/{protocol}"],
                capture_output=True
            )
            console.print(f"  ✓ {port}/{protocol} - {description}")
            self.logger.debug(f"Added firewalld rule: {port}/{protocol}")
        
        # NodePort 범위
        subprocess.run(
            ["firewall-cmd", "--permanent", f"--add-port={self.nodeport_range}/tcp"],
            capture_output=True
        )
        console.print(f"  ✓ {self.nodeport_range}/tcp - NodePort range")
        self.logger.debug(f"Added firewalld rule: {self.nodeport_range}/tcp")
        
        # 추가 포트
        for port_spec in self.additional_ports:
            subprocess.run(
                ["firewall-cmd", "--permanent", f"--add-port={port_spec}"],
                capture_output=True
            )
            console.print(f"  ✓ {port_spec} - Additional port")
            self.logger.debug(f"Added firewalld rule: {port_spec}")
        
        # 규칙 적용
        subprocess.run(
            ["firewall-cmd", "--reload"],
            capture_output=True
        )
        
        console.print("\n[green]✓ firewalld 방화벽 설정 완료[/green]")
        self.logger.info("firewalld configuration completed")
        return True, "firewalld 설정 완료"
    
    def _configure_iptables(self) -> Tuple[bool, str]:
        """iptables 설정"""
        console.print("[cyan]iptables 방화벽 규칙 추가 중...[/cyan]")
        self.logger.info("Configuring iptables...")
        
        ports = [
            (self.vpn_port, "udp", "VPN"),
            (self.k8s_api_port, "tcp", "K8s API"),
            (self.kubelet_port, "tcp", "Kubelet"),
            (22, "tcp", "SSH"),
        ]
        
        for port, protocol, description in ports:
            subprocess.run(
                ["iptables", "-A", "INPUT", "-p", protocol, "--dport", str(port), "-j", "ACCEPT"],
                capture_output=True
            )
            console.print(f"  ✓ {port}/{protocol} - {description}")
            self.logger.debug(f"Added iptables rule: {port}/{protocol}")
        
        # NodePort 범위
        start, end = self.nodeport_range.split("-")
        subprocess.run(
            ["iptables", "-A", "INPUT", "-p", "tcp", "--dport", f"{start}:{end}", "-j", "ACCEPT"],
            capture_output=True
        )
        console.print(f"  ✓ {self.nodeport_range}/tcp - NodePort range")
        self.logger.debug(f"Added iptables rule: {self.nodeport_range}/tcp")
        
        console.print("\n[green]✓ iptables 방화벽 설정 완료[/green]")
        self.logger.info("iptables configuration completed")
        return True, "iptables 설정 완료"

