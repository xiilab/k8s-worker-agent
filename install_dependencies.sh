#!/bin/bash
set -e

# Kubernetes Worker Node Agent - 의존성 설치 스크립트
# CRI-O, kubeadm, kubelet 설치

echo "=========================================="
echo "Kubernetes Worker Node Agent"
echo "의존성 설치를 시작합니다..."
echo "=========================================="

# 루트 권한 확인
if [ "$EUID" -ne 0 ]; then 
    echo "이 스크립트는 root 권한이 필요합니다."
    exit 1
fi

# OS 버전 확인
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VER=$VERSION_ID
else
    echo "지원하지 않는 운영체제입니다."
    exit 1
fi

echo "감지된 OS: $OS $VER"

# 0. Python 환경 설치
echo ""
echo "[0/7] Python 환경 설치 중..."
if ! command -v python3 &> /dev/null; then
    echo "Python3를 설치합니다..."
    apt-get update -qq
    apt-get install -y -qq python3 python3-pip python3-dev build-essential
    echo "✓ Python3 설치 완료: $(python3 --version)"
else
    echo "✓ Python3가 이미 설치되어 있습니다: $(python3 --version)"
fi

# pip 확인 및 설치
if ! command -v pip3 &> /dev/null; then
    echo "pip3를 설치합니다..."
    apt-get install -y -qq python3-pip
fi

# 빌드 도구 확인 (Python 패키지 컴파일용)
if ! dpkg -l | grep -q build-essential; then
    echo "빌드 도구를 설치합니다..."
    apt-get install -y -qq build-essential python3-dev
fi

echo "✓ Python 환경 준비 완료"

# 0.5. GPU 드라이버 확인 및 설치
echo ""
echo "[0.5/7] GPU 드라이버 확인 중..."

# 드라이버 설치 플래그 초기화
INSTALL_DRIVER=false

# nvidia-smi로 드라이버 설치 여부 확인
if command -v nvidia-smi &> /dev/null; then
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null | head -n1)
    if [ -n "$DRIVER_VERSION" ]; then
        echo "✓ NVIDIA 드라이버가 이미 설치되어 있습니다: $DRIVER_VERSION"
        echo "  GPU 정보:"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -n1
    else
        echo "⚠️  nvidia-smi는 있지만 드라이버가 제대로 로드되지 않았습니다."
        echo "  드라이버 재설치를 시도합니다..."
        INSTALL_DRIVER=true
    fi
else
    echo "NVIDIA 드라이버가 설치되어 있지 않습니다."
    
    # GPU 하드웨어 존재 여부 확인
    if lspci | grep -i nvidia > /dev/null 2>&1; then
        echo "✓ NVIDIA GPU 감지됨"
        lspci | grep -i nvidia
        echo ""
        echo "NVIDIA 드라이버를 설치합니다..."
        INSTALL_DRIVER=true
    else
        echo "ℹ️  NVIDIA GPU가 감지되지 않았습니다. 드라이버 설치를 건너뜁니다."
        INSTALL_DRIVER=false
    fi
fi

# 드라이버 설치 진행
if [ "$INSTALL_DRIVER" = "true" ]; then
    echo ""
    echo "📦 NVIDIA 드라이버 535 버전 설치 중... (5-10분 소요)"
    
    # 필요한 패키지 설치
    apt-get update -qq
    apt-get install -y -qq build-essential dkms
    
    # Ubuntu 저장소에서 드라이버 설치
    apt-get install -y nvidia-driver-535 nvidia-dkms-535
    
    if [ $? -eq 0 ]; then
        echo "✓ NVIDIA 드라이버 535 설치 완료"
        echo ""
        echo "⚠️  중요: 드라이버 적용을 위해 시스템을 재부팅해야 합니다!"
        echo ""
        echo "재부팅 후 다음 명령으로 확인하세요:"
        echo "  nvidia-smi"
        echo ""
        
        read -p "지금 재부팅하시겠습니까? [y/N]: " REBOOT_NOW
        if [[ "$REBOOT_NOW" =~ ^[Yy]$ ]]; then
            echo "시스템을 재부팅합니다..."
            echo "재부팅 후 이 스크립트를 다시 실행하세요: sudo bash install_dependencies.sh"
            sleep 3
            reboot
        else
            echo "재부팅을 건너뜁니다. 나중에 수동으로 재부팅하세요."
            echo ""
        fi
    else
        echo "⚠️  드라이버 설치 실패. 계속 진행합니다..."
    fi
