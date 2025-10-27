#!/usr/bin/env python3
"""
Kubernetes Worker Node Agent
워커 노드를 Kubernetes 클러스터에 자동으로 조인하는 에이전트
"""
import sys
import os
import time
import argparse
from pathlib import Path

# 모듈 임포트
from modules.logger import AgentLogger
from modules.config_manager import ConfigManager
from modules.vpn_manager import VPNManager
from modules.firewall_manager import FirewallManager
from modules.cluster_manager import ClusterManager
from modules.tui import TUI


class K8sWorkerAgent:
    def __init__(self, auto_mode=False):
        self.auto_mode = auto_mode
        self.tui = TUI()
        self.logger = None
        self.config_manager = ConfigManager("config.yaml")
        self.vpn_manager = None
        self.firewall_manager = None
        self.cluster_manager = None
        self.config = None
    
    def check_root(self):
        """루트 권한 확인"""
        if os.geteuid() != 0:
            self.tui.show_error("이 프로그램은 root 권한이 필요합니다.")
            self.tui.console.print("sudo python3 agent.py 로 실행해주세요.")
            sys.exit(1)
    
    def initialize(self):
        """에이전트 초기화"""
        if not self.auto_mode:
            self.tui.show_welcome()
        
        # 설정 로드 또는 생성
        if not Path("config.yaml").exists():
            if self.auto_mode:
                self.tui.show_error("자동 모드에서는 config.yaml 파일이 필요합니다.")
                sys.exit(1)
            self.tui.show_warning("설정 파일이 없습니다.")
            if self.tui.confirm("새로운 설정 파일을 생성하시겠습니까?"):
                self.config = self.config_manager.create_default_config()
                self.tui.show_success("기본 설정 파일이 생성되었습니다.")
            else:
                self.tui.show_error("설정 파일이 필요합니다.")
                sys.exit(1)
        else:
            try:
                self.config = self.config_manager.load_config()
                if not self.auto_mode:
                    self.tui.show_success("설정 파일을 로드했습니다.")
            except Exception as e:
                self.tui.show_error(f"설정 파일 로드 실패: {str(e)}")
                sys.exit(1)
        
        # 로거 초기화
        log_file = self.config.get('system.log_file', '/var/log/k8s-agent.log')
        self.logger = AgentLogger(log_file)
        
        # 매니저 초기화
        self.vpn_manager = VPNManager(self.logger)
        self.firewall_manager = FirewallManager(self.logger)
        self.cluster_manager = ClusterManager(self.logger)
    
    def run_interactive_setup(self):
        """대화형 설정"""
        self.tui.console.print("\n[bold cyan]클러스터 조인 설정[/bold cyan]\n")
        
        # 1. 마스터 노드 정보
        master_config = self.tui.get_master_config(
            default_api_server=self.config.get('master_node.api_server', ''),
            default_token=self.config.get('master_node.token', ''),
            default_hash=self.config.get('master_node.ca_cert_hash', '')
        )
        self.config_manager.set('master_node', master_config)
        
        # 2. VPN 설정
        vpn_config = self.tui.get_vpn_config(auto_detect=True)
        self.config_manager.set('vpn', vpn_config)
        
        # 3. 워커 노드 설정
        worker_config = self.tui.get_worker_config(
            default_prefix=self.config.get('worker_node.hostname_prefix', 'worker'),
            default_username=self.config.get('worker_node.username', '')
        )
        
        # 사용자 이름 레이블 자동 생성 (이메일이면 분리)
        username = worker_config.get('username', '')
        if username:
            # 기본 레이블
            base_labels = ['node-role.kubernetes.io/worker=worker']
            
            # 이메일 형식이면 username과 domain 분리
            if '@' in username:
                user_part, domain_part = username.split('@', 1)
                base_labels.append(f'added-username={user_part}')
                base_labels.append(f'added-user-domain={domain_part}')
            else:
                base_labels.append(f'added-by={username}')
            
            worker_config['labels'] = base_labels
        
        self.config_manager.set('worker_node', worker_config)
        
        # 4. 방화벽 설정
        firewall_config = self.tui.get_firewall_config()
        self.config_manager.set('firewall', firewall_config)
        
        # 5. 시스템 설정
        system_config = self.tui.get_system_config()
        self.config_manager.set('system', system_config)
        
        # 설정 저장
        self.config_manager.save_config(self.config_manager.config)
        self.config = self.config_manager.config
        
        # 설정 요약
        self.tui.show_config_summary(self.config)
        
        if not self.tui.confirm("\n이 설정으로 진행하시겠습니까?"):
            self.tui.show_warning("작업이 취소되었습니다.")
            return False
        
        return True
    
    def join_cluster(self):
        """클러스터 조인 프로세스"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("클러스터 조인 프로세스 시작")
            self.logger.info("=" * 50)
            
            # 1. 사전 요구사항 확인
            self.tui.show_progress("사전 요구사항 확인 중...")
            if not self.cluster_manager.check_prerequisites():
                self.tui.show_error("사전 요구사항을 충족하지 못했습니다.")
                self.tui.console.print("quick_install.sh를 먼저 실행해주세요: sudo bash quick_install.sh")
                return False
            self.tui.show_success("사전 요구사항 확인 완료")
            
            # 2. VPN 설정 (필요시)
            master_api = self.config['master_node']['api_server']
            vpn_config = self.config['vpn']
            
            if vpn_config.get('auto_detect', True):
                self.tui.show_progress("VPN 필요 여부 자동 감지 중...")
                vpn_needed = self.vpn_manager.auto_detect_vpn_need(master_api)
                
                if vpn_needed:
                    self.tui.show_warning("마스터 노드와 직접 통신할 수 없습니다. VPN이 필요합니다.")
                    
                    if not vpn_config.get('headscale_url'):
                        self.tui.show_error("VPN 설정이 필요합니다.")
                        if self.tui.confirm("VPN 설정을 입력하시겠습니까?"):
                            vpn_input = self.tui.get_vpn_config(auto_detect=False)
                            self.config_manager.set('vpn', vpn_input)
                            self.config_manager.save_config(self.config_manager.config)
                            vpn_config = vpn_input
                        else:
                            return False
                    
                    if vpn_config['enabled'] or vpn_config.get('headscale_url'):
                        self.tui.show_progress("VPN 연결 중...")
                        if not self.vpn_manager.connect_headscale(
                            vpn_config['headscale_url'],
                            vpn_config['auth_key']
                        ):
                            self.tui.show_error("VPN 연결 실패")
                            return False
                        self.tui.show_success("VPN 연결 완료")
                        
                        # VPN 연결 후 재확인
                        time.sleep(3)
                        if not self.vpn_manager.check_connectivity(master_api):
                            self.tui.show_error("VPN 연결 후에도 마스터 노드에 접근할 수 없습니다.")
                            return False
                else:
                    self.tui.show_success("마스터 노드와 직접 통신 가능 (VPN 불필요)")
            
            elif vpn_config.get('enabled', False):
                self.tui.show_progress("VPN 연결 중...")
                if not self.vpn_manager.connect_headscale(
                    vpn_config['headscale_url'],
                    vpn_config['auth_key']
                ):
                    self.tui.show_error("VPN 연결 실패")
                    return False
                self.tui.show_success("VPN 연결 완료")
            
            # 3. 방화벽 설정
            if self.config['firewall'].get('auto_configure', True):
                self.tui.show_progress("방화벽 설정 중...")
                self.firewall_manager.configure_firewall(
                    k8s_api_port=self.config['firewall']['k8s_api_port'],
                    kubelet_port=self.config['firewall']['kubelet_port'],
                    nodeport_range=self.config['firewall']['nodeport_range']
                )
                self.tui.show_success("방화벽 설정 완료")
            
            # 4. 호스트명 설정
            hostname = self.cluster_manager.generate_hostname(
                prefix=self.config['worker_node']['hostname_prefix']
            )
            self.tui.show_progress(f"호스트명 설정 중: {hostname}")
            if not self.cluster_manager.set_hostname(hostname):
                self.tui.show_error("호스트명 설정 실패")
                return False
            self.tui.show_success(f"호스트명 설정 완료: {hostname}")
            
            # 5. 클러스터 조인
            self.tui.show_progress("클러스터 조인 중... (최대 5분 소요)")
            
            node_labels = self.config['worker_node'].get('labels', [])
            # 사용자 이름 레이블 추가
            if self.config['worker_node'].get('username'):
                username_label = f"added-by={self.config['worker_node']['username']}"
                if username_label not in node_labels:
                    node_labels.append(username_label)
            
            success = self.cluster_manager.join_cluster(
                api_server=self.config['master_node']['api_server'],
                token=self.config['master_node']['token'],
                ca_cert_hash=self.config['master_node']['ca_cert_hash'],
                node_labels=node_labels
            )
            
            if success:
                self.tui.show_success("클러스터 조인 성공!")
                self.tui.console.print("\n[bold green]워커 노드가 성공적으로 클러스터에 추가되었습니다![/bold green]")
                self.tui.console.print(f"[cyan]노드 이름: {hostname}[/cyan]")
                self.tui.console.print(f"[cyan]레이블: {', '.join(node_labels)}[/cyan]")
                return True
            else:
                self.tui.show_error("클러스터 조인 실패")
                return False
        
        except Exception as e:
            self.logger.error(f"클러스터 조인 중 예외 발생: {str(e)}")
            self.tui.show_error(f"오류 발생: {str(e)}")
            return False
    
    def handle_failure(self):
        """실패 처리"""
        if self.config.get('system.rollback_on_failure', True):
            self.tui.show_warning("롤백을 수행합니다...")
            self.cluster_manager.rollback()
            
            # VPN 연결 해제
            if self.config.get('vpn.enabled', False):
                self.vpn_manager.disconnect_headscale()
        
        if self.config.get('system.auto_reconnect', True):
            if self.tui.confirm("재시도하시겠습니까?"):
                return self.join_cluster()
        
        return False
    
    def reset_node(self):
        """노드 리셋"""
        self.tui.show_warning("노드를 리셋하면 클러스터에서 제거됩니다.")
        if not self.tui.confirm("정말로 노드를 리셋하시겠습니까?", default=False):
            return
        
        self.tui.show_progress("노드 리셋 중...")
        if self.cluster_manager.reset_node():
            self.tui.show_success("노드 리셋 완료")
        else:
            self.tui.show_error("노드 리셋 실패")
    
    def run(self):
        """메인 실행"""
        self.check_root()
        self.initialize()
        
        # 자동 모드: config.yaml로 바로 조인
        if self.auto_mode:
            self.tui.console.print("[bold cyan]클러스터 조인을 진행합니다...[/bold cyan]\n")
            self.tui.show_config_summary(self.config)
            success = self.join_cluster()
            if not success:
                self.handle_failure()
            return
        
        # 대화형 모드
        while True:
            choice = self.tui.show_menu()
            
            if choice == '1':
                # 새로운 설정으로 조인
                if self.run_interactive_setup():
                    success = self.join_cluster()
                    if not success:
                        self.handle_failure()
                    else:
                        break
            
            elif choice == '2':
                # 기존 설정으로 조인
                self.tui.show_config_summary(self.config)
                if self.tui.confirm("이 설정으로 진행하시겠습니까?"):
                    success = self.join_cluster()
                    if not success:
                        self.handle_failure()
                    else:
                        break
            
            elif choice == '3':
                # 설정 파일 생성/수정
                self.run_interactive_setup()
                self.tui.show_success("설정이 저장되었습니다.")
            
            elif choice == '4':
                # 노드 리셋
                self.reset_node()
            
            elif choice == '5':
                # 종료
                self.tui.console.print("[yellow]프로그램을 종료합니다.[/yellow]")
                break
            
            else:
                self.tui.show_warning("올바른 번호를 선택해주세요.")


def main():
    try:
        # 커맨드라인 인자 파싱
        parser = argparse.ArgumentParser(
            description='Kubernetes Worker Node Agent - 워커 노드 자동 조인 에이전트'
        )
        parser.add_argument(
            '--auto',
            action='store_true',
            help='자동 모드: config.yaml을 사용하여 자동으로 조인 (대화형 없음)'
        )
        args = parser.parse_args()
        
        agent = K8sWorkerAgent(auto_mode=args.auto)
        agent.run()
    except KeyboardInterrupt:
        print("\n\n프로그램이 중단되었습니다.")
        sys.exit(0)
    except Exception as e:
        print(f"\n예상치 못한 오류 발생: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

