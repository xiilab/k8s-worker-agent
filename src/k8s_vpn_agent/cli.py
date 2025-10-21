"""
CLI 메인 인터페이스
Click 및 Rich 기반 사용자 친화적 CLI
"""

import os
import sys
import click
from typing import Dict
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from .config import Config
from .logger import init_logger, get_logger
from .network import NetworkChecker
from .vpn import VPNManager
from .k8s import K8sManager
from .firewall import FirewallManager
from .monitor import HealthChecker, NodeMonitor, generate_health_summary
from .doc_generator import DocGenerator

console = Console()


class AgentOrchestrator:
    """에이전트 오케스트레이터"""
    
    def __init__(self, config: Config, debug: bool = False):
        self.config = config
        self.debug = debug
        self.logger = get_logger()
        self.network_checker = NetworkChecker(debug)
        self.vpn_manager = None
        self.k8s_manager = None
        self.firewall_manager = None
        self.execution_log = []
    
    def log_step(self, step: str, status: str, message: str = ""):
        """실행 단계 로깅"""
        self.execution_log.append({
            "step": step,
            "status": status,
            "message": message
        })
    
    def show_summary(self):
        """실행 결과 요약 표시"""
        console.print("\n" + "="*60)
        console.print("[bold]실행 결과 요약[/bold]")
        console.print("="*60 + "\n")
        
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("단계", style="cyan", width=30)
        table.add_column("상태", width=10)
        table.add_column("메시지", width=18)
        
        for log in self.execution_log:
            status_icon = "✓" if log["status"] == "success" else "✗"
            status_color = "green" if log["status"] == "success" else "red"
            table.add_row(
                log["step"],
                f"[{status_color}]{status_icon}[/{status_color}]",
                log["message"][:18] if log["message"] else ""
            )
        
        console.print(table)
        
        # 로그 파일 위치 표시
        log_files = self.logger.get_log_files()
        console.print(f"\n[bold]로그 파일:[/bold]")
        console.print(f"  Main: {log_files['main_log']}")
        console.print(f"  Error: {log_files['error_log']}")
    
    def rollback_all(self):
        """전체 롤백"""
        console.print("\n[bold yellow]오류 발생! 롤백을 시작합니다...[/bold yellow]\n")
        self.logger.error("Error occurred, starting rollback...")
        
        if self.k8s_manager:
            self.k8s_manager.rollback()
        
        if self.vpn_manager:
            self.vpn_manager.rollback()
        
        if self.firewall_manager:
            self.firewall_manager.rollback()
        
        console.print("\n[yellow]롤백 완료[/yellow]")
        self.logger.info("Rollback completed")
    
    def run(self) -> bool:
        """메인 실행 로직"""
        try:
            # 1. 초기 네트워크 체크
            console.print(Panel.fit(
                "[bold cyan]K8s VPN Worker Node Agent[/bold cyan]\n"
                "서로 다른 네트워크망의 워커노드를 클러스터에 추가합니다.",
                border_style="cyan"
            ))
            
            self.logger.info("=== Agent execution started ===")
            
            # 마스터 노드와의 직접 연결 확인
            master_ip = self.config.master.ip
            network_result = self.network_checker.comprehensive_check(master_ip)
            
            # 2. VPN 설정 (필요시)
            if self.config.vpn.enabled and not network_result["overall"]:
                console.print("\n[yellow]마스터 노드와 직접 통신이 불가능합니다. VPN을 설정합니다.[/yellow]")
                self.logger.info("Direct communication failed, setting up VPN...")
                
                self.vpn_manager = VPNManager(self.config.to_dict()["vpn"], self.debug)
                success, msg = self.vpn_manager.connect()
                self.log_step("VPN 연결", "success" if success else "failed", msg)
                
                if not success:
                    self.logger.error(f"VPN connection failed: {msg}")
                    if self.config.agent.rollback_on_failure:
                        self.rollback_all()
                    return False
                
                # VPN 연결 후 재확인
                vpn_ip = self.vpn_manager.get_vpn_ip()
                if vpn_ip:
                    master_ip = vpn_ip.rsplit('.', 1)[0] + '.1'  # VPN 네트워크의 마스터 IP 추정
                    network_result = self.network_checker.comprehensive_check(master_ip, "tailscale0")
                    
                    if not network_result["overall"]:
                        self.logger.error("Network check failed after VPN connection")
                        if self.config.agent.rollback_on_failure:
                            self.rollback_all()
                        return False
                
                self.vpn_manager.enable_autostart()
            
            elif not self.config.vpn.enabled:
                console.print("\n[cyan]VPN이 비활성화되어 있습니다. 직접 통신을 사용합니다.[/cyan]")
                self.logger.info("VPN disabled, using direct communication")
                self.log_step("VPN 설정", "success", "건너뜀")
            
            else:
                console.print("\n[green]마스터 노드와 직접 통신이 가능합니다. VPN을 건너뜁니다.[/green]")
                self.logger.info("Direct communication available, skipping VPN")
                self.log_step("VPN 설정", "success", "건너뜀")
            
            # 3. 방화벽 설정
            self.firewall_manager = FirewallManager(self.config.to_dict()["firewall"], self.debug)
            success, msg = self.firewall_manager.configure()
            self.log_step("방화벽 설정", "success" if success else "failed", msg)
            
            if not success and self.config.agent.rollback_on_failure:
                self.rollback_all()
                return False
            
            # 4. K8s 조인
            self.k8s_manager = K8sManager(self.config.to_dict(), self.debug)
            
            # 의존성 확인
            deps_ok, missing = self.k8s_manager.check_dependencies()
            if not deps_ok:
                self.logger.error(f"Missing dependencies: {missing}")
                self.log_step("의존성 확인", "failed", f"누락: {', '.join(missing)}")
                if self.config.agent.rollback_on_failure:
                    self.rollback_all()
                return False
            
            self.log_step("의존성 확인", "success", "완료")
            
            # 호스트명 설정
            success, hostname = self.k8s_manager.setup_hostname()
            if not success:
                self.logger.error(f"Hostname setup failed: {hostname}")
                if self.config.agent.rollback_on_failure:
                    self.rollback_all()
                return False
            
            self.log_step("호스트명 설정", "success", hostname)
            
            # Kubelet 설정
            node_ip = self.vpn_manager.get_vpn_ip() if self.vpn_manager else None
            self.k8s_manager.configure_kubelet(node_ip)
            self.log_step("Kubelet 설정", "success", "완료")
            
            # 클러스터 조인
            success, msg = self.k8s_manager.join_cluster()
            self.log_step("클러스터 조인", "success" if success else "failed", msg)
            
            if not success:
                self.logger.error(f"Cluster join failed: {msg}")
                if self.config.agent.rollback_on_failure:
                    self.rollback_all()
                return False
            
            # 노드 상태 확인
            status = self.k8s_manager.verify_node_status()
            self.log_step("노드 상태 확인", "success", "완료")
            
            # 성공
            self.logger.info("=== Agent execution completed successfully ===")
            self.show_summary()
            
            console.print("\n" + "="*60)
            console.print("[bold green]✓ 워커노드 추가 완료![/bold green]")
            console.print("="*60)
            
            return True
        
        except KeyboardInterrupt:
            console.print("\n[yellow]사용자에 의해 중단되었습니다.[/yellow]")
            self.logger.warning("Execution interrupted by user")
            if self.config.agent.rollback_on_failure:
                self.rollback_all()
            return False
        
        except Exception as e:
            console.print(f"\n[red]예상치 못한 오류 발생: {str(e)}[/red]")
            self.logger.exception("Unexpected error occurred")
            if self.config.agent.rollback_on_failure:
                self.rollback_all()
            return False


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """K8s VPN Worker Node Agent
    
    서로 다른 네트워크망에 있는 워커노드를 VPN을 통해 K8s 클러스터에 추가합니다.
    """
    pass


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='설정 파일 경로')
@click.option('--debug', is_flag=True, help='디버그 모드')
@click.option('--interactive', '-i', is_flag=True, help='대화형 모드')
def join(config, debug, interactive):
    """워커노드를 클러스터에 추가"""
    
    # 설정 로드
    cfg = Config(config)
    
    # 로거 초기화
    init_logger(cfg.agent.log_dir, cfg.agent.log_level, debug)
    logger = get_logger()
    
    logger.info(f"Starting join command (debug={debug}, interactive={interactive})")
    
    # 대화형 모드
    if interactive:
        console.print("\n[bold cyan]대화형 설정[/bold cyan]\n")
        
        # 마스터 노드 정보
        cfg.master.ip = Prompt.ask("마스터 노드 IP", default=cfg.master.ip or "")
        cfg.master.api_endpoint = Prompt.ask("API 엔드포인트", default=cfg.master.api_endpoint or f"https://{cfg.master.ip}:6443")
        cfg.master.token = Prompt.ask("Kubeadm 토큰", default=cfg.master.token or "")
        cfg.master.ca_cert_hash = Prompt.ask("CA 인증서 해시", default=cfg.master.ca_cert_hash or "")
        
        # VPN 설정
        cfg.vpn.enabled = Confirm.ask("VPN을 사용하시겠습니까?", default=cfg.vpn.enabled)
        
        if cfg.vpn.enabled:
            cfg.vpn.headscale_url = Prompt.ask("Headscale URL", default=cfg.vpn.headscale_url or "")
            cfg.vpn.auth_key = Prompt.ask("Auth Key (선택사항)", default=cfg.vpn.auth_key or "")
    
    # 필수 정보 확인
    if not cfg.master.ip or not cfg.master.token or not cfg.master.ca_cert_hash:
        console.print("[red]오류: 마스터 노드 정보가 불완전합니다.[/red]")
        console.print("[yellow]--interactive 옵션을 사용하거나 설정 파일을 제공하세요.[/yellow]")
        sys.exit(1)
    
    # 실행
    orchestrator = AgentOrchestrator(cfg, debug)
    success = orchestrator.run()
    
    sys.exit(0 if success else 1)