fi

echo "✓ GPU 드라이버 확인 완료"

# 1. 기존 저장소 정리 (오류 방지)
echo ""
echo "[1/7] 기존 설정 정리 중..."
echo "오래된 CRI-O 및 Kubernetes 저장소를 제거합니다..."

# 오래된 CRI-O 저장소 제거
rm -f /etc/apt/sources.list.d/cri-o.list 2>/dev/null || true
rm -f /etc/apt/keyrings/cri-o-apt-keyring.gpg 2>/dev/null || true
rm -f /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list 2>/dev/null || true
rm -f /etc/apt/sources.list.d/devel:kubic:libcontainers:stable:cri-o:*.list 2>/dev/null || true
rm -f /usr/share/keyrings/libcontainers-archive-keyring.gpg 2>/dev/null || true
rm -f /usr/share/keyrings/libcontainers-crio-archive-keyring.gpg 2>/dev/null || true

# 오래된 Kubernetes 저장소 제거
rm -f /etc/apt/sources.list.d/kubernetes.list 2>/dev/null || true
rm -f /etc/apt/keyrings/kubernetes-apt-keyring.gpg 2>/dev/null || true

# keyrings 디렉토리 생성
mkdir -p /etc/apt/keyrings

echo "✓ 기존 설정 정리 완료"

# 2. 시스템 업데이트 및 기본 패키지 설치
echo ""
echo "[2/7] 시스템 업데이트 및 기본 패키지 설치..."
apt-get update -y
apt-get install -y apt-transport-https ca-certificates curl gnupg2 software-properties-common

# 3. 커널 모듈 로드
echo ""
echo "[3/7] 커널 모듈 설정..."
cat <<EOF | tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

modprobe overlay
modprobe br_netfilter

# 4. sysctl 설정
echo ""
echo "[4/7] sysctl 파라미터 설정..."
cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sysctl --system

# 5. CRI-O 설치
echo ""
echo "[5/7] CRI-O 컨테이너 런타임 설치..."

# Kubernetes 버전에 맞는 CRI-O 버전 설정
KUBERNETES_VERSION=1.30
CRIO_VERSION=1.30

# CRI-O가 이미 설치되어 있는지 확인
if command -v crio &> /dev/null; then
    INSTALLED_VERSION=$(crio --version | head -n1 | awk '{print $NF}')
    echo "✓ CRI-O가 이미 설치되어 있습니다: $INSTALLED_VERSION"
    
    # 버전이 맞지 않으면 재설치
    if [[ "$INSTALLED_VERSION" != *"1.30"* ]]; then
        echo "버전이 맞지 않아 재설치합니다..."
        systemctl stop crio || true
        apt-get remove -y cri-o conmon containers-common || true
        apt-get autoremove -y
    else
        # 서비스 상태 확인
        if systemctl is-active --quiet crio; then
            echo "✓ CRI-O 서비스가 실행 중입니다."
        else
            echo "CRI-O 서비스를 시작합니다..."
            systemctl start crio
            systemctl enable crio
        fi
        echo "CRI-O 설치 확인 완료 (설치 생략)"
        
        # Harbor insecure registry 설정 (이미 있는지 확인)
        if [ ! -f /etc/containers/registries.conf.d/crio.conf ]; then
            echo "Harbor insecure registry 설정 추가 중..."
            mkdir -p /etc/containers/registries.conf.d
            cat > /etc/containers/registries.conf.d/crio.conf <<'EOF'
unqualified-search-registries = ["docker.io"]

[[registry]]
location = "harbor.bigdata-car.kr:30954"
insecure = true
EOF
            echo "✓ Harbor insecure registry 설정 완료"
            systemctl restart crio
        fi
        
        # 다음 단계로
        return 0 2>/dev/null || :
    fi
