"""
설정 관리 모듈
YAML/JSON 기반 설정 파일 관리 및 기본값 제공
"""

import os
import yaml
import json
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class MasterConfig:
    """마스터 노드 설정"""
    ip: str = ""
    hostname: str = "k8s-master"
    api_endpoint: str = ""
    token: str = ""
    ca_cert_hash: str = ""


@dataclass
class VPNConfig:
    """VPN 설정"""
    enabled: bool = True
    type: str = "headscale"
    headscale_url: str = ""
    auth_key: str = ""
    namespace: str = "default"


@dataclass
class WorkerConfig:
    """워커 노드 설정"""
    hostname: str = ""
    labels: list = field(default_factory=lambda: ["network=vpn", "zone=remote"])
    taints: list = field(default_factory=list)


@dataclass
class NetworkConfig:
    """네트워크 설정"""
    pod_cidr: str = "10.244.0.0/16"
    service_cidr: str = "10.96.0.0/12"
    dns_domain: str = "cluster.local"


@dataclass
class FirewallConfig:
    """방화벽 설정"""
    enabled: bool = True
    vpn_port: int = 41641  # Tailscale default
    k8s_api_port: int = 6443
    kubelet_port: int = 10250
    nodeport_range: str = "30000-32767"
    additional_ports: list = field(default_factory=list)


@dataclass
class AgentConfig:
    """에이전트 설정"""
    log_dir: str = "/var/log/k8s-vpn-agent"
    log_level: str = "INFO"
    health_check_interval: int = 30
    auto_reconnect: bool = True
    max_retry: int = 5
    rollback_on_failure: bool = True
    idempotent: bool = True


@dataclass
class RuntimeConfig:
    """컨테이너 런타임 설정"""
    type: str = "containerd"
    version: str = "latest"


class Config:
    """전체 설정 관리 클래스"""
    
    DEFAULT_CONFIG_PATHS = [
        "/etc/k8s-vpn-agent/config.yaml",
        "~/.k8s-vpn-agent/config.yaml",
        "./config/config.yaml",
        "./config.yaml",
    ]
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path
        self.master = MasterConfig()
        self.vpn = VPNConfig()
        self.worker = WorkerConfig()
        self.network = NetworkConfig()
        self.firewall = FirewallConfig()
        self.agent = AgentConfig()
        self.runtime = RuntimeConfig()
        
        if config_path:
            self.load(config_path)
        else:
            self._load_from_default_paths()
    
    def _load_from_default_paths(self):
        """기본 경로에서 설정 파일 로드"""
        for path in self.DEFAULT_CONFIG_PATHS:
            expanded_path = os.path.expanduser(path)
            if os.path.exists(expanded_path):
                self.load(expanded_path)
                return
    
    def load(self, path: str):
        """설정 파일 로드"""
        path = os.path.expanduser(path)
        if not os.path.exists(path):
            return
        
        with open(path, 'r', encoding='utf-8') as f:
            if path.endswith('.json'):
                data = json.load(f)
            else:
                data = yaml.safe_load(f) or {}
        
        self._update_from_dict(data)
        self.config_path = path
    
    def _update_from_dict(self, data: Dict[str, Any]):
        """딕셔너리에서 설정 업데이트"""
        if 'master' in data:
            for key, value in data['master'].items():
                if hasattr(self.master, key):
                    setattr(self.master, key, value)
        
        if 'vpn' in data:
            for key, value in data['vpn'].items():
                if hasattr(self.vpn, key):
                    setattr(self.vpn, key, value)
        
        if 'worker' in data:
            for key, value in data['worker'].items():
                if hasattr(self.worker, key):
                    setattr(self.worker, key, value)
        
        if 'network' in data:
            for key, value in data['network'].items():
                if hasattr(self.network, key):
                    setattr(self.network, key, value)
        
        if 'firewall' in data:
            for key, value in data['firewall'].items():
                if hasattr(self.firewall, key):
                    setattr(self.firewall, key, value)
        
        if 'agent' in data:
            for key, value in data['agent'].items():
                if hasattr(self.agent, key):
                    setattr(self.agent, key, value)
        
        if 'runtime' in data:
            for key, value in data['runtime'].items():
                if hasattr(self.runtime, key):
                    setattr(self.runtime, key, value)
    
    def save(self, path: Optional[str] = None):
        """설정 파일 저장"""
        save_path = path or self.config_path or self.DEFAULT_CONFIG_PATHS[0]
        save_path = os.path.expanduser(save_path)
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        data = {
            'master': asdict(self.master),
            'vpn': asdict(self.vpn),
            'worker': asdict(self.worker),
            'network': asdict(self.network),
            'firewall': asdict(self.firewall),
            'agent': asdict(self.agent),
            'runtime': asdict(self.runtime),
        }
        
        with open(save_path, 'w', encoding='utf-8') as f:
            if save_path.endswith('.json'):
                json.dump(data, f, indent=2)
            else:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'master': asdict(self.master),
            'vpn': asdict(self.vpn),
            'worker': asdict(self.worker),
            'network': asdict(self.network),
            'firewall': asdict(self.firewall),
            'agent': asdict(self.agent),
            'runtime': asdict(self.runtime),
        }
    
    def create_sample(self, output_path: str):
        """샘플 설정 파일 생성"""
        template = """# K8s VPN Agent Configuration File
# 이 파일을 복사하여 config.yaml로 사용하세요

# 마스터 노드 설정
master:
  ip: "10.0.1.100"  # 마스터 노드 IP (VPN 사용 시 VPN IP)
  hostname: "k8s-master"
  api_endpoint: "https://10.0.1.100:6443"
  token: ""  # kubeadm token (마스터에서 생성: kubeadm token create)
  ca_cert_hash: ""  # CA 인증서 해시 (sha256:xxxxx 형식)

# VPN 설정
vpn:
  enabled: true  # VPN 사용 여부 (false면 직접 통신)
  type: "headscale"  # headscale 또는 tailscale
  headscale_url: "https://headscale.example.com"
  auth_key: ""  # Headscale Pre-auth key
  namespace: "default"

# 워커 노드 설정
worker:
  hostname: ""  # 비워두면 자동 생성
  labels:
    - "network=vpn"
    - "zone=remote"
  taints: []  # 예: ["dedicated=special:NoSchedule"]

# 네트워크 설정
network:
  pod_cidr: "10.244.0.0/16"
  service_cidr: "10.96.0.0/12"
  dns_domain: "cluster.local"

# 방화벽 설정
firewall:
  enabled: true
  vpn_port: 41641  # Tailscale/Headscale
  k8s_api_port: 6443
  kubelet_port: 10250
  nodeport_range: "30000-32767"
  additional_ports: []

# 에이전트 설정
agent:
  log_dir: "/var/log/k8s-vpn-agent"
  log_level: "INFO"  # DEBUG, INFO, WARN, ERROR
  health_check_interval: 30
  auto_reconnect: true
  max_retry: 5
  rollback_on_failure: true
  idempotent: true

# 컨테이너 런타임
runtime:
  type: "containerd"
  version: "latest"
"""
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(template)