@cli.command()
@click.argument('output', type=click.Path(), default='./config.yaml')
def init(output):
    """샘플 설정 파일 생성"""
    cfg = Config()
    cfg.create_sample(output)
    console.print(f"[green]✓ 샘플 설정 파일 생성: {output}[/green]")
    console.print(f"[cyan]설정 파일을 편집한 후 다음 명령어로 실행하세요:[/cyan]")
    console.print(f"[cyan]  k8s-vpn-agent join --config {output}[/cyan]")


@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='설정 파일 경로')
def validate(config):
    """설정 파일 유효성 검사"""
    try:
        cfg = Config(config)
        console.print("[green]✓ 설정 파일이 유효합니다.[/green]")
        
        # 설정 내용 표시
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("항목", style="cyan")
        table.add_column("값")
        
        table.add_row("마스터 IP", cfg.master.ip or "[red]미설정[/red]")
        table.add_row("API 엔드포인트", cfg.master.api_endpoint or "[red]미설정[/red]")
        table.add_row("VPN 활성화", "예" if cfg.vpn.enabled else "아니오")
        table.add_row("방화벽 활성화", "예" if cfg.firewall.enabled else "아니오")
        table.add_row("롤백 활성화", "예" if cfg.agent.rollback_on_failure else "아니오")
        
        console.print(table)
    
    except Exception as e:
        console.print(f"[red]✗ 설정 파일 오류: {str(e)}[/red]")
        sys.exit(1)


