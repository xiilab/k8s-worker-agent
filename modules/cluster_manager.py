"""
Kubernetes 클러스터 관리 모듈
"""
import subprocess
import time
import secrets
import ipaddress
import socket
import netifaces
from pathlib import Path


class ClusterManager:
    def __init__(self, logger):
        self.logger = logger
        self.rollback_steps = []
    
    def generate_hostname(self, prefix="worker"):
        """랜덤 호스트명 생성"""
        random_suffix = secrets.token_hex(4)
        return f"{prefix}-{random_suffix}"
    
    def set_hostname(self, hostname):
        """호스트명 설정"""
        try:
            self.logger.info(f"호스트명 설정 중: {hostname}")
            
            # 현재 호스트명 백업 (롤백용)
            result = subprocess.run(['hostname'], capture_output=True, text=True)
            old_hostname = result.stdout.strip()
            self.rollback_steps.append(('hostname', old_hostname))
            
            # 호스트명 변경
            subprocess.run(['hostnamectl', 'set-hostname', hostname], check=True)
            
            # /etc/hosts 업데이트
            with open('/etc/hosts', 'r') as f:
                hosts_content = f.read()
            
            if old_hostname in hosts_content:
                hosts_content = hosts_content.replace(old_hostname, hostname)
            else:
                hosts_content += f"\n127.0.1.1 {hostname}\n"
            
            with open('/etc/hosts', 'w') as f:
                f.write(hosts_content)
            
            self.logger.info(f"✓ 호스트명 설정 완료: {hostname}")
            return True
        
        except Exception as e:
            self.logger.error(f"호스트명 설정 실패: {str(e)}")
            return False
    
    def check_prerequisites(self):
        """클러스터 조인 전 사전 요구사항 확인"""
        self.logger.info("사전 요구사항 확인 중...")
        
        checks = {
            'kubeadm': ['kubeadm', 'version'],
            'kubelet': ['kubelet', '--version'],
            'CRI-O': ['crio', '--version'],
        }
        
        all_passed = True
        for name, cmd in checks.items():
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    self.logger.info(f"  ✓ {name} 설치됨")
                else:
                    self.logger.error(f"  ✗ {name} 확인 실패")
                    all_passed = False
            except Exception as e:
                self.logger.error(f"  ✗ {name} 없음: {str(e)}")
                all_passed = False
        
        # swap 확인
        result = subprocess.run(['swapon', '--show'], capture_output=True, text=True)
        if result.stdout.strip():
            self.logger.warning("  ⚠ swap이 활성화되어 있습니다. 비활성화를 권장합니다.")
        else:
            self.logger.info("  ✓ swap 비활성화됨")
        
        return all_passed
    
    def check_node_ip_conflict(self, node_ip, api_server):
        """
        동일한 IP를 가진 노드가 클러스터에 이미 등록되어 있는지 확인
        """
        try:
            # 기존 kubelet.conf가 있으면 사용 (재설치 시나리오)
            kubeconfig_path = '/etc/kubernetes/kubelet.conf'
            
            if Path(kubeconfig_path).exists():
                # 기존 kubeconfig로 노드 목록 확인
                check_cmd = [
                    'kubectl', '--kubeconfig', kubeconfig_path, 'get', 'nodes',
                    '-o', 'custom-columns=NAME:.metadata.name,IP:.status.addresses[0].address',
                    '--no-headers'
                ]
                
                result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if line:
                            parts = line.split()
                            if len(parts) >= 2:
                                node_name, node_addr = parts[0], parts[1]
                                if node_addr == node_ip:
                                    # 현재 호스트명과 다른 노드만 경고
                                    current_hostname = subprocess.run(['hostname'], capture_output=True, text=True).stdout.strip()
                                    if node_name != current_hostname:
                                        self.logger.warning(f"⚠️  동일한 IP({node_ip})를 가진 노드가 이미 클러스터에 등록되어 있습니다: {node_name}")
                                        self.logger.warning(f"   이 노드를 계속 등록하면 네트워크 충돌이 발생할 수 있습니다.")
                                        self.logger.warning(f"   마스터 노드에서 다음 명령으로 기존 노드를 제거하세요:")
                                        self.logger.warning(f"   kubectl delete node {node_name}")
                                        return True
            return False
        except Exception as e:
            self.logger.debug(f"노드 IP 충돌 체크 실패 (계속 진행): {str(e)}")
            return False
    
    def get_node_ip_for_master(self, master_ip):
        """
        마스터 노드와 같은 네트워크 대역에 있는 로컬 IP 찾기
        """
        try:
            # 마스터 IP 파싱
            master_addr = ipaddress.ip_address(master_ip)
            
            # 모든 네트워크 인터페이스 확인
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                
                # IPv4 주소만 확인
                if netifaces.AF_INET not in addrs:
                    continue
                
                for addr_info in addrs[netifaces.AF_INET]:
                    local_ip = addr_info.get('addr')
                    netmask = addr_info.get('netmask')
                    
                    if not local_ip or not netmask or local_ip == '127.0.0.1':
                        continue
                    
                    try:
                        # 로컬 네트워크 생성
                        local_addr = ipaddress.ip_address(local_ip)
                        network = ipaddress.ip_network(f"{local_ip}/{netmask}", strict=False)
                        
                        # 마스터 IP가 이 네트워크에 속하는지 확인
                        if master_addr in network:
                            self.logger.info(f"마스터 노드와 통신 가능한 로컬 IP 발견: {local_ip} (인터페이스: {interface}, 네트워크: {network})")
                            return local_ip
                    except Exception as e:
                        continue
            
            # 찾지 못한 경우 경고
            self.logger.warning(f"마스터 노드({master_ip})와 같은 네트워크 대역의 로컬 IP를 찾지 못했습니다.")
            self.logger.warning("기본 IP가 사용되며, 마스터에서 이 노드로 접근하지 못할 수 있습니다.")
            return None
            
        except Exception as e:
            self.logger.error(f"노드 IP 감지 중 오류: {str(e)}")
            return None
    
    def join_cluster(self, api_server, token, ca_cert_hash, node_labels=None):
        """
        Kubernetes 클러스터에 워커 노드로 조인
        """
        try:
            self.logger.info("클러스터 조인 시작...")
            
            # 기존 Kubernetes 설정 파일 확인 및 정리
            if Path('/etc/kubernetes/pki').exists():
                self.logger.warning("기존 Kubernetes 설정이 발견되었습니다. 정리 중...")
                subprocess.run(['kubeadm', 'reset', '-f'], timeout=60, capture_output=True)
                subprocess.run(['rm', '-rf', '/etc/kubernetes'], capture_output=True)
                subprocess.run(['rm', '-rf', '/var/lib/kubelet/*'], shell=True, capture_output=True)
                subprocess.run(['rm', '-rf', '/etc/cni/net.d/*'], shell=True, capture_output=True)
                self.logger.info("✓ 기존 설정 정리 완료")
            
            # 비표준 클러스터 호환성: /etc/kubernetes/ssl → /etc/kubernetes/pki 심볼릭 링크
            # kubespray 등 비표준 클러스터가 /etc/kubernetes/ssl/ca.crt를 요구할 경우 대비
            self.logger.info("비표준 클러스터 호환성: CA 경로 심볼릭 링크 준비 중...")
            k8s_dir = Path('/etc/kubernetes')
            ssl_dir = k8s_dir / 'ssl'
            
            # 기존 ssl 디렉토리/링크 제거
            if ssl_dir.exists() or ssl_dir.is_symlink():
                subprocess.run(['rm', '-rf', str(ssl_dir)], capture_output=True)
            
            # /etc/kubernetes 디렉토리 생성
            k8s_dir.mkdir(parents=True, exist_ok=True)
            
            # ssl → pki 심볼릭 링크 생성
            subprocess.run(
                ['ln', '-sf', 'pki', str(ssl_dir)],
                check=True,
                capture_output=True
            )
            self.logger.info("✓ /etc/kubernetes/ssl → /etc/kubernetes/pki 심볼릭 링크 생성 완료")
            
            # 마스터 노드와 같은 네트워크의 로컬 IP 자동 감지
            master_ip = api_server.split(':')[0]  # "10.61.3.12:6443" -> "10.61.3.12"
            node_ip = self.get_node_ip_for_master(master_ip)
            
            # 동일한 IP를 가진 노드가 이미 등록되어 있는지 확인
            if node_ip and self.check_node_ip_conflict(node_ip, api_server):
                self.logger.error("❌ IP 충돌로 인해 클러스터 조인을 중단합니다.")
                self.logger.info("   기존 노드를 제거한 후 다시 시도하세요.")
                return False

            # 노드 레이블을 kubelet 설정에 추가 (kubeadm v1.24+ 호환)
            if node_labels:
                self.logger.info(f"노드 레이블 처리 중: {', '.join(node_labels)}")
                
                # kubernetes.io/k8s.io 레이블 필터링 및 중복 제거
                safe_labels = []
                safe_labels_set = set()  # 중복 방지용
                filtered_labels = []
                
                for label in node_labels:
                    # kubernetes.io 또는 k8s.io 레이블은 kubelet이 설정할 수 없음
                    if 'kubernetes.io' in label or 'k8s.io' in label:
                        filtered_labels.append(label)
                        continue
                    
                    # 이미 added-username 또는 added-user-domain이면 그대로 사용 (중복 방지)
                    if label.startswith('added-username=') or label.startswith('added-user-domain='):
                        if label not in safe_labels_set:
                            safe_labels.append(label)
                            safe_labels_set.add(label)
                        continue
                    
                    # 이메일 형식 레이블 처리 (added-by=email@domain)
                    if '=' in label and '@' in label:
                        key, value = label.split('=', 1)
                        if '@' in value:
                            # 이메일을 username과 domain으로 분리
                            username, domain = value.split('@', 1)
                            username_label = f'added-username={username}'
                            domain_label = f'added-user-domain={domain}'
                            
                            if username_label not in safe_labels_set:
                                safe_labels.append(username_label)
                                safe_labels_set.add(username_label)
                            if domain_label not in safe_labels_set:
                                safe_labels.append(domain_label)
                                safe_labels_set.add(domain_label)
                            
                            self.logger.info(f"이메일 레이블 분리: {username} @ {domain}")
                            continue
                    
                    # @ 기호가 있으면 하이픈으로 교체
                    safe_label = label.replace('@', '-at-')
                    if safe_label not in safe_labels_set:
                        safe_labels.append(safe_label)
                        safe_labels_set.add(safe_label)
                
                # 필터링된 레이블 안내
                if filtered_labels:
                    self.logger.warning(f"kubernetes.io/k8s.io 레이블은 kubelet으로 설정할 수 없습니다: {', '.join(filtered_labels)}")
                    self.logger.info("→ 이 레이블은 조인 후 마스터 노드에서 kubectl로 추가해주세요")
                
                # 안전한 레이블만 kubelet 설정에 추가
                if safe_labels:
                    labels_str = ','.join(safe_labels)
                    self.logger.info(f"kubelet 레이블 설정: {labels_str}")
                    
                    # /etc/default/kubelet에 레이블 + node-ip 추가
                    kubelet_extra_args = f'KUBELET_EXTRA_ARGS=--container-runtime-endpoint=unix:///var/run/crio/crio.sock --node-labels={labels_str}'
                    if node_ip:
                        kubelet_extra_args += f' --node-ip={node_ip}'
                    kubelet_extra_args += '\n'
                    
                    with open('/etc/default/kubelet', 'w') as f:
                        f.write(kubelet_extra_args)
                    
                    self.logger.info("✓ kubelet 설정에 레이블 추가 완료")
                else:
                    # 레이블이 없으면 기본 설정만 (+ node-ip)
                    kubelet_extra_args = 'KUBELET_EXTRA_ARGS=--container-runtime-endpoint=unix:///var/run/crio/crio.sock'
                    if node_ip:
                        kubelet_extra_args += f' --node-ip={node_ip}'
                    kubelet_extra_args += '\n'
                    
                    with open('/etc/default/kubelet', 'w') as f:
                        f.write(kubelet_extra_args)
                    
                    self.logger.info("kubelet 기본 설정 완료 (레이블 없음)")
            
            # kubeadm join 명령 구성 (--node-labels 제거됨)
            join_cmd = [
                'kubeadm', 'join', api_server,
                '--token', token,
                '--discovery-token-ca-cert-hash', ca_cert_hash,
                '--cri-socket', 'unix:///var/run/crio/crio.sock'
            ]
            
            self.logger.info(f"실행 명령: {' '.join(join_cmd[:4])} ...")
            
            # kubeadm join 실행
            result = subprocess.run(
                join_cmd,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                self.logger.info("✓ 클러스터 조인 성공!")
                self.logger.debug(f"출력:\n{result.stdout}")
                
                # kubelet 시작
                subprocess.run(['systemctl', 'start', 'kubelet'], check=True)
                subprocess.run(['systemctl', 'enable', 'kubelet'], check=True)
                
                self.rollback_steps.append(('cluster_joined', True))
                
                # 노드 상태 확인
                time.sleep(5)
                self._check_node_status()
                
                return True
            else:
                self.logger.error(f"클러스터 조인 실패:\n{result.stderr}")
                return False
        
        except subprocess.TimeoutExpired:
            self.logger.error("클러스터 조인 타임아웃 (5분 초과)")
            return False
        except Exception as e:
            self.logger.error(f"클러스터 조인 중 오류: {str(e)}")
            return False
    
    def _check_node_status(self):
        """노드 상태 확인"""
        try:
            self.logger.info("노드 상태 확인 중...")
            
            result = subprocess.run(
                ['systemctl', 'status', 'kubelet'],
                capture_output=True,
                text=True
            )
            
            if 'active (running)' in result.stdout:
                self.logger.info("✓ kubelet이 정상 실행 중입니다")
            else:
                self.logger.warning("⚠ kubelet 상태를 확인하세요")
        
        except Exception as e:
            self.logger.warning(f"노드 상태 확인 실패: {str(e)}")
    
    def rollback(self):
        """
        실패 시 롤백 수행
        """
        self.logger.warning("롤백 시작...")
        
        for step_type, step_data in reversed(self.rollback_steps):
            try:
                if step_type == 'hostname':
                    self.logger.info(f"호스트명 복원: {step_data}")
                    subprocess.run(['hostnamectl', 'set-hostname', step_data])
                
                elif step_type == 'cluster_joined':
                    self.logger.info("클러스터에서 노드 제거 중...")
                    # 완전한 정리
                    subprocess.run(['kubeadm', 'reset', '-f'], timeout=60, capture_output=True)
                    subprocess.run(['systemctl', 'stop', 'kubelet'])
                    subprocess.run(['rm', '-rf', '/etc/kubernetes'], capture_output=True)
                    subprocess.run(['rm', '-rf', '/var/lib/kubelet/*'], shell=True, capture_output=True)
                    subprocess.run(['rm', '-rf', '/etc/cni/net.d/*'], shell=True, capture_output=True)
                    self.logger.info("✓ Kubernetes 설정 완전히 제거됨")
            
            except Exception as e:
                self.logger.error(f"롤백 단계 실패 ({step_type}): {str(e)}")
        
        self.rollback_steps.clear()
        self.logger.info("롤백 완료")
    
    def reset_node(self):
        """
        노드를 초기 상태로 리셋
        """
        try:
            self.logger.info("노드 리셋 중...")
            
            result = subprocess.run(
                ['kubeadm', 'reset', '-f'],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                self.logger.info("✓ 노드 리셋 완료")
                
                # 추가 정리
                subprocess.run(['systemctl', 'stop', 'kubelet'])
                subprocess.run(['rm', '-rf', '/etc/cni/net.d'])
                subprocess.run(['rm', '-rf', '/var/lib/kubelet/*'])
                
                return True
            else:
                self.logger.error(f"노드 리셋 실패: {result.stderr}")
                return False
        
        except Exception as e:
            self.logger.error(f"노드 리셋 중 오류: {str(e)}")
            return False

