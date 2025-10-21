"""
K8s VPN Agent
서로 다른 네트워크망에 있는 워커노드를 VPN을 통해 K8s 클러스터에 추가하는 에이전트

Features:
- Headscale/Tailscale 기반 VPN 연결
- 자동 패키지 설치 및 환경 설정
- idempotent 및 롤백 지원
- 자동 매뉴얼 생성
- 상태 모니터링 및 헬스체크
"""

__version__ = "1.0.0"
__author__ = "DevOps Team"

