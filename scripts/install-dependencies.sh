#!/bin/bash
#
# K8s VPN Agent - 시스템 의존성 설치 스크립트
# 자동으로 OS를 감지하고 필요한 패키지를 설치합니다.
#

set -euo pipefail

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Root 권한 확인
if [[ $EUID -ne 0 ]]; then
   log_error "이 스크립트는 root 권한으로 실행해야 합니다."
   exit 1
fi

# OS 감지
detect_os() {
    if [[ -f /etc/os-release ]]; then
        . /etc/os-release
        OS=$ID
        VER=$VERSION_ID
    else
        log_error "지원하지 않는 OS입니다."
        exit 1
    fi
    
    log_info "감지된 OS: $OS $VER"
}

# 시스템 요구사항 확인
check_system_requirements() {
    log_step "시스템 요구사항 확인 중..."
    
    total_mem=$(free -m | awk '/^Mem:/{print $2}')
    if [[ $total_mem -lt 2000 ]]; then
        log_warn "메모리가 2GB 미만입니다. 최소 2GB 이상 권장합니다."
    fi
    
    cpu_cores=$(nproc)
    if [[ $cpu_cores -lt 2 ]]; then
        log_warn "CPU 코어가 2개 미만입니다. 최소 2코어 이상 권장합니다."
    fi
    
    available_space=$(df -BG / | awk 'NR==2 {print $4}' | sed 's/G//')
    if [[ $available_space -lt 20 ]]; then
        log_warn "디스크 공간이 20GB 미만입니다. 최소 20GB 이상 권장합니다."
    fi
    
    log_info "시스템 요구사항: CPU=$cpu_cores cores, MEM=${total_mem}MB, DISK=${available_space}GB"
}

# 기본 패키지 설치
install_base_packages() {
    log_step "기본 패키지 설치 중..."
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        apt-get update
        apt-get install -y \
            apt-transport-https \
            ca-certificates \
            curl \
            gnupg \
            lsb-release \
            software-properties-common \
            python3 \
            python3-pip \
            python3-venv \
            net-tools \
            ipset \
            ipvsadm \
            socat \
            conntrack \
            jq \
            wget \
            git
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "rocky" ]]; then
        yum install -y \
            yum-utils \
            device-mapper-persistent-data \
            lvm2 \
            python3 \
            python3-pip \
            net-tools \
            ipset \
            ipvsadm \
            socat \
            conntrack \
            jq \
            wget \
            git
    elif [[ "$OS" == "fedora" ]]; then
        dnf install -y \
            python3 \
            python3-pip \
            net-tools \
            ipset \
            ipvsadm \
            socat \
            conntrack \
            jq \
            wget \
            git
    fi
    
    log_info "기본 패키지 설치 완료"
}

# CRI-O 컨테이너 런타임 설치 (기본)

# CRI-O 설치
install_crio() {
    log_step "CRI-O 설치 확인 중..."
    
    if command -v crio &> /dev/null; then
        log_info "✓ CRI-O가 이미 설치되어 있습니다."
        crio --version
        
        # CRI-O 서비스 상태 확인 및 시작
        if systemctl is-active --quiet crio; then
            log_info "✓ CRI-O 서비스가 실행 중입니다."
        else
            log_info "CRI-O 서비스를 시작합니다..."
            systemctl start crio
            systemctl enable crio
        fi
        
        log_info "CRI-O 설치 확인 완료 (설치 생략)"
        return 0
    fi
    
    log_step "CRI-O 설치 중..."
    
    # Kubernetes 버전에 맞는 CRI-O 버전
    CRIO_VERSION="1.28"
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        # GPG 키 먼저 다운로드 (만료된 키 문제 해결)
        mkdir -p /usr/share/keyrings
        
        log_info "CRI-O GPG 키 다운로드 중..."
        curl -fsSL https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_$(lsb_release -rs)/Release.key | \
            gpg --dearmor -o /usr/share/keyrings/libcontainers-archive-keyring.gpg
        
        curl -fsSL https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable:/cri-o:/${CRIO_VERSION}/xUbuntu_$(lsb_release -rs)/Release.key | \
            gpg --dearmor -o /usr/share/keyrings/libcontainers-crio-archive-keyring.gpg
        
        # CRI-O 저장소 추가
        echo "deb [signed-by=/usr/share/keyrings/libcontainers-archive-keyring.gpg] https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/xUbuntu_$(lsb_release -rs)/ /" | \
            tee /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
        
        echo "deb [signed-by=/usr/share/keyrings/libcontainers-crio-archive-keyring.gpg] https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable:/cri-o:/${CRIO_VERSION}/xUbuntu_$(lsb_release -rs)/ /" | \
            tee /etc/apt/sources.list.d/devel:kubic:libcontainers:stable:cri-o:${CRIO_VERSION}.list
        
        # GPG 키가 만료되었을 경우를 대비한 옵션 추가
        apt-get update --allow-insecure-repositories 2>/dev/null || apt-get update
        
        # CRI-O 설치 (키 검증 경고 무시)
        apt-get install -y --allow-unauthenticated cri-o cri-o-runc || \
        apt-get install -y -o APT::Get::AllowUnauthenticated=true cri-o cri-o-runc
        
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "rocky" ]]; then
        OS_VERSION=$(rpm -E %rhel)
        
        # CRI-O 저장소 추가
        curl -L -o /etc/yum.repos.d/devel:kubic:libcontainers:stable.repo \
            https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable/CentOS_${OS_VERSION}/devel:kubic:libcontainers:stable.repo
        
        curl -L -o /etc/yum.repos.d/devel:kubic:libcontainers:stable:cri-o:${CRIO_VERSION}.repo \
            https://download.opensuse.org/repositories/devel:/kubic:/libcontainers:/stable:/cri-o:/${CRIO_VERSION}/CentOS_${OS_VERSION}/devel:kubic:libcontainers:stable:cri-o:${CRIO_VERSION}.repo
        
        yum install -y cri-o
        
    elif [[ "$OS" == "fedora" ]]; then
        # Fedora용 CRI-O 설치
        dnf install -y cri-o
    fi
    
    # CRI-O 설정
    mkdir -p /etc/crio/crio.conf.d
    
    # Systemd cgroup 드라이버 설정
    cat > /etc/crio/crio.conf.d/02-cgroup-manager.conf <<EOF
