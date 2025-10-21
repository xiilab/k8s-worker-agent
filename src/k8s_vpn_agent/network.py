"""
네트워크 연결성 체크 모듈
ping, 포트, DNS, HTTP 체크 기능
"""

import subprocess
import socket
import requests
from typing import Tuple, Optional, Dict
from rich.console import Console
from .logger import get_logger

console = Console()


class NetworkChecker:
    """네트워크 연결성 확인 클래스"""
    
    def __init__(self, debug: bool = False):
        self.debug = debug
        self.logger = get_logger()
    
    def check_ping(self, host: str, count: int = 3, timeout: int = 5) -> Tuple[bool, str]:
        """호스트 핑 테스트"""
        try:
            self.logger.debug(f"Pinging {host}...")
            cmd = ["ping", "-c", str(count), "-W", str(timeout), host]
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout + 5
            )
            
            if result.returncode == 0:
                self.logger.debug(f"✓ {host} is reachable")
                return True, f"✓ {host} 응답 성공"
            else:
                self.logger.warning(f"✗ {host} is unreachable")
                return False, f"✗ {host} 응답 실패"
        
        except subprocess.TimeoutExpired:
            self.logger.error(f"✗ Ping timeout for {host}")
            return False, f"✗ {host} 타임아웃"
        except Exception as e:
            self.logger.error(f"Ping error: {str(e)}")
            return False, f"✗ 핑 테스트 오류: {str(e)}"
    
    def check_port(self, host: str, port: int, timeout: int = 5) -> Tuple[bool, str]:
        """포트 연결 테스트"""
        try:
            self.logger.debug(f"Checking port {host}:{port}...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                self.logger.debug(f"✓ {host}:{port} is open")
                return True, f"✓ {host}:{port} 연결 성공"
            else:
                self.logger.warning(f"✗ {host}:{port} is closed")
                return False, f"✗ {host}:{port} 연결 실패"
        
        except socket.gaierror:
            self.logger.error(f"✗ Cannot resolve {host}")
            return False, f"✗ {host} 호스트를 찾을 수 없습니다"
        except Exception as e:
            self.logger.error(f"Port check error: {str(e)}")
            return False, f"✗ 포트 테스트 오류: {str(e)}"
    
    def check_dns(self, domain: str = "google.com") -> Tuple[bool, str]:
        """DNS 조회 테스트"""
        try:
            self.logger.debug(f"Checking DNS for {domain}...")
            socket.gethostbyname(domain)
            self.logger.debug("✓ DNS resolution successful")
            return True, f"✓ DNS 조회 성공 ({domain})"
        except socket.gaierror:
            self.logger.warning("✗ DNS resolution failed")
            return False, f"✗ DNS 조회 실패 ({domain})"
        except Exception as e:
            self.logger.error(f"DNS check error: {str(e)}")
            return False, f"✗ DNS 테스트 오류: {str(e)}"
    
    def check_http(self, url: str, timeout: int = 5) -> Tuple[bool, str]:
        """HTTP/HTTPS 연결 테스트"""
        try:
            self.logger.debug(f"Checking HTTP connection to {url}...")
            response = requests.get(url, timeout=timeout, verify=False)
            if response.status_code < 400:
                self.logger.debug(f"✓ HTTP connection successful (status: {response.status_code})")
                return True, f"✓ HTTP 연결 성공 ({url})"
            else:
                self.logger.warning(f"✗ HTTP error: {response.status_code}")
                return False, f"✗ HTTP 오류: {response.status_code}"
        except requests.exceptions.SSLError:
            self.logger.error("✗ SSL certificate error")
            return False, f"✗ SSL 인증서 오류"
        except requests.exceptions.ConnectionError:
            self.logger.error("✗ Connection failed")
            return False, f"✗ 연결 실패"
        except requests.exceptions.Timeout:
            self.logger.error("✗ Connection timeout")
            return False, f"✗ 타임아웃"
        except Exception as e:
            self.logger.error(f"HTTP check error: {str(e)}")
            return False, f"✗ HTTP 테스트 오류: {str(e)}"
    
    def check_interface(self, interface: str) -> Tuple[bool, str]:
        """네트워크 인터페이스 확인"""
        try:
            self.logger.debug(f"Checking interface {interface}...")
            result = subprocess.run(
                ["ip", "link", "show", interface],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                if "state UP" in result.stdout:
                    self.logger.debug(f"✓ Interface {interface} is UP")
                    return True, f"✓ {interface} 인터페이스 활성화"
                else:
                    self.logger.warning(f"✗ Interface {interface} is DOWN")
                    return False, f"✗ {interface} 인터페이스 비활성화"
            else:
                self.logger.warning(f"✗ Interface {interface} not found")
                return False, f"✗ {interface} 인터페이스를 찾을 수 없습니다"
        
        except Exception as e:
            self.logger.error(f"Interface check error: {str(e)}")
            return False, f"✗ 인터페이스 확인 오류: {str(e)}"
    
    def get_interface_ip(self, interface: str) -> Optional[str]:
        """인터페이스의 IP 주소 가져오기"""
        try:
            result = subprocess.run(
                ["ip", "addr", "show", interface],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'inet ' in line:
                        ip = line.strip().split()[1].split('/')[0]
                        self.logger.debug(f"Interface {interface} IP: {ip}")
                        return ip
            
            return None
        
        except Exception as e:
            self.logger.error(f"Get interface IP error: {str(e)}")
            return None
    
    def comprehensive_check(self, master_ip: str, vpn_interface: Optional[str] = None) -> Dict:
        """종합 네트워크 체크"""
        console.print("\n[bold cyan]네트워크 연결성 체크 시작...[/bold cyan]\n")
        self.logger.info("Starting comprehensive network check...")
        
        results = {
            "vpn": None,
            "master_ping": None,
            "master_api": None,
            "dns": None,
            "internet": None,
            "overall": False,
        }
        
        # VPN 인터페이스 체크
        if vpn_interface:
            success, msg = self.check_interface(vpn_interface)
            results["vpn"] = {"success": success, "message": msg}
            console.print(f"  {msg}")
            
            if success:
                vpn_ip = self.get_interface_ip(vpn_interface)
                if vpn_ip:
                    console.print(f"    VPN IP: {vpn_ip}")
                    self.logger.info(f"VPN IP: {vpn_ip}")
        
        # 마스터 노드 핑 체크
        success, msg = self.check_ping(master_ip)
        results["master_ping"] = {"success": success, "message": msg}
        console.print(f"  {msg}")
        
        # K8s API 서버 포트 체크
        success, msg = self.check_port(master_ip, 6443)
        results["master_api"] = {"success": success, "message": msg}
        console.print(f"  {msg}")
        
        # DNS 체크
        success, msg = self.check_dns()
        results["dns"] = {"success": success, "message": msg}
        console.print(f"  {msg}")
        
        # 인터넷 연결 체크
        success, msg = self.check_ping("8.8.8.8", count=2)
        results["internet"] = {"success": success, "message": msg}
        console.print(f"  {msg}")
        
        # 전체 결과 판단
        critical_checks = [
            results["master_ping"]["success"] if results["master_ping"] else False,
            results["master_api"]["success"] if results["master_api"] else False,
        ]
        
        results["overall"] = all(critical_checks)
        
        console.print()
        if results["overall"]:
            console.print("[bold green]✓ 네트워크 연결성 체크 통과[/bold green]")
            self.logger.info("Network connectivity check passed")
        else:
            console.print("[bold red]✗ 네트워크 연결성 체크 실패[/bold red]")
            console.print("[yellow]마스터 노드와의 연결을 확인해주세요.[/yellow]")
            self.logger.error("Network connectivity check failed")
        
        return results

