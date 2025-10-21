"""
VPN 관리 모듈 (Headscale/Tailscale)
idempotent 및 롤백 지원
"""

import subprocess
import time
import json
from typing import Tuple, Optional, Dict
from rich.console import Console
from .logger import get_logger

console = Console()


class VPNManager:
    """VPN 관리 클래스"""
    
    def __init__(self, config: Dict, debug: bool = False):
        self.config = config
        self.debug = debug
        self.logger = get_logger()
        self.vpn_type = config.get("type", "headscale")
        self.headscale_url = config.get("headscale_url", "")
        self.auth_key = config.get("auth_key", "")
        self.namespace = config.get("namespace", "default")
        self.idempotent = True
        self.original_state = None
    
    def save_state(self):
        """현재 상태 저장 (롤백용)"""
        try:
            self.original_state = {
                "connected": self.is_connected(),
                "status": self.get_status()
            }
            self.logger.debug(f"Saved VPN state: {self.original_state}")
        except Exception as e:
            self.logger.error(f"Failed to save VPN state: {e}")
    
    def rollback(self) -> bool:
        """이전 상태로 롤백"""
        try:
            self.logger.info("Rolling back VPN configuration...")
            console.print("\n[yellow]VPN 설정 롤백 중...[/yellow]")
            
            if not self.original_state:
                self.logger.warning("No saved state to rollback")
                return True
            
            # VPN이 원래 연결되어 있지 않았다면 연결 해제
            if not self.original_state.get("connected", False):
                self.disconnect()
            
            self.logger.info("VPN rollback completed")
            console.print("[green]✓ VPN 롤백 완료[/green]")
            return True
        
        except Exception as e:
            self.logger.error(f"VPN rollback failed: {e}")
            console.print(f"[red]✗ VPN 롤백 실패: {e}[/red]")
            return False
    
    def is_installed(self) -> bool:
        """Tailscale 클라이언트 설치 확인"""
        try:
            result = subprocess.run(
                ["which", "tailscale"],
                capture_output=True,
                text=True
            )
            installed = result.returncode == 0
            self.logger.debug(f"Tailscale installed: {installed}")
            return installed
        except Exception:
            return False
    
    def install_client(self) -> Tuple[bool, str]:
        """Tailscale 클라이언트 설치"""
        console.print("[cyan]Tailscale 클라이언트 설치 중...[/cyan]")
        self.logger.info("Installing Tailscale client...")
        
        try:
            install_cmd = "curl -fsSL https://tailscale.com/install.sh | sh"
            
            result = subprocess.run(
                install_cmd,
                shell=True,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("[green]✓ Tailscale 클라이언트 설치 완료[/green]")
                self.logger.info("Tailscale client installed successfully")
                return True, "설치 완료"
            else:
                error_msg = f"설치 실패: {result.stderr}"
                self.logger.error(error_msg)
                return False, error_msg
        
        except Exception as e:
            error_msg = f"설치 오류: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def get_status(self) -> Dict:
        """VPN 상태 확인"""
        try:
            result = subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                status = json.loads(result.stdout)
                self.logger.debug(f"VPN status: {status.get('BackendState')}")
                return status
            else:
                return {}
        
        except Exception as e:
            self.logger.error(f"Failed to get VPN status: {e}")
            return {}
    
    def is_connected(self) -> bool:
        """VPN 연결 상태 확인"""
        status = self.get_status()
        connected = status.get("BackendState") == "Running"
        self.logger.debug(f"VPN connected: {connected}")
        return connected
    
    def connect(self) -> Tuple[bool, str]:
        """VPN 연결 (idempotent)"""
        console.print("\n[bold cyan]VPN 연결 시작...[/bold cyan]\n")
        self.logger.info("Starting VPN connection...")
        
        # 상태 저장
        self.save_state()
        
        # 이미 연결되어 있는지 확인 (idempotent)
        if self.is_connected():
            console.print("[green]✓ 이미 VPN에 연결되어 있습니다.[/green]")
            self.logger.info("VPN already connected (idempotent)")
            return True, "이미 연결됨"
        
        # 클라이언트 설치 확인
        if not self.is_installed():
            console.print("[yellow]Tailscale 클라이언트가 설치되어 있지 않습니다.[/yellow]")
            self.logger.warning("Tailscale client not installed")
            success, msg = self.install_client()
            if not success:
                return False, f"클라이언트 설치 실패: {msg}"
        
        # Headscale 서버 설정
        if self.vpn_type == "headscale" and self.headscale_url:
            console.print(f"[cyan]Headscale 서버 설정: {self.headscale_url}[/cyan]")
            self.logger.info(f"Configuring Headscale server: {self.headscale_url}")
            
            # tailscaled 시작
            try:
                subprocess.run(
                    ["systemctl", "start", "tailscaled"],
                    check=True
                )
                time.sleep(2)
                self.logger.debug("tailscaled started")
            except subprocess.CalledProcessError as e:
                error_msg = f"tailscaled 시작 실패: {str(e)}"
                self.logger.error(error_msg)
                return False, error_msg
            
            # Headscale 서버로 연결
            cmd = [
                "tailscale", "up",
                "--login-server", self.headscale_url,
                "--accept-routes",
                "--accept-dns=false"
            ]
            
            if self.auth_key:
                cmd.extend(["--authkey", self.auth_key])
            
            try:
                console.print("[cyan]VPN 연결 중...[/cyan]")
                self.logger.info("Connecting to VPN...")
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    console.print("[green]✓ VPN 연결 성공![/green]")
                    self.logger.info("VPN connected successfully")
                    
                    # 연결 정보 표시
                    time.sleep(2)
                    self.show_status()
                    
                    return True, "연결 성공"
                else:
                    error_msg = result.stderr or result.stdout
                    console.print(f"[red]✗ VPN 연결 실패: {error_msg}[/red]")
                    self.logger.error(f"VPN connection failed: {error_msg}")
                    
                    # Auth key가 필요한 경우
                    if "auth" in error_msg.lower() or "key" in error_msg.lower():
                        console.print("\n[yellow]Pre-authentication key가 필요합니다.[/yellow]")
                        console.print("[yellow]Headscale 서버에서 다음 명령어로 생성하세요:[/yellow]")
                        console.print(f"[cyan]headscale preauthkeys create --namespace {self.namespace}[/cyan]\n")
                        self.logger.warning("Pre-authentication key required")
                    
                    return False, error_msg
            
            except subprocess.TimeoutExpired:
                error_msg = "VPN 연결 타임아웃"
                console.print(f"[red]✗ {error_msg}[/red]")
                self.logger.error(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"연결 오류: {str(e)}"
                self.logger.exception(error_msg)
                return False, error_msg
        
        else:
            # 일반 Tailscale 연결
            console.print("[cyan]Tailscale 연결 중...[/cyan]")
            self.logger.info("Connecting to Tailscale...")
            
            try:
                result = subprocess.run(
                    ["tailscale", "up"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode == 0:
                    console.print("[green]✓ VPN 연결 성공![/green]")
                    self.logger.info("VPN connected successfully")
                    return True, "연결 성공"
                else:
                    error_msg = result.stderr
                    self.logger.error(f"VPN connection failed: {error_msg}")
                    return False, error_msg
            
            except Exception as e:
                error_msg = f"연결 오류: {str(e)}"
                self.logger.exception(error_msg)
                return False, error_msg
    
    def disconnect(self) -> Tuple[bool, str]:
        """VPN 연결 해제"""
        try:
            self.logger.info("Disconnecting VPN...")
            result = subprocess.run(
                ["tailscale", "down"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("[green]✓ VPN 연결 해제[/green]")
                self.logger.info("VPN disconnected")
                return True, "연결 해제 완료"
            else:
                error_msg = result.stderr
                self.logger.error(f"VPN disconnect failed: {error_msg}")
                return False, error_msg
        
        except Exception as e:
            error_msg = f"연결 해제 오류: {str(e)}"
            self.logger.exception(error_msg)
            return False, error_msg
    
    def show_status(self):
        """VPN 상태 표시"""
        try:
            result = subprocess.run(
                ["tailscale", "status"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                console.print("\n[bold]VPN 상태:[/bold]")
                console.print(result.stdout)
                self.logger.debug(f"VPN status:\n{result.stdout}")
            
            # IP 정보 표시
            result = subprocess.run(
                ["tailscale", "ip"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                ips = result.stdout.strip().split('\n')
                console.print(f"[bold]VPN IP:[/bold] {ips[0] if ips else 'N/A'}")
                self.logger.info(f"VPN IP: {ips[0] if ips else 'N/A'}")
        
        except Exception as e:
            console.print(f"[yellow]상태 조회 실패: {str(e)}[/yellow]")
            self.logger.error(f"Failed to show VPN status: {e}")
    
    def get_vpn_ip(self) -> Optional[str]:
        """VPN IP 주소 가져오기"""
        try:
            result = subprocess.run(
                ["tailscale", "ip", "-4"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                ip = result.stdout.strip()
                self.logger.debug(f"VPN IP: {ip}")
                return ip
            
            return None
        
        except Exception as e:
            self.logger.error(f"Failed to get VPN IP: {e}")
            return None
    
    def enable_autostart(self) -> Tuple[bool, str]:
        """부팅 시 자동 시작 설정"""
        try:
            self.logger.info("Enabling VPN autostart...")
            subprocess.run(
                ["systemctl", "enable", "tailscaled"],
                check=True
            )
            self.logger.info("VPN autostart enabled")
            return True, "자동 시작 설정 완료"
        except subprocess.CalledProcessError as e:
            error_msg = f"자동 시작 설정 실패: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