@cli.command()
@click.option("-c", "--config", "config_path", type=click.Path(exists=True),
              help="설정 파일 경로")
@click.option("--save-report", is_flag=True, help="리포트를 파일로 저장")
def health(config_path, save_report):
    """시스템 헬스체크 수행"""
    console.print("[bold cyan]K8s VPN Agent - 헬스체크[/bold cyan]\n")
    
    # 설정 로드
    if config_path:
        config_obj = Config.from_yaml(config_path)
        config_dict = {
            "master": {"ip": config_obj.master.ip},
            "vpn": {"enabled": config_obj.vpn.enabled},
        }
    else:
        console.print("[yellow]경고: 설정 파일이 제공되지 않았습니다. 기본값 사용[/yellow]")
        config_dict = {}
    
    # 헬스체크 수행
    checker = HealthChecker(config_dict)
    
    with console.status("[bold green]헬스체크 수행 중...[/bold green]"):
        results = checker.check_all()
    
    # 결과 출력
    status_color = "green" if results["overall_status"] == "healthy" else "red"
    console.print(f"\n[bold {status_color}]전체 상태: {results['overall_status'].upper()}[/bold {status_color}]\n")
    
    # 개별 체크 결과
    table = Table(title="헬스체크 상세 결과")
    table.add_column("항목", style="cyan")
    table.add_column("상태", style="magenta")
    table.add_column("메시지", style="white")
    
    for check_name, check_result in results["checks"].items():
        status_icon = "✅" if check_result.get("healthy") else "❌"
        status_text = f"{status_icon} {check_result.get('status', 'unknown')}"
        message = check_result.get("message", "")
        
        table.add_row(
            check_name.upper(),
            status_text,
            message
        )
    
    console.print(table)
    
    # 리포트 저장
    if save_report:
        report_file = checker.save_health_report(results)
        console.print(f"\n[green]✅ 리포트 저장: {report_file}[/green]")
    
    # 종료 코드
    sys.exit(0 if results["overall_status"] == "healthy" else 1)


@cli.command()
@click.option("-c", "--config", "config_path", type=click.Path(exists=True),
              required=True, help="설정 파일 경로")
