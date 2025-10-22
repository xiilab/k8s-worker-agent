"""
TUI (Text User Interface) 모듈
"""
from prompt_toolkit import prompt
from prompt_toolkit.validation import Validator, ValidationError
from prompt_toolkit.completion import WordCompleter
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm


class IPValidator(Validator):
    """IP 주소 검증"""
    def validate(self, document):
        text = document.text
        if not text:
            return
        
        # IP:PORT 형식 확인
        if ':' in text:
            ip_part, port_part = text.rsplit(':', 1)
            try:
                port = int(port_part)
                if not (1 <= port <= 65535):
                    raise ValidationError(message="포트는 1-65535 범위여야 합니다")
            except ValueError:
                raise ValidationError(message="올바른 포트 번호를 입력하세요")
        else:
            ip_part = text
        
        # IP 형식 간단 확인
        parts = ip_part.split('.')
        if len(parts) != 4:
            raise ValidationError(message="올바른 IP 주소 형식이 아닙니다 (예: 192.168.1.100:6443)")


class TokenValidator(Validator):
    """Kubeadm 토큰 검증"""
    def validate(self, document):
        text = document.text
        if not text:
            raise ValidationError(message="토큰을 입력해주세요")
        
        # 기본 형식 확인 (abcdef.0123456789abcdef)
        if '.' not in text:
            raise ValidationError(message="토큰 형식이 올바르지 않습니다 (예: abcdef.0123456789abcdef)")


class HashValidator(Validator):
    """CA 인증서 해시 검증"""
    def validate(self, document):
        text = document.text
        if not text:
            raise ValidationError(message="CA 해시를 입력해주세요")
        
        if not text.startswith('sha256:'):
            raise ValidationError(message="CA 해시는 'sha256:'으로 시작해야 합니다")


