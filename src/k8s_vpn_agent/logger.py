"""
로깅 시스템
파일 및 콘솔 로깅, 디버그 모드 지원
"""

import logging
import os
from datetime import datetime
from typing import Optional
from rich.logging import RichHandler
from rich.console import Console

console = Console()


class AgentLogger:
    """에이전트 로거"""
    
    def __init__(self, log_dir: str = "/var/log/k8s-vpn-agent", log_level: str = "INFO", debug: bool = False):
        self.log_dir = log_dir
        self.log_level = logging.DEBUG if debug else getattr(logging, log_level.upper())
        self.debug_mode = debug
        
        # 로그 디렉토리 생성
        os.makedirs(log_dir, exist_ok=True)
        
        # 로그 파일 경로
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"agent_{timestamp}.log")
        self.error_file = os.path.join(log_dir, f"error_{timestamp}.log")
        
        # 로거 설정
        self.logger = logging.getLogger("k8s_vpn_agent")
        self.logger.setLevel(self.log_level)
        
        # 기존 핸들러 제거
        self.logger.handlers.clear()
        
        # 파일 핸들러
        file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
        file_handler.setLevel(self.log_level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        self.logger.addHandler(file_handler)
        
        # 에러 파일 핸들러
        error_handler = logging.FileHandler(self.error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        self.logger.addHandler(error_handler)
        
        # 콘솔 핸들러 (Rich)
        rich_handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_time=False,
            show_path=debug
        )
        rich_handler.setLevel(self.log_level)
        self.logger.addHandler(rich_handler)
    
    def debug(self, message: str):
        """디버그 로그"""
        self.logger.debug(message)
    
    def info(self, message: str):
        """정보 로그"""
        self.logger.info(message)
    
    def warning(self, message: str):
        """경고 로그"""
        self.logger.warning(message)
    
    def error(self, message: str):
        """에러 로그"""
        self.logger.error(message)
    
    def critical(self, message: str):
        """치명적 에러 로그"""
        self.logger.critical(message)
    
    def exception(self, message: str):
        """예외 로그 (트레이스백 포함)"""
        self.logger.exception(message)
    
    def get_log_files(self) -> dict:
        """로그 파일 경로 반환"""
        return {
            "main_log": self.log_file,
            "error_log": self.error_file,
            "log_dir": self.log_dir
        }


# 글로벌 로거 인스턴스
_logger: Optional[AgentLogger] = None


def get_logger(log_dir: str = "/var/log/k8s-vpn-agent", 
               log_level: str = "INFO", 
               debug: bool = False) -> AgentLogger:
    """로거 인스턴스 가져오기"""
    global _logger
    if _logger is None:
        _logger = AgentLogger(log_dir, log_level, debug)
    return _logger


def init_logger(log_dir: str, log_level: str, debug: bool) -> AgentLogger:
    """로거 초기화"""
    global _logger
    _logger = AgentLogger(log_dir, log_level, debug)
    return _logger