[crio.runtime]
conmon_cgroup = "pod"
cgroup_manager = "systemd"
EOF
    
    # 컨테이너 레지스트리 설정
    mkdir -p /etc/containers/registries.conf.d
    cat > /etc/containers/registries.conf.d/crio.conf <<EOF
unqualified-search-registries = ["docker.io"]

[[registry]]
location = "harbor.bigdata-car.kr:30954"
insecure = true
EOF
    
    log_info "컨테이너 레지스트리 설정 완료 (Harbor: harbor.bigdata-car.kr:30954)"
    
    systemctl daemon-reload
    systemctl start crio
    systemctl enable crio
    
    log_info "CRI-O 설치 완료"
}

# Kubelet에서 CRI-O 사용하도록 설정
configure_kubelet_for_crio() {
    log_step "Kubelet CRI-O 연동 설정 확인 중..."
    
    # 이미 설정되어 있는지 확인
    if [ -f "/etc/systemd/system/kubelet.service.d/0-crio.conf" ] && \
       [ -f "/var/lib/kubelet/config.yaml" ]; then
        log_info "✓ Kubelet CRI-O 연동 설정이 이미 되어 있습니다."
        return 0
    fi
    
    log_step "Kubelet CRI-O 연동 설정 중..."
    
    # Kubelet 환경 변수 설정
    mkdir -p /etc/systemd/system/kubelet.service.d
    
    cat > /etc/systemd/system/kubelet.service.d/0-crio.conf <<EOF
[Service]
Environment="KUBELET_EXTRA_ARGS=--container-runtime=remote --container-runtime-endpoint=unix:///var/run/crio/crio.sock --cgroup-driver=systemd"
EOF
    
    # Kubelet 기본 설정에 CRI-O 소켓 추가
    mkdir -p /var/lib/kubelet
    cat > /var/lib/kubelet/config.yaml <<EOF
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
cgroupDriver: systemd
containerRuntimeEndpoint: unix:///var/run/crio/crio.sock
EOF
    
    systemctl daemon-reload
    
    log_info "✓ Kubelet CRI-O 연동 설정 완료"
    log_info "  CRI-O 소켓: unix:///var/run/crio/crio.sock"
}


# Kubernetes 도구 설치
install_kubernetes_tools() {
    log_step "Kubernetes 도구 설치 중..."
    
    if command -v kubeadm &> /dev/null; then
        log_info "Kubernetes 도구가 이미 설치되어 있습니다."
        kubeadm version
        return
    fi
    
    K8S_VERSION="1.28"
    
    if [[ "$OS" == "ubuntu" ]] || [[ "$OS" == "debian" ]]; then
        curl -fsSL https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/Release.key | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
        echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/deb/ /" | tee /etc/apt/sources.list.d/kubernetes.list
        
        apt-get update
        apt-get install -y kubelet kubeadm kubectl
        apt-mark hold kubelet kubeadm kubectl
    elif [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "rocky" ]]; then
        cat <<EOF > /etc/yum.repos.d/kubernetes.repo
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/repodata/repomd.xml.key
EOF
        
        yum install -y kubelet kubeadm kubectl
    elif [[ "$OS" == "fedora" ]]; then
        cat <<EOF > /etc/yum.repos.d/kubernetes.repo
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/v${K8S_VERSION}/rpm/repodata/repomd.xml.key
EOF
        
        dnf install -y kubelet kubeadm kubectl
    fi
    
    systemctl enable kubelet
    
    log_info "Kubernetes 도구 설치 완료"
}

