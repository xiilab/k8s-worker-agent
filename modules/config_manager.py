"""
설정 관리 모듈
"""
import yaml
import shutil
from pathlib import Path
from datetime import datetime


class ConfigManager:
    def __init__(self, config_path="config.yaml"):
        self.config_path = Path(config_path)
        self.config = None
    
    def load_config(self):
        """설정 파일 로드"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        return self.config
    
    def save_config(self, config):
        """설정 파일 저장"""
        # 기존 설정 백업
        if self.config_path.exists() and config.get('system', {}).get('backup_config', True):
            self.backup_config()
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
        
        self.config = config
    
    def backup_config(self):
        """설정 파일 백업"""
        if not self.config_path.exists():
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.config_path.parent / f"{self.config_path.stem}.{timestamp}.backup"
        shutil.copy2(self.config_path, backup_path)
        return backup_path
    
    def get(self, key_path, default=None):
        """중첩된 키 경로로 값 가져오기 (예: 'master_node.api_server')"""
        if self.config is None:
            return default
        
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path, value):
        """중첩된 키 경로로 값 설정"""
        if self.config is None:
            self.config = {}
        
        keys = key_path.split('.')
        current = self.config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        current[keys[-1]] = value
    
    def create_default_config(self):
        """기본 설정 파일 생성"""
        default_config = {
            'master_node': {
                'api_server': '',
                'token': '',
                'ca_cert_hash': ''
            },
            'vpn': {
                'enabled': False,
                'headscale_url': '',
                'auth_key': '',
                'auto_detect': True
            },
            'worker_node': {
                'hostname_prefix': 'worker',
                'username': '',
                'labels': ['node-role.kubernetes.io/worker=worker']
            },
            'firewall': {
                'k8s_api_port': 6443,
                'kubelet_port': 10250,
                'nodeport_range': '30000-32767',
                'auto_configure': True
            },
            'system': {
                'log_file': '/var/log/k8s-agent.log',
                'auto_reconnect': True,
                'rollback_on_failure': True,
                'backup_config': True
            }
        }
        
        self.save_config(default_config)
        return default_config

