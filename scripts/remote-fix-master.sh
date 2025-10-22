#!/bin/bash
#
# 워커 노드에서 마스터 노드의 ConfigMap을 원격으로 수정하는 스크립트
# SSH를 통해 마스터에 접속하여 fix 스크립트를 실행합니다
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 설정 (quick-setup.sh와 동일)
MASTER_IP="10.61.3.12"
MASTER_USER="${MASTER_USER:-root}"  # 환경변수로 변경 가능
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔧 원격 마스터 노드 ConfigMap 수정${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}마스터 노드: ${GREEN}$MASTER_USER@$MASTER_IP${NC}"
echo ""

# SSH 접속 테스트
echo -e "${BLUE}1️⃣  SSH 연결 테스트...${NC}"
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $MASTER_USER@$MASTER_IP "echo 'SSH OK'" &> /dev/null; then
    echo -e "${RED}✗ SSH 연결 실패${NC}"
    echo ""
    echo -e "${YELLOW}다음을 확인하세요:${NC}"
    echo "  1. 마스터 노드 IP가 올바른지: $MASTER_IP"
    echo "  2. SSH 키가 설정되어 있는지:"
    echo "     ${GREEN}ssh-copy-id $MASTER_USER@$MASTER_IP${NC}"
    echo "  3. 또는 비밀번호로 접속:"
    echo "     ${GREEN}MASTER_USER=$MASTER_USER ssh $MASTER_IP${NC}"
    echo ""
    echo -e "${YELLOW}또는 마스터 노드에서 직접 실행하세요:${NC}"
    echo "  scp scripts/fix-master-config.sh $MASTER_USER@$MASTER_IP:/tmp/"
    echo "  ssh $MASTER_USER@$MASTER_IP"
    echo "  sudo /tmp/fix-master-config.sh"
    exit 1
fi

echo -e "${GREEN}✓ SSH 연결 성공${NC}"
echo ""

# 원격 스크립트 전송 및 실행
echo -e "${BLUE}2️⃣  마스터 노드로 스크립트 전송 중...${NC}"

# 임시 스크립트 생성 (진단만 수행)
REMOTE_SCRIPT=$(cat <<'EOF'
#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}마스터 노드에서 실행 중...${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# kubectl 확인
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}✗ kubectl이 설치되지 않았습니다.${NC}"
    exit 1
fi

# ConfigMap 확인
if ! kubectl get cm kubeadm-config -n kube-system &> /dev/null; then
    echo -e "${RED}✗ kubeadm-config ConfigMap을 찾을 수 없습니다.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ kubectl 및 ConfigMap 확인 완료${NC}"
echo ""

# ClusterConfiguration 추출
CLUSTER_CONFIG=$(kubectl get cm kubeadm-config -n kube-system -o jsonpath='{.data.ClusterConfiguration}')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "현재 apiServer.extraArgs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$CLUSTER_CONFIG" | grep -A 10 "extraArgs:" || echo "extraArgs를 찾을 수 없습니다"
echo ""

# 배열 형식 확인
if echo "$CLUSTER_CONFIG" | grep -q "extraArgs:" && echo "$CLUSTER_CONFIG" | grep -A 5 "extraArgs:" | grep -q "^[[:space:]]*-[[:space:]]*"; then
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ 문제 발견: extraArgs가 배열 형식입니다!${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}수동으로 수정이 필요합니다:${NC}"
    echo "  kubectl edit cm kubeadm-config -n kube-system"
    echo ""
    echo -e "${RED}변경 전:${NC}"
    echo "  extraArgs:"
    echo "    - arg1=value1"
    echo ""
    echo -e "${GREEN}변경 후:${NC}"
    echo "  extraArgs:"
    echo "    arg1: value1"
    echo ""
    exit 1
else
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ extraArgs가 올바른 형식입니다!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
fi
EOF
)

# SSH로 원격 실행
echo "$REMOTE_SCRIPT" | ssh $MASTER_USER@$MASTER_IP "sudo bash -s"

SSH_EXIT_CODE=$?

echo ""
if [ $SSH_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ 마스터 노드 ConfigMap이 올바릅니다!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}워커 노드에서 조인을 다시 시도하세요:${NC}"
    echo "  sudo ./quick-setup.sh"
    echo ""
else
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠️  마스터 노드에서 직접 수정이 필요합니다${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${BLUE}마스터 노드에 SSH로 접속:${NC}"
    echo "  ssh $MASTER_USER@$MASTER_IP"
    echo ""
    echo -e "${BLUE}다음 명령 실행:${NC}"
    echo "  kubectl edit cm kubeadm-config -n kube-system"
    echo ""
    echo -e "${YELLOW}또는 자동 수정 스크립트 실행:${NC}"
    echo "  # 워커 노드에서:"
    echo "  scp scripts/fix-master-config.sh $MASTER_USER@$MASTER_IP:/tmp/"
    echo "  ssh $MASTER_USER@$MASTER_IP 'sudo /tmp/fix-master-config.sh'"
    echo ""
fi

exit $SSH_EXIT_CODE

