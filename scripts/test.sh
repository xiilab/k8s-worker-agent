#!/bin/bash
#
# K8s VPN Agent 테스트 스크립트
#

set -euo pipefail

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

echo "========================================"
echo " K8s VPN Agent 테스트"
echo "========================================"
echo ""

# Python venv 활성화
if [[ -d "venv" ]]; then
    source venv/bin/activate
else
    log_info "Python 가상환경이 없습니다. 먼저 install-agent.sh를 실행하세요."
    exit 1
fi

# 유닛 테스트
log_step "유닛 테스트 실행 중..."
if command -v pytest &> /dev/null; then
    pytest tests/ -v
else
    log_info "pytest가 설치되지 않았습니다. pip install pytest를 실행하세요."
fi

# 설정 파일 검증 테스트
log_step "설정 파일 검증 테스트..."
if [[ -f "config/config.yaml.sample" ]]; then
    k8s-vpn-agent validate --config config/config.yaml.sample || true
else
    echo -e "${YELLOW}샘플 설정 파일이 없습니다.${NC}"
fi

# CLI 도움말 테스트
log_step "CLI 도움말 테스트..."
k8s-vpn-agent --help

echo ""
echo "========================================"
echo " 테스트 완료!"
echo "========================================"

