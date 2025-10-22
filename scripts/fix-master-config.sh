#!/bin/bash
#
# kubeadm-config ConfigMap 문제 진단 및 수정 스크립트
# 마스터 노드에서 실행하세요!
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 kubeadm-config ConfigMap 진단"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Root 권한 확인
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}이 스크립트는 root 권한으로 실행해야 합니다.${NC}"
   exit 1
fi

# kubectl 확인
if ! command -v kubectl &> /dev/null; then
    echo -e "${RED}kubectl이 설치되지 않았습니다.${NC}"
    exit 1
fi

# ConfigMap 존재 확인
if ! kubectl get cm kubeadm-config -n kube-system &> /dev/null; then
    echo -e "${RED}kubeadm-config ConfigMap을 찾을 수 없습니다.${NC}"
    exit 1
fi

echo -e "${BLUE}1️⃣  현재 설정 확인 중...${NC}"
echo ""

# ClusterConfiguration 추출
CLUSTER_CONFIG=$(kubectl get cm kubeadm-config -n kube-system -o jsonpath='{.data.ClusterConfiguration}')

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 현재 ClusterConfiguration:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "$CLUSTER_CONFIG"
echo ""

# extraArgs 형식 확인
if echo "$CLUSTER_CONFIG" | grep -q "extraArgs:" && echo "$CLUSTER_CONFIG" | grep -q "^[[:space:]]*-[[:space:]]*"; then
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${RED}❌ 문제 발견!${NC}"
    echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo -e "${YELLOW}extraArgs가 배열 형식으로 되어 있습니다.${NC}"
    echo ""
    
    # 문제가 있는 부분 강조 표시
    echo -e "${RED}잘못된 형식:${NC}"
    echo "$CLUSTER_CONFIG" | grep -A 10 "extraArgs:" | head -15
    echo ""
    
    echo -e "${BLUE}2️⃣  백업 생성 중...${NC}"
    BACKUP_FILE="/root/kubeadm-config-backup-$(date +%Y%m%d-%H%M%S).yaml"
    kubectl get cm kubeadm-config -n kube-system -o yaml > "$BACKUP_FILE"
    echo -e "${GREEN}✓ 백업 완료: $BACKUP_FILE${NC}"
    echo ""
    
    echo -e "${BLUE}3️⃣  수정 필요${NC}"
    echo ""
    echo -e "${YELLOW}다음 명령으로 수정하세요:${NC}"
    echo ""
    echo -e "  ${GREEN}kubectl edit cm kubeadm-config -n kube-system${NC}"
    echo ""
    echo -e "${YELLOW}수정 방법:${NC}"
    echo ""
    echo -e "${RED}변경 전 (배열 형식):${NC}"
    echo "  apiServer:"
    echo "    extraArgs:"
    echo "      - authorization-mode=Node,RBAC"
    echo "      - enable-admission-plugins=NodeRestriction"
    echo ""
    echo -e "${GREEN}변경 후 (맵 형식):${NC}"
    echo "  apiServer:"
    echo "    extraArgs:"
    echo "      authorization-mode: Node,RBAC"
    echo "      enable-admission-plugins: NodeRestriction"
    echo ""
    echo -e "${YELLOW}주의사항:${NC}"
    echo "  • '-' 기호를 제거하고 'key: value' 형식으로 변경"
    echo "  • '=' 기호를 ': '로 변경"
    echo "  • 들여쓰기 유지"
    echo ""
    
    echo -e "${BLUE}4️⃣  수동 수정을 시작하시겠습니까? (y/N)${NC}"
    read -p "> " PROCEED
    
    if [[ "$PROCEED" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${GREEN}에디터를 엽니다...${NC}"
        echo -e "${YELLOW}변경 후 저장하고 종료하세요.${NC}"
        echo ""
        sleep 2
        
        kubectl edit cm kubeadm-config -n kube-system
        
        echo ""
        echo -e "${BLUE}5️⃣  수정 검증 중...${NC}"
        sleep 2
        
        # 다시 확인
        CLUSTER_CONFIG_NEW=$(kubectl get cm kubeadm-config -n kube-system -o jsonpath='{.data.ClusterConfiguration}')
        
        if echo "$CLUSTER_CONFIG_NEW" | grep -q "extraArgs:" && echo "$CLUSTER_CONFIG_NEW" | grep -q "^[[:space:]]*-[[:space:]]*"; then
            echo -e "${RED}✗ 아직 배열 형식입니다. 다시 확인하세요.${NC}"
            exit 1
        else
            echo -e "${GREEN}✓ 수정 완료!${NC}"
            echo ""
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${GREEN}✓ kubeadm-config가 올바르게 수정되었습니다!${NC}"
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""
            echo -e "${YELLOW}이제 워커 노드에서 조인을 다시 시도하세요:${NC}"
            echo "  sudo ./quick-setup.sh"
            echo ""
        fi
    else
        echo ""
        echo -e "${YELLOW}수동으로 수정하세요:${NC}"
        echo "  kubectl edit cm kubeadm-config -n kube-system"
        echo ""
        echo -e "${YELLOW}수정 후 검증:${NC}"
        echo "  ./scripts/fix-master-config.sh"
        echo ""
    fi
    
else
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✓ kubeadm-config가 올바른 형식입니다!${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "워커 노드에서 조인을 시도할 수 있습니다."
    echo ""
fi

