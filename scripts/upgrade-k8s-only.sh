#!/bin/bash
#
# Kubernetes만 v1.28 → v1.30으로 업그레이드 (CRI-O는 유지)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔄 Kubernetes v1.28 → v1.30 업그레이드${NC}"
echo -e "${BLUE}   (CRI-O는 1.28 유지 - 호환됨)${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Root 권한 확인
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}❌ root 권한으로 실행하세요.${NC}"
   exit 1
fi

# 현재 버전 확인
echo -e "${BLUE}1️⃣  현재 버전 확인${NC}"
echo ""
echo "kubeadm: $(kubeadm version -o short)"
echo "kubelet: $(kubelet --version)"
echo "CRI-O:   $(crio --version | head -1)"
echo ""

# 백업
echo -e "${BLUE}2️⃣  설정 백업${NC}"
mkdir -p /tmp/k8s-backup-$(date +%Y%m%d-%H%M%S)
cp -r /etc/kubernetes /tmp/k8s-backup-$(date +%Y%m%d-%H%M%S)/ 2>/dev/null || true
echo -e "${GREEN}✓ 백업 완료${NC}"
echo ""

# 패키지 고정 해제
echo -e "${BLUE}3️⃣  패키지 고정 해제${NC}"
apt-mark unhold kubelet kubeadm
echo ""

# 저장소 업데이트 (v1.28 → v1.30)
echo -e "${BLUE}4️⃣  Kubernetes 저장소 업데이트 (v1.28 → v1.30)${NC}"

# 기존 키와 저장소 삭제
rm -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg
rm -f /etc/apt/sources.list.d/kubernetes.list

# v1.30 저장소 추가
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | \
  gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /" | \
  tee /etc/apt/sources.list.d/kubernetes.list

echo -e "${GREEN}✓ 저장소 업데이트 완료${NC}"
echo ""

# apt 업데이트
echo -e "${BLUE}5️⃣  패키지 목록 업데이트${NC}"
apt-get update
echo ""

# 업그레이드
echo -e "${BLUE}6️⃣  Kubernetes 패키지 업그레이드${NC}"
echo -e "${YELLOW}⚠️  업그레이드를 시작합니다...${NC}"
echo ""

apt-get install -y kubelet kubeadm

echo ""
echo -e "${GREEN}✓ 업그레이드 완료${NC}"
echo ""

# 패키지 고정
echo -e "${BLUE}7️⃣  패키지 고정${NC}"
apt-mark hold kubelet kubeadm
echo ""

# kubelet 재시작
echo -e "${BLUE}8️⃣  Kubelet 재시작${NC}"
systemctl daemon-reload
systemctl restart kubelet 2>/dev/null || echo "kubelet이 아직 조인되지 않음 (정상)"
echo ""

# 최종 버전 확인
echo -e "${BLUE}9️⃣  업그레이드 완료 확인${NC}"
echo ""
echo "kubeadm: $(kubeadm version -o short)"
echo "kubelet: $(kubelet --version)"
echo "CRI-O:   $(crio --version | head -1)"
echo ""

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Kubernetes v1.30으로 업그레이드 완료!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}📝 참고:${NC}"
echo "  • CRI-O 1.28은 Kubernetes 1.30과 호환됩니다"
echo "  • 마스터 노드: Kubernetes v1.30.13 + CRI-O 1.30.13"
echo "  • 워커 노드: Kubernetes v1.30.x  + CRI-O 1.28.4 ✅"
echo ""
echo -e "${YELLOW}다음 단계:${NC}"
echo "1. 마스터 노드에서 ConfigMap 수정"
echo "2. 워커 노드 join 재시도"
echo "   sudo venv/bin/k8s-vpn-agent join -c config/config.yaml"
echo ""

