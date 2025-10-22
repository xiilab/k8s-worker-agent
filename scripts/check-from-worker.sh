#!/bin/bash
#
# 워커 노드에서 kubectl을 사용하여 마스터의 ConfigMap을 확인하는 스크립트
# 마스터의 admin.conf가 필요합니다
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MASTER_IP="10.61.3.12"
MASTER_USER="${MASTER_USER:-root}"
ADMIN_CONF="/tmp/k8s-admin.conf"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔍 워커 노드에서 마스터 ConfigMap 확인${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# admin.conf 확인
if [ ! -f "$ADMIN_CONF" ]; then
    echo -e "${YELLOW}⚠️  admin.conf가 없습니다${NC}"
    echo ""
    echo -e "${BLUE}마스터 노드에서 admin.conf를 가져오세요:${NC}"
    echo ""
    echo -e "${GREEN}방법 1: SCP 사용${NC}"
    echo "  scp $MASTER_USER@$MASTER_IP:/etc/kubernetes/admin.conf $ADMIN_CONF"
    echo ""
    echo -e "${GREEN}방법 2: 수동 복사${NC}"
    echo "  1. 마스터 노드에서 실행:"
    echo "     cat /etc/kubernetes/admin.conf"
    echo "  2. 출력 내용을 복사"
    echo "  3. 워커 노드에서:"
    echo "     vi $ADMIN_CONF"
    echo "     # 붙여넣기하고 저장"
    echo ""
    echo -e "${RED}보안 주의:${NC} admin.conf는 클러스터 전체 권한을 가진 파일입니다."
    echo "사용 후 삭제하세요: ${GREEN}rm $ADMIN_CONF${NC}"
    echo ""
    
    read -p "지금 admin.conf를 가져오시겠습니까? (y/N): " FETCH
    if [[ "$FETCH" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}admin.conf 가져오는 중...${NC}"
        if scp $MASTER_USER@$MASTER_IP:/etc/kubernetes/admin.conf $ADMIN_CONF 2>/dev/null; then
            echo -e "${GREEN}✓ admin.conf 다운로드 완료${NC}"
            chmod 600 $ADMIN_CONF
        else
            echo -e "${RED}✗ SCP 실패${NC}"
            echo "수동으로 복사하세요."
            exit 1
        fi
    else
        exit 1
    fi
fi

echo -e "${GREEN}✓ admin.conf 확인 완료${NC}"
echo ""

# kubectl로 ConfigMap 확인
echo -e "${BLUE}1️⃣  ConfigMap 확인 중...${NC}"
echo ""

CLUSTER_CONFIG=$(KUBECONFIG=$ADMIN_CONF kubectl get cm kubeadm-config -n kube-system -o jsonpath='{.data.ClusterConfiguration}' 2>/dev/null)

if [ -z "$CLUSTER_CONFIG" ]; then
    echo -e "${RED}✗ ConfigMap을 가져올 수 없습니다${NC}"
    echo "admin.conf가 올바른지 확인하세요."
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "현재 ClusterConfiguration:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$CLUSTER_CONFIG" | head -50
echo ""

# extraArgs 확인
echo -e "${BLUE}2️⃣  extraArgs 형식 확인 중...${NC}"
echo ""

if echo "$CLUSTER_CONFIG" | grep -q "extraArgs:" && echo "$CLUSTER_CONFIG" | grep -A 5 "extraArgs:" | grep -q "^[[:space:]]*-[[:space:]]*"; then
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ 문제 발견: extraArgs가 배열 형식입니다!${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    echo -e "${YELLOW}문제가 있는 부분:${NC}"
    echo "$CLUSTER_CONFIG" | grep -A 10 "extraArgs:"
    echo ""
    
    echo -e "${BLUE}3️⃣  수정하시겠습니까? (y/N):${NC}"
    read -p "> " FIX
    
    if [[ "$FIX" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${GREEN}kubectl edit 실행...${NC}"
        echo ""
        KUBECONFIG=$ADMIN_CONF kubectl edit cm kubeadm-config -n kube-system
        
        echo ""
        echo -e "${BLUE}4️⃣  수정 확인 중...${NC}"
        sleep 2
        
        CLUSTER_CONFIG_NEW=$(KUBECONFIG=$ADMIN_CONF kubectl get cm kubeadm-config -n kube-system -o jsonpath='{.data.ClusterConfiguration}' 2>/dev/null)
        
        if echo "$CLUSTER_CONFIG_NEW" | grep -q "extraArgs:" && echo "$CLUSTER_CONFIG_NEW" | grep -A 5 "extraArgs:" | grep -q "^[[:space:]]*-[[:space:]]*"; then
            echo -e "${RED}✗ 아직 배열 형식입니다${NC}"
        else
            echo -e "${GREEN}✓ 수정 완료!${NC}"
            echo ""
            echo -e "${YELLOW}워커 노드에서 조인을 다시 시도하세요:${NC}"
            echo "  sudo ./quick-setup.sh"
        fi
    fi
else
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ extraArgs가 올바른 형식입니다!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}워커 노드에서 조인을 시도할 수 있습니다:${NC}"
    echo "  sudo ./quick-setup.sh"
fi

echo ""
echo -e "${YELLOW}보안: admin.conf를 삭제하시겠습니까? (Y/n):${NC}"
read -p "> " DELETE
if [[ ! "$DELETE" =~ ^[Nn]$ ]]; then
    rm -f $ADMIN_CONF
    echo -e "${GREEN}✓ admin.conf 삭제됨${NC}"
fi