class TUI:
    def __init__(self):
        self.console = Console()
    
    def show_welcome(self):
        """환영 메시지 출력"""
        welcome_text = """
[bold cyan]Kubernetes Worker Node Agent[/bold cyan]
[yellow]버전 1.0.0[/yellow]

이 에이전트는 Kubernetes 클러스터에 워커 노드를 자동으로 추가합니다.
        """
        self.console.print(Panel(welcome_text, border_style="cyan"))
    
    def show_menu(self):
        """메인 메뉴 표시"""
        table = Table(title="메인 메뉴", show_header=True, header_style="bold magenta")
        table.add_column("번호", style="cyan", width=6)
        table.add_column("작업", style="green")
        
        table.add_row("1", "새로운 설정으로 클러스터 조인")
        table.add_row("2", "기존 설정 파일로 조인")
        table.add_row("3", "설정 파일 생성/수정")
        table.add_row("4", "노드 리셋 (클러스터에서 제거)")
        table.add_row("5", "종료")
        
        self.console.print(table)
        
        choice = prompt("선택: ", validator=None)
        return choice
    
    def get_master_config(self, default_api_server="", default_token="", default_hash=""):
        """마스터 노드 설정 입력"""
        self.console.print("\n[bold]1. 마스터 노드 정보[/bold]", style="cyan")
        
        api_server = prompt(
            "마스터 노드 API 서버 (IP:PORT): ",
            default=default_api_server,
            validator=IPValidator()
        )
        
        token = prompt(
            "Kubeadm 토큰: ",
            default=default_token,
            validator=TokenValidator()
        )
        
        ca_cert_hash = prompt(
            "CA 인증서 해시: ",
            default=default_hash,
            validator=HashValidator()
        )
        
        return {
            'api_server': api_server,
            'token': token,
            'ca_cert_hash': ca_cert_hash
        }
    
    def get_vpn_config(self, auto_detect=True):
        """VPN 설정 입력"""
        self.console.print("\n[bold]2. VPN 설정[/bold]", style="cyan")
        
        if auto_detect:
            use_auto = Confirm.ask("마스터 노드 연결 테스트 후 자동으로 VPN 사용 여부 결정", default=True)
            if use_auto:
                return {
                    'enabled': False,  # 일단 False로 시작, 자동 감지 후 결정
                    'auto_detect': True,
                    'headscale_url': '',
                    'auth_key': ''
                }
        
        use_vpn = Confirm.ask("VPN(Headscale) 사용", default=False)
        
        if use_vpn:
            headscale_url = prompt("Headscale 서버 URL: ")
            auth_key = prompt("Headscale 인증 키: ")
            
            return {
                'enabled': True,
                'auto_detect': False,
                'headscale_url': headscale_url,
                'auth_key': auth_key
            }
        else:
            return {
                'enabled': False,
                'auto_detect': False,
                'headscale_url': '',
                'auth_key': ''
            }
    
    def get_worker_config(self, default_prefix="worker", default_username=""):
        """워커 노드 설정 입력"""
        self.console.print("\n[bold]3. 워커 노드 설정[/bold]", style="cyan")
        
        hostname_prefix = prompt(
            "호스트명 접두사: ",
            default=default_prefix
        )
        
        username = prompt(
            "노드 추가 사용자 이름 (레이블로 사용): ",
            default=default_username
        )
        
        # 추가 레이블
        add_more_labels = Confirm.ask("추가 레이블을 입력하시겠습니까?", default=False)
        labels = [f"node-role.kubernetes.io/worker=worker", f"added-by={username}"]
        
        if add_more_labels:
            self.console.print("레이블 형식: key=value (종료하려면 빈 줄 입력)")
            while True:
                label = prompt("레이블: ")
                if not label:
                    break
                labels.append(label)
        
        return {
            'hostname_prefix': hostname_prefix,
            'username': username,
            'labels': labels
        }
    
    def get_firewall_config(self):
        """방화벽 설정 입력"""
        self.console.print("\n[bold]4. 방화벽 설정[/bold]", style="cyan")
        
        auto_configure = Confirm.ask("자동으로 방화벽 설정", default=True)
        
        if auto_configure:
            return {
                'auto_configure': True,
                'k8s_api_port': 6443,
                'kubelet_port': 10250,
                'nodeport_range': '30000-32767'
            }
        else:
            return {
                'auto_configure': False,
                'k8s_api_port': 6443,
                'kubelet_port': 10250,
                'nodeport_range': '30000-32767'
            }
    
    def get_system_config(self):
        """시스템 설정 입력"""
        self.console.print("\n[bold]5. 시스템 설정[/bold]", style="cyan")
        
        log_file = prompt(
            "로그 파일 경로: ",
            default="/var/log/k8s-agent.log"
        )
        
        auto_reconnect = Confirm.ask("실패 시 자동 재연결", default=True)
        rollback_on_failure = Confirm.ask("실패 시 자동 롤백", default=True)
        backup_config = Confirm.ask("설정 파일 백업", default=True)
        
        return {
            'log_file': log_file,
            'auto_reconnect': auto_reconnect,
            'rollback_on_failure': rollback_on_failure,
            'backup_config': backup_config
        }
    
    def show_config_summary(self, config):
        """설정 요약 표시"""
        self.console.print("\n[bold]설정 요약[/bold]", style="cyan")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("항목", style="cyan", width=30)
        table.add_column("값", style="green")
        
        # 마스터 노드
        table.add_row("마스터 API 서버", config['master_node']['api_server'])
        table.add_row("토큰", config['master_node']['token'][:20] + "...")
        
        # VPN
        vpn_status = "자동 감지" if config['vpn']['auto_detect'] else ("사용" if config['vpn']['enabled'] else "사용 안 함")
        table.add_row("VPN", vpn_status)
        
        # 워커 노드
        table.add_row("호스트명 접두사", config['worker_node']['hostname_prefix'])
        table.add_row("사용자 이름", config['worker_node']['username'])
        
        # 방화벽
        fw_status = "자동 설정" if config['firewall']['auto_configure'] else "수동"
        table.add_row("방화벽", fw_status)
        
        # 시스템
        table.add_row("자동 롤백", "예" if config['system']['rollback_on_failure'] else "아니오")
        
        self.console.print(table)
    
    def show_progress(self, message, style="cyan"):
        """진행 상황 표시"""
        self.console.print(f"[{style}]→ {message}[/{style}]")
    
    def show_success(self, message):
        """성공 메시지"""
        self.console.print(f"[bold green]✓ {message}[/bold green]")
    
    def show_error(self, message):
        """에러 메시지"""
        self.console.print(f"[bold red]✗ {message}[/bold red]")
    
    def show_warning(self, message):
        """경고 메시지"""
        self.console.print(f"[bold yellow]⚠ {message}[/bold yellow]")
    
    def confirm(self, message, default=True):
        """확인 프롬프트"""
        return Confirm.ask(message, default=default)

