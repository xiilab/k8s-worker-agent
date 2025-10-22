#!/bin/bash

echo "=========================================="
echo "K8s Worker Node Agent - 완전 제거 스크립트"
echo "=========================================="
echo ""

# 루트 권한 확인
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 이 스크립트는 root 권한이 필요합니다."
    echo "   sudo bash cleanup.sh 로 실행해주세요."
    exit 1
fi

echo "⚠️  경고: 이 스크립트는 다음 항목을 완전히 제거합니다:"
echo ""
echo "   [서비스 및 프로세스]"
echo "   - kubelet, crio 서비스 중지 및 비활성화"
echo ""
echo "   [Kubernetes 관련]"
echo "   - 클러스터에서 노드 제거 (kubeadm reset)"
echo "   - /etc/kubernetes/ 전체 삭제"
echo "   - /var/lib/kubelet/ 전체 삭제"
echo "   - /etc/cni/net.d/ CNI 설정 삭제"
echo "   - /etc/default/kubelet 설정 삭제"
echo ""
echo "   [CRI-O 관련]"
echo "   - /etc/crio/ 설정 삭제"
echo "   - /etc/containers/ 설정 삭제"
echo "   - /var/lib/crio/ 데이터 삭제"
echo ""
echo "   [저장소 및 키]"
echo "   - CRI-O 저장소 및 GPG 키 제거"
echo "   - Kubernetes 저장소 및 GPG 키 제거"
echo ""
echo "   [네트워크]"
echo "   - iptables 규칙 초기화"
echo "   - CNI 네트워크 인터페이스 정리"
echo ""
echo "   [로그 및 기타]"
echo "   - /var/log/k8s-agent.log 삭제"
echo "   - config.yaml 삭제 (백업 제외)"
echo ""
echo "   ⚠️  패키지 제거 옵션 (선택):"
echo "   - kubeadm, kubelet, kubectl"
echo "   - cri-o 및 관련 패키지"
echo ""

read -p "정말로 모든 항목을 제거하시겠습니까? (yes/no): " CONFIRM
if [[ "$CONFIRM" != "yes" ]]; then
    echo "취소되었습니다."
    exit 0
fi

echo ""
read -p "패키지도 함께 제거하시겠습니까? (kubeadm, kubelet, kubectl, cri-o) (y/n): " REMOVE_PACKAGES
echo ""

echo "정리 시작..."
echo ""

# 1. 서비스 중지
echo "[1/10] 서비스 중지 중..."
systemctl stop kubelet 2>/dev/null || true
systemctl stop crio 2>/dev/null || true
systemctl disable kubelet 2>/dev/null || true
systemctl disable crio 2>/dev/null || true
echo "✅ 서비스 중지 완료"

# 2. kubeadm reset 실행
echo ""
echo "[2/10] Kubernetes 클러스터에서 노드 제거 중..."
kubeadm reset -f 2>/dev/null || echo "   (kubeadm이 설치되지 않았거나 이미 리셋됨)"
echo "✅ 노드 제거 완료"

# 3. Kubernetes 디렉토리 및 파일 삭제
echo ""
echo "[3/10] Kubernetes 설정 및 데이터 삭제 중..."
rm -rf /etc/kubernetes
rm -rf /var/lib/kubelet
rm -rf /var/lib/etcd
rm -rf /etc/cni/net.d
rm -f /etc/default/kubelet
rm -rf $HOME/.kube
echo "✅ Kubernetes 설정 삭제 완료"

# 4. CRI-O 디렉토리 및 파일 삭제
echo ""
echo "[4/10] CRI-O 설정 및 데이터 삭제 중..."
rm -rf /etc/crio
rm -rf /etc/containers
rm -rf /var/lib/crio
rm -rf /var/lib/containers
echo "✅ CRI-O 설정 삭제 완료"

# 5. CNI 플러그인 삭제
echo ""
echo "[5/10] CNI 플러그인 삭제 중..."
rm -rf /opt/cni/bin
rm -rf /var/lib/cni
echo "✅ CNI 플러그인 삭제 완료"

