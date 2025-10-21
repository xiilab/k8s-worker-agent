"""
네트워크 체커 모듈 테스트
"""

import pytest
from k8s_vpn_agent.network import NetworkChecker


def test_check_dns():
    """DNS 체크 테스트"""
    checker = NetworkChecker()
    success, msg = checker.check_dns("google.com")
    assert success == True
    assert "DNS" in msg


def test_check_ping_localhost():
    """로컬호스트 핑 테스트"""
    checker = NetworkChecker()
    success, msg = checker.check_ping("127.0.0.1", count=1)
    assert success == True


def test_check_port_invalid():
    """잘못된 포트 테스트"""
    checker = NetworkChecker()
    success, msg = checker.check_port("127.0.0.1", 99999, timeout=1)
    assert success == False

