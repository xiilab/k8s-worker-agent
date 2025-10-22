"""
방화벽 관리 모듈
"""
import subprocess


class FirewallManager:
    def __init__(self, logger):
        self.logger = logger
        self.firewall_type = self._detect_firewall()
    
    def _detect_firewall(self):
        """시스템의 방화벽 타입 감지"""
        try:
            # ufw 확인
            result = subprocess.run(['which', 'ufw'], capture_output=True)
            if result.returncode == 0:
                return 'ufw'
            
            # firewalld 확인
            result = subprocess.run(['which', 'firewall-cmd'], capture_output=True)
            if result.returncode == 0:
                return 'firewalld'
            
            # iptables
            result = subprocess.run(['which', 'iptables'], capture_output=True)
            if result.returncode == 0:
                return 'iptables'
            
            return None
        except Exception:
            return None
    
    def configure_firewall(self, k8s_api_port=6443, kubelet_port=10250, nodeport_range="30000-32767"):
        """
        Kubernetes 워커 노드에 필요한 방화벽 규칙 설정
        """
        try:
            self.logger.info(f"방화벽 설정 중... (타입: {self.firewall_type})")
            
            if self.firewall_type == 'ufw':
                return self._configure_ufw(k8s_api_port, kubelet_port, nodeport_range)
            elif self.firewall_type == 'firewalld':
                return self._configure_firewalld(k8s_api_port, kubelet_port, nodeport_range)
            elif self.firewall_type == 'iptables':
                return self._configure_iptables(k8s_api_port, kubelet_port, nodeport_range)
            else:
                self.logger.warning("방화벽을 감지하지 못했습니다. 수동으로 포트를 개방해주세요.")
                return True  # 방화벽이 없으면 통과
        
        except Exception as e:
            self.logger.error(f"방화벽 설정 중 오류: {str(e)}")
            return False
    
    def _configure_ufw(self, k8s_api_port, kubelet_port, nodeport_range):
        """UFW 방화벽 설정"""
        commands = [
            f"ufw allow {kubelet_port}/tcp comment 'Kubelet API'",
            f"ufw allow {nodeport_range}/tcp comment 'NodePort Services'",
            f"ufw allow {nodeport_range}/udp comment 'NodePort Services'",
            "ufw allow 10256/tcp comment 'kube-proxy health check'",
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.warning(f"UFW 규칙 추가 실패: {cmd}")
        
        self.logger.info("✓ UFW 방화벽 설정 완료")
        return True
    
    def _configure_firewalld(self, k8s_api_port, kubelet_port, nodeport_range):
        """firewalld 방화벽 설정"""
        commands = [
            f"firewall-cmd --permanent --add-port={kubelet_port}/tcp",
            f"firewall-cmd --permanent --add-port={nodeport_range}/tcp",
            f"firewall-cmd --permanent --add-port={nodeport_range}/udp",
            "firewall-cmd --permanent --add-port=10256/tcp",
            "firewall-cmd --reload"
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.warning(f"firewalld 규칙 추가 실패: {cmd}")
        
        self.logger.info("✓ firewalld 방화벽 설정 완료")
        return True
    
    def _configure_iptables(self, k8s_api_port, kubelet_port, nodeport_range):
        """iptables 방화벽 설정"""
        start_port, end_port = nodeport_range.split('-')
        
        commands = [
            f"iptables -A INPUT -p tcp --dport {kubelet_port} -j ACCEPT",
            f"iptables -A INPUT -p tcp --dport {start_port}:{end_port} -j ACCEPT",
            f"iptables -A INPUT -p udp --dport {start_port}:{end_port} -j ACCEPT",
            "iptables -A INPUT -p tcp --dport 10256 -j ACCEPT",
        ]
        
        for cmd in commands:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.warning(f"iptables 규칙 추가 실패: {cmd}")
        
        # iptables 규칙 저장
        subprocess.run("iptables-save > /etc/iptables/rules.v4", shell=True)
        
        self.logger.info("✓ iptables 방화벽 설정 완료")
        return True
    
    def check_port_open(self, port):
        """특정 포트가 열려있는지 확인"""
        try:
            result = subprocess.run(
                f"netstat -tuln | grep :{port}",
                shell=True,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