# 6. 저장소 및 GPG 키 제거
echo ""
echo "[6/10] 저장소 및 GPG 키 제거 중..."
rm -f /etc/apt/sources.list.d/cri-o.list
rm -f /etc/apt/keyrings/cri-o-apt-keyring.gpg
rm -f /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
rm -f /etc/apt/sources.list.d/devel:kubic:libcontainers:stable:cri-o:*.list
rm -f /usr/share/keyrings/libcontainers-archive-keyring.gpg
rm -f /usr/share/keyrings/libcontainers-crio-archive-keyring.gpg
rm -f /etc/apt/sources.list.d/kubernetes.list
rm -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "✅ 저장소 및 키 제거 완료"

# 7. 네트워크 정리
echo ""
echo "[7/10] 네트워크 설정 정리 중..."

# iptables 규칙 초기화 (선택적)
read -p "   iptables 규칙을 초기화하시겠습니까? (y/n): " RESET_IPTABLES
if [[ "$RESET_IPTABLES" == "y" || "$RESET_IPTABLES" == "Y" ]]; then
    iptables -F 2>/dev/null || true
    iptables -t nat -F 2>/dev/null || true
    iptables -t mangle -F 2>/dev/null || true
    iptables -X 2>/dev/null || true
    echo "   ✓ iptables 규칙 초기화 완료"
else
    echo "   (iptables 규칙 유지)"
fi

# CNI 네트워크 인터페이스 제거
ip link delete cni0 2>/dev/null || true
ip link delete flannel.1 2>/dev/null || true
ip link delete tunl0 2>/dev/null || true
echo "✅ 네트워크 정리 완료"

# 8. 로그 및 설정 파일 삭제
echo ""
echo "[8/10] 로그 및 설정 파일 삭제 중..."
rm -f /var/log/k8s-agent.log
rm -f config.yaml  # config.yaml.example은 유지
echo "✅ 로그 및 설정 삭제 완료"

# 9. 패키지 제거 (선택)
echo ""
echo "[9/10] 패키지 제거 중..."
if [[ "$REMOVE_PACKAGES" == "y" || "$REMOVE_PACKAGES" == "Y" ]]; then
    apt-mark unhold kubelet kubeadm kubectl 2>/dev/null || true
    
    apt-get remove -y kubeadm kubelet kubectl 2>/dev/null || echo "   (Kubernetes 도구가 설치되지 않았거나 이미 제거됨)"
    apt-get remove -y cri-o cri-tools conmon containers-common 2>/dev/null || echo "   (CRI-O가 설치되지 않았거나 이미 제거됨)"
    apt-get autoremove -y
    
    echo "   ✓ 패키지 제거 완료"
else
    echo "   (패키지 유지)"
fi
echo "✅ 패키지 처리 완료"

# 10. apt 캐시 정리 및 업데이트
echo ""
echo "[10/10] apt 캐시 정리 및 업데이트 중..."
apt-get clean
rm -rf /var/lib/apt/lists/*
apt-get update -y 2>&1 | grep -E "Hit:|Get:|Ign:" | head -20
echo "✅ apt 캐시 정리 완료"

echo ""
echo "=========================================="
echo "✅ 완전 제거 완료!"
echo "=========================================="
echo ""
echo "제거된 항목:"
echo "  - Kubernetes 클러스터 연결 해제"
echo "  - 모든 설정 파일 및 데이터"
echo "  - CNI 네트워크 설정"
echo "  - 저장소 및 GPG 키"
if [[ "$REMOVE_PACKAGES" == "y" || "$REMOVE_PACKAGES" == "Y" ]]; then
    echo "  - kubeadm, kubelet, kubectl, cri-o 패키지"
fi
echo ""
echo "시스템이 깨끗하게 정리되었습니다."
echo ""
echo "재설치하려면:"
echo "  sudo bash quick_install.sh"
echo ""
echo "⚠️  참고: 재부팅을 권장합니다."
echo "  sudo reboot"
echo ""