@click.option("--interval", type=int, default=60,
              help="모니터링 간격 (초, 기본값: 60)")
@click.option("--duration", type=int, default=None,
              help="모니터링 지속 시간 (초, 기본값: 무한)")
def monitor(config_path, interval, duration):
    """시스템을 지속적으로 모니터링"""
    console.print("[bold cyan]K8s VPN Agent - 모니터링 시작[/bold cyan]\n")
    
    # 설정 로드
    config_obj = Config.from_yaml(config_path)
    config_dict = {
        "master": {"ip": config_obj.master.ip},
        "vpn": {"enabled": config_obj.vpn.enabled},
    }
    
    # 모니터 시작
    monitor_obj = NodeMonitor(config_dict, interval=interval)
    
    console.print(f"[green]모니터링 간격: {interval}초[/green]")
    if duration:
        console.print(f"[green]모니터링 지속 시간: {duration}초[/green]")
    else:
        console.print("[green]모니터링 지속 시간: 무한 (Ctrl+C로 중지)[/green]")
    
    console.print("\n[yellow]모니터링 시작...[/yellow]\n")
    
    try:
        monitor_obj.start_monitoring(duration=duration)
    except KeyboardInterrupt:
        console.print("\n[yellow]모니터링 중지[/yellow]")
    
    console.print("[green]모니터링 종료[/green]")


@cli.command()
@click.option("--log-dir", type=click.Path(exists=True),
              default="/var/log/k8s-vpn-agent",
              help="로그 디렉토리 경로")
def health_summary(log_dir):
    """헬스체크 요약 보기"""
    console.print("[bold cyan]K8s VPN Agent - 헬스체크 요약[/bold cyan]\n")
    
    summary = generate_health_summary(log_dir)
    
    if summary.get("status") == "no_reports":
        console.print("[yellow]헬스 리포트가 없습니다.[/yellow]")
        return
    
    if summary.get("status") == "error":
        console.print(f"[red]오류: {summary.get('message')}[/red]")
        return
    
    # 요약 정보 출력
    table = Table(title="헬스체크 요약")
    table.add_column("항목", style="cyan")
    table.add_column("값", style="white")
    
    table.add_row("최근 체크 시간", summary["latest_check"])
    table.add_row("최근 상태", summary["latest_status"])
    table.add_row("총 체크 횟수", str(summary["total_checks"]))
    table.add_row("정상 체크", str(summary["healthy_checks"]))
    table.add_row("비정상 체크", str(summary["unhealthy_checks"]))
    table.add_row("정상률", f"{summary['health_rate']}%")
    
    console.print(table)
    
    if summary.get("warning"):
        console.print(f"\n[yellow]⚠️  {summary['warning']}[/yellow]")


@cli.command()
@click.option("-l", "--log-file", "log_file", type=click.Path(exists=True),
              required=True, help="분석할 로그 파일")
@click.option("-o", "--output-dir", "output_dir",
              default="./docs/generated",
              help="출력 디렉토리 (기본값: ./docs/generated)")
def generate_docs(log_file, output_dir):
    """로그 파일 기반으로 문서 자동 생성"""
    console.print("[bold cyan]K8s VPN Agent - 문서 자동 생성[/bold cyan]\n")
    
    console.print(f"[yellow]로그 파일: {log_file}[/yellow]")
    console.print(f"[yellow]출력 디렉토리: {output_dir}[/yellow]\n")
    
    try:
        generator = DocGenerator(log_file, output_dir)
        
        with console.status("[bold green]문서 생성 중...[/bold green]"):
            generated_files = generator.generate_all()
        
        # 결과 출력
        console.print("\n[bold green]✅ 문서 생성 완료![/bold green]\n")
        
        table = Table(title="생성된 파일")
        table.add_column("유형", style="cyan")
        table.add_column("파일 경로", style="white")
        
        for doc_type, file_path in generated_files.items():
            table.add_row(doc_type.upper(), str(file_path))
        
        console.print(table)
        
        console.print("\n[green]생성된 문서를 확인하세요:[/green]")
        console.print(f"  • 실행 매뉴얼: {generated_files['manual']}")
        console.print(f"  • 재실행 스크립트: {generated_files['script']}")
        console.print(f"  • 트러블슈팅 가이드: {generated_files['troubleshooting']}")
        
    except FileNotFoundError as e:
        console.print(f"[red]❌ 오류: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]❌ 문서 생성 실패: {e}[/red]")
        sys.exit(1)


def main():
    """메인 엔트리 포인트"""
    cli()


if __name__ == '__main__':
    main()

