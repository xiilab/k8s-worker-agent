#!/bin/bash
#
# K8s VPN Agent 설치 스크립트
#

set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Root 권한 확인
if [[ $EUID -ne 0 ]]; then
   echo "이 스크립트는 root 권한으로 실행해야 합니다."
   exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo " K8s VPN Agent 설치"
echo "========================================"
echo ""

# Python venv 생성
log_step "Python 가상환경 생성 중..."
if [[ ! -d "venv" ]]; then
    python3 -m venv venv
fi

# 패키지 설치
log_step "Python 패키지 설치 중..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

# 샘플 설정 파일 생성
log_step "샘플 설정 파일 생성 중..."
venv/bin/k8s-vpn-agent init /root/k8s-vpn-agent/config/config.yaml.sample

# 스크립트 실행 권한 추가
log_step "스크립트 실행 권한 추가 중..."
chmod +x scripts/*.sh

# 로그 디렉토리 생성
log_step "로그 디렉토리 생성 중..."
mkdir -p /var/log/k8s-vpn-agent

echo ""
echo "========================================"
echo " 설치 완료!"
echo "========================================"
echo ""
log_info "다음 단계:"
log_info "1. 설정 파일을 편집하세요:"
log_info "   cp config/config.yaml.sample config/config.yaml"
log_info "   vi config/config.yaml"
log_info ""
log_info "2. 에이전트를 실행하세요:"
log_info "   source venv/bin/activate"
log_info "   k8s-vpn-agent join --config config/config.yaml"
log_info ""
log_info "또는 대화형 모드로 실행:"
log_info "   k8s-vpn-agent join --interactive"

