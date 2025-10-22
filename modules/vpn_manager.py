"""
VPN(Headscale) 관리 모듈
"""
import subprocess
import socket
import time
from pathlib import Path


class VPNManager:
    def __init__(self, logger):
        self.logger = logger
        self.headscale_installed = False
    
    def check_connectivity(self, host, port=6443, timeout=3):
        """
        대상 호스트와의 연결 가능 여부 확인
        """
        try:
            # IP와 포트 분리
            if ':' in host:
                host, port = host.rsplit(':', 1)
                port = int(port)
            
            self.logger.info(f"연결 테스트 중: {host}:{port}")
            
            # TCP 연결 시도
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                self.logger.info(f"✓ {host}:{port} 연결 성공")
                return True
            else:
                self.logger.warning(f"✗ {host}:{port} 연결 실패")
                return False
        
        except socket.gaierror:
            self.logger.error(f"호스트 이름을 해석할 수 없습니다: {host}")
            return False
        except Exception as e:
            self.logger.error(f"연결 테스트 중 오류: {str(e)}")
            return False
    
    def ping_test(self, host, count=3):
        """
        ping 테스트로 연결 확인
        """
        try:
            # IP만 추출
            if ':' in host:
                host = host.rsplit(':', 1)[0]
            
            self.logger.info(f"Ping 테스트 중: {host}")
            
            result = subprocess.run(
                ['ping', '-c', str(count), '-W', '2', host],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                self.logger.info(f"✓ Ping 성공: {host}")
                return True
            else:
                self.logger.warning(f"✗ Ping 실패: {host}")
                return False
        
        except subprocess.TimeoutExpired:
            self.logger.warning(f"Ping 타임아웃: {host}")
            return False
        except Exception as e:
            self.logger.error(f"Ping 테스트 중 오류: {str(e)}")
            return False
    
    def install_headscale_client(self):
        """
        Headscale 클라이언트(Tailscale) 설치
        """
        try:
            self.logger.info("Headscale 클라이언트 설치 중...")
            
            # Tailscale 설치 (Headscale과 호환)
            commands = [
                "curl -fsSL https://tailscale.com/install.sh | sh"
            ]
            
            for cmd in commands:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    self.logger.error(f"설치 실패: {result.stderr}")
                    return False
            
            self.headscale_installed = True
            self.logger.info("✓ Headscale 클라이언트 설치 완료")
            return True
        
        except Exception as e:
            self.logger.error(f"Headscale 클라이언트 설치 중 오류: {str(e)}")
            return False
    
    def connect_headscale(self, headscale_url, auth_key):
        """
        Headscale 서버에 연결
        """
        try:
            if not self.headscale_installed:
                if not self.install_headscale_client():
                    return False
            
            self.logger.info(f"Headscale 서버 연결 중: {headscale_url}")
            
            # Tailscale을 Headscale 서버로 설정
            commands = [
                f"tailscale up --login-server={headscale_url} --authkey={auth_key} --accept-routes"
            ]
            
            for cmd in commands:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    self.logger.error(f"연결 실패: {result.stderr}")
                    return False
            
            # 연결 확인
            time.sleep(3)
            status = subprocess.run(
                ['tailscale', 'status'],
                capture_output=True,
                text=True
            )
            
            if status.returncode == 0:
                self.logger.info("✓ Headscale VPN 연결 성공")
                self.logger.debug(f"VPN 상태:\n{status.stdout}")
                return True
            else:
                self.logger.error("VPN 연결 확인 실패")
                return False
        
        except Exception as e:
            self.logger.error(f"Headscale 연결 중 오류: {str(e)}")
            return False
    
    def disconnect_headscale(self):
        """
        Headscale 연결 해제
        """
        try:
            self.logger.info("Headscale VPN 연결 해제 중...")
            
            result = subprocess.run(
                ['tailscale', 'down'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.logger.info("✓ VPN 연결 해제 완료")
                return True
            else:
                self.logger.warning(f"VPN 연결 해제 실패: {result.stderr}")
                return False
        
        except Exception as e:
            self.logger.error(f"VPN 연결 해제 중 오류: {str(e)}")
            return False
    
    def auto_detect_vpn_need(self, master_api_server):
        """
        VPN 필요 여부 자동 감지
        """
        self.logger.info("VPN 필요 여부 자동 감지 중...")
        
        # 1차: Ping 테스트
        if self.ping_test(master_api_server):
            self.logger.info("→ 마스터 노드와 직접 통신 가능, VPN 불필요")
            return False
        
        # 2차: TCP 연결 테스트
        if self.check_connectivity(master_api_server):
            self.logger.info("→ 마스터 노드와 직접 통신 가능, VPN 불필요")
            return False
        
        self.logger.warning("→ 마스터 노드와 직접 통신 불가, VPN 필요")
        return True

