"""
설정 관리 모듈 테스트
"""

import os
import tempfile
import pytest
from k8s_vpn_agent.config import Config


def test_default_config():
    """기본 설정 테스트"""
    config = Config()
    assert config.master.hostname == "k8s-master"
    assert config.vpn.enabled == True
    assert config.agent.idempotent == True


def test_config_load_yaml():
    """YAML 설정 파일 로드 테스트"""
    yaml_content = """
master:
  ip: "192.168.1.100"
  hostname: "test-master"

vpn:
  enabled: false
"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name
    
    try:
        config = Config(temp_path)
        assert config.master.ip == "192.168.1.100"
        assert config.master.hostname == "test-master"
        assert config.vpn.enabled == False
    finally:
        os.unlink(temp_path)


def test_config_save():
    """설정 저장 테스트"""
    config = Config()
    config.master.ip = "10.0.0.1"
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        temp_path = f.name
    
    try:
        config.save(temp_path)
        
        # 저장된 파일 다시 로드
        config2 = Config(temp_path)
        assert config2.master.ip == "10.0.0.1"
    finally:
        os.unlink(temp_path)


def test_config_to_dict():
    """딕셔너리 변환 테스트"""
    config = Config()
    data = config.to_dict()
    
    assert "master" in data
    assert "vpn" in data
    assert "agent" in data
    assert data["agent"]["idempotent"] == True