fi

# CRI-O 설치 시작
echo "CRI-O v${CRIO_VERSION} 설치 중..."

# 충돌하는 패키지 먼저 제거
echo "충돌 가능한 패키지 제거 중..."
apt-get remove -y conmon containers-common 2>/dev/null || true
apt-get autoremove -y

# pkgs.k8s.io 저장소 사용 (최신 방식)
echo "CRI-O 저장소 추가 중..."
mkdir -p /etc/apt/keyrings
curl -fsSL https://pkgs.k8s.io/addons:/cri-o:/stable:/v${CRIO_VERSION}/deb/Release.key | \
    gpg --dearmor -o /etc/apt/keyrings/cri-o-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/cri-o-apt-keyring.gpg] https://pkgs.k8s.io/addons:/cri-o:/stable:/v${CRIO_VERSION}/deb/ /" | \
    tee /etc/apt/sources.list.d/cri-o.list

echo "✓ CRI-O 저장소 추가 완료"

# apt 업데이트
echo "저장소 목록 업데이트 중..."
apt-get update -y

# CRI-O 설치
echo "CRI-O 및 관련 패키지 설치 중..."
DEBIAN_FRONTEND=noninteractive apt-get install -y -o Dpkg::Options::="--force-overwrite" cri-o

# CRI-O 시작 및 활성화
echo "CRI-O 서비스 시작 중..."
systemctl daemon-reload
systemctl enable crio
systemctl start crio

# Harbor insecure registry 설정
echo "Harbor insecure registry 설정 추가 중..."
mkdir -p /etc/containers/registries.conf.d
cat > /etc/containers/registries.conf.d/crio.conf <<'EOF'
unqualified-search-registries = ["docker.io"]

[[registry]]
location = "harbor.bigdata-car.kr:30954"
insecure = true
EOF

echo "✓ Harbor insecure registry 설정 완료"

# CRI-O 재시작 (설정 적용)
systemctl restart crio

echo "✓ CRI-O 설치 완료 및 실행 중"

# 6. Kubernetes 도구 설치 (kubeadm, kubelet, kubectl)
echo ""
echo "[6/7] Kubernetes 도구 설치..."

# Kubernetes 저장소 추가 (이미 [1/7]에서 정리됨)
echo "Kubernetes v${KUBERNETES_VERSION} 저장소 추가 중..."
curl -fsSL https://pkgs.k8s.io/core:/stable:/v${KUBERNETES_VERSION}/deb/Release.key | \
    gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${KUBERNETES_VERSION}/deb/ /" | \
    tee /etc/apt/sources.list.d/kubernetes.list

# 저장소 업데이트
apt-get update -y

# Kubernetes 도구 설치
echo "kubeadm, kubelet, kubectl 설치 중..."
apt-get install -y kubelet kubeadm kubectl

# 버전 고정 (자동 업데이트 방지)
apt-mark hold kubelet kubeadm kubectl

# kubelet이 CRI-O를 사용하도록 설정
cat <<EOF | tee /etc/default/kubelet
KUBELET_EXTRA_ARGS=--container-runtime-endpoint=unix:///var/run/crio/crio.sock
EOF

# kubelet 활성화 (아직 시작하지 않음 - 조인 후 시작됨)
systemctl enable kubelet

echo "Kubernetes 도구 설치 완료"

# 7. 네트워크 도구 및 방화벽 설정
echo ""
echo "[7/7] 네트워크 도구 설치..."
apt-get install -y iptables ipset conntrack socat

# swap 비활성화 (Kubernetes 요구사항)
swapoff -a
sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

echo ""
echo "=========================================="
echo "의존성 설치가 완료되었습니다!"
echo "=========================================="
echo ""
echo "설치된 버전:"
echo "- CRI-O: $(crio --version | head -n1)"
echo "- kubeadm: $(kubeadm version -o short)"
echo "- kubelet: $(kubelet --version)"
echo ""
echo "다음 단계: Python 에이전트를 실행하여 클러스터에 조인하세요."
echo "  python3 agent.py"
echo ""