# 시스템 설정
configure_system() {
    log_step "시스템 설정 중..."
    
    # Swap 비활성화
    swapoff -a
    sed -i '/ swap / s/^/#/' /etc/fstab
    
    # 커널 모듈 로드
    cat <<EOF | tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
    
    modprobe overlay
    modprobe br_netfilter
    
    # 커널 파라미터 설정
    cat <<EOF | tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
    
    sysctl --system
    
    # SELinux 설정 (CentOS/RHEL)
    if [[ "$OS" == "centos" ]] || [[ "$OS" == "rhel" ]] || [[ "$OS" == "rocky" ]]; then
        setenforce 0 || true
        sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config
    fi
    
    log_info "시스템 설정 완료"
}

# 설치 확인
verify_installation() {
    log_step "설치 확인 중..."
    
    local errors=0
    
    # CRI-O 컨테이너 런타임 확인
    if command -v crio &> /dev/null; then
        log_info "✓ CRI-O: $(crio --version | head -n1)"
    else
        log_error "✗ CRI-O가 설치되지 않았습니다."
        errors=$((errors + 1))
    fi
    
    if command -v kubeadm &> /dev/null; then
        log_info "✓ kubeadm: $(kubeadm version -o short)"
    else
        log_error "✗ kubeadm이 설치되지 않았습니다."
        errors=$((errors + 1))
    fi
    
    if command -v kubelet &> /dev/null; then
        log_info "✓ kubelet: $(kubelet --version)"
    else
        log_error "✗ kubelet이 설치되지 않았습니다."
        errors=$((errors + 1))
    fi
    
    if command -v kubectl &> /dev/null; then
        log_info "✓ kubectl: $(kubectl version --client -o json 2>/dev/null | jq -r '.clientVersion.gitVersion')"
    else
        log_error "✗ kubectl이 설치되지 않았습니다."
        errors=$((errors + 1))
    fi
    
    if command -v python3 &> /dev/null; then
        log_info "✓ Python3: $(python3 --version)"
    else
        log_error "✗ Python3가 설치되지 않았습니다."
        errors=$((errors + 1))
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_info "모든 필수 패키지가 정상적으로 설치되었습니다."
        return 0
    else
        log_error "$errors개의 패키지 설치에 실패했습니다."
        return 1
    fi
}

# 설치될 패키지 목록 표시
show_packages() {
    log_step "설치될 패키지 목록"
    echo ""
    echo "【시스템 기본 패키지】"
    echo "  - curl, wget, git, jq"
    echo "  - net-tools, ipset, ipvsadm, socat, conntrack"
    echo "  - Python 3.8+ (python3, python3-pip, python3-venv)"
    echo ""
    echo "【컨테이너 런타임】"
    echo "  - CRI-O (컨테이너 런타임)"
    echo ""
    echo "【Kubernetes 도구】"
    echo "  - kubeadm v1.28.x"
    echo "  - kubelet v1.28.x"
    echo "  - kubectl v1.28.x"
    echo ""
    echo "【VPN 클라이언트】"
    echo "  - Tailscale (에이전트 실행 시 자동 설치)"
    echo ""
    echo "자세한 패키지 정보: docs/PREREQUISITES.md"
    echo ""
}

# 메인 실행
main() {
    echo "========================================"
    echo " K8s VPN Agent - 의존성 설치"
    echo "========================================"
    echo ""
    
    show_packages
    
    read -p "계속하시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "설치가 취소되었습니다."
        exit 0
    fi
    
    echo ""
    
    detect_os
    check_system_requirements
    install_base_packages
    configure_system
    install_crio
    install_kubernetes_tools
    configure_kubelet_for_crio
    verify_installation
    
    echo ""
    echo "========================================"
    echo " 의존성 설치 완료!"
    echo "========================================"
    echo ""
    log_info "설치된 패키지:"
    log_info "  • Python $(python3 --version 2>&1 | cut -d' ' -f2)"
    log_info "  • CRI-O $(crio --version 2>&1 | head -n1)"
    log_info "  • kubeadm $(kubeadm version -o short 2>&1)"
    log_info "  • kubelet $(kubelet --version 2>&1 | cut -d' ' -f2)"
    log_info "  • kubectl $(kubectl version --client -o json 2>&1 | jq -r '.clientVersion.gitVersion')"
    echo ""
    log_info "📌 Kubelet은 CRI-O를 컨테이너 런타임으로 사용하도록 설정되었습니다."
    log_info "   CRI-O 소켓: unix:///var/run/crio/crio.sock"
    echo ""
    log_info "다음 단계: K8s VPN Agent를 설치하세요."
    log_info "  cd /root/k8s-vpn-agent"
    log_info "  ./scripts/install-agent.sh"
}

main

