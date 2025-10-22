# K8s VPN Agent - 사전 요구사항 및 패키지 정보

## 시스템 요구사항

### 하드웨어
- **CPU**: 2 cores 이상
- **Memory**: 2GB 이상 (4GB 권장)
- **Disk**: 20GB 이상의 여유 공간

### 운영체제
다음 운영체제를 지원합니다:

| OS | 버전 | 패키지 관리자 |
|----|------|--------------|
| Ubuntu | 20.04, 22.04, 24.04 | apt |
| Debian | 11, 12 | apt |
| CentOS | 8, 9 | yum/dnf |
| RHEL | 8, 9 | yum/dnf |
| Rocky Linux | 8, 9 | yum/dnf |
| Fedora | 35+ | dnf |

### 네트워크
- 인터넷 연결 (패키지 다운로드용)
- 마스터 노드와의 통신 경로 (직접 또는 VPN)

## 필수 패키지 목록

### 1. 시스템 기본 패키지

#### Ubuntu/Debian
```bash
apt-transport-https
ca-certificates
curl
gnupg
lsb-release
software-properties-common
net-tools
ipset
ipvsadm
socat
conntrack
jq
wget
git
```

#### CentOS/RHEL/Rocky
```bash
yum-utils
device-mapper-persistent-data
lvm2
net-tools
ipset
ipvsadm
socat
conntrack
jq
wget
git
```

#### Fedora
```bash
net-tools
ipset
ipvsadm
socat
conntrack
jq
wget
git
```

### 2. Python 환경
```
python3 (3.8 이상)
python3-pip
python3-venv
python3-dev (Ubuntu/Debian)
```

**Python 패키지** (`requirements.txt`):
```
click>=8.1.7        # CLI 프레임워크
rich>=13.7.0        # 터미널 UI
pyyaml>=6.0.1       # YAML 파싱
requests>=2.31.0    # HTTP 클라이언트
python-dotenv>=1.0.0
psutil>=5.9.6       # 시스템 정보
tabulate>=0.9.0     # 테이블 출력
jinja2>=3.1.2       # 템플릿
```

### 3. 컨테이너 런타임

#### CRI-O (기본)
```
cri-o
cri-o-runc
```

**설정 디렉토리**: `/etc/crio/crio.conf.d/`
- Systemd cgroup 드라이버 사용
- Kubelet과 자동 연동 설정됨
- CRI-O 소켓: `unix:///var/run/crio/crio.sock`

### 4. Kubernetes 도구

```
kubeadm  (1.30.x) - 클러스터 조인용
kubelet  (1.30.x) - 워커 노드 필수
```

**저장소**: https://pkgs.k8s.io/core:/stable:/v1.30/

**참고**: kubectl은 마스터 노드 전용이며 워커 노드에는 불필요합니다.

### 5. VPN 클라이언트

#### Tailscale/Headscale
```
tailscale
```

**설치 방법**: 
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

### 6. 방화벽 (선택사항)

다음 중 하나가 설치되어 있어야 합니다:

#### UFW (Ubuntu/Debian)
```bash
sudo apt install ufw
```

#### firewalld (CentOS/RHEL/Fedora)
```bash
sudo yum install firewalld
# 또는
sudo dnf install firewalld
```

#### iptables (기본)
대부분의 시스템에 기본 설치됨

## 필수 포트

에이전트가 사용하는 포트:

| 포트 | 프로토콜 | 용도 | 방향 |
|------|----------|------|------|
| 22 | TCP | SSH | Inbound |
| 6443 | TCP | Kubernetes API | Outbound |
| 10250 | TCP | Kubelet API | Inbound |
| 30000-32767 | TCP | NodePort Services | Inbound |
| 41641 | UDP | Tailscale/Headscale VPN | Both |

### 방화벽 설정 예시

#### UFW
```bash
sudo ufw allow 22/tcp
sudo ufw allow 6443/tcp
sudo ufw allow 10250/tcp
sudo ufw allow 30000:32767/tcp
sudo ufw allow 41641/udp
```

#### firewalld
```bash
sudo firewall-cmd --permanent --add-port=22/tcp
sudo firewall-cmd --permanent --add-port=6443/tcp
sudo firewall-cmd --permanent --add-port=10250/tcp
sudo firewall-cmd --permanent --add-port=30000-32767/tcp
sudo firewall-cmd --permanent --add-port=41641/udp
sudo firewall-cmd --reload
```

## 커널 설정

### 필수 커널 모듈
```bash
overlay
br_netfilter
```

### 필수 커널 파라미터
```bash
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
```

## 사전 확인 체크리스트

### 1. 시스템 정보 확인
```bash
# OS 버전
cat /etc/os-release

# 커널 버전
uname -r

# CPU 정보
nproc

# 메모리 정보
free -h

# 디스크 공간
df -h /
```

### 2. 네트워크 확인
```bash
# 인터넷 연결
ping -c 3 8.8.8.8

# DNS 확인
nslookup google.com

# 마스터 노드 연결 (VPN 없이)
ping -c 3 <master-node-ip>
```

### 3. 권한 확인
```bash
# Root 권한 확인
sudo whoami
# 출력: root
```

### 4. Swap 확인
```bash
# Swap 상태 (Kubernetes는 swap 비활성화 필요)
swapon --show
# 비어있어야 함
```

## 자동 설치 스크립트

에이전트는 다음 스크립트를 제공합니다:

### 1. `install-dependencies.sh`
- 모든 시스템 의존성 자동 설치
- OS 자동 감지
- 패키지 관리자 자동 선택

```bash
cd /root/k8s-vpn-agent
sudo ./scripts/install-dependencies.sh
```

**설치 항목**:
- 기본 시스템 패키지
- Python 환경
- Containerd
- Kubernetes 도구 (kubeadm, kubelet, kubectl)
- 커널 설정

**소요 시간**: 약 5-10분

### 2. `install-agent.sh`
- Python 가상환경 생성
- Python 패키지 설치
- 에이전트 설치

```bash
sudo ./scripts/install-agent.sh
```

**설치 항목**:
- Python venv
- Python 패키지 (requirements.txt)
- CLI 도구 (k8s-vpn-agent)

**소요 시간**: 약 2-3분

## 수동 설치 가이드

자동 스크립트를 사용하지 않는 경우:

### Ubuntu/Debian

#### 1. 기본 패키지
```bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl \
  gnupg lsb-release python3 python3-pip python3-venv \
  net-tools ipset ipvsadm socat conntrack jq wget git
```

#### 2. Containerd
```bash
# Docker 저장소 추가
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Containerd 설치
sudo apt update
sudo apt install -y containerd.io

# 설정
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

#### 3. Kubernetes 도구
```bash
# 저장소 추가
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.30/deb/Release.key | \
  sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] \
  https://pkgs.k8s.io/core:/stable:/v1.30/deb/ /" | \
  sudo tee /etc/apt/sources.list.d/kubernetes.list

# 설치 (워커 노드)
sudo apt update
sudo apt install -y kubelet kubeadm
sudo apt-mark hold kubelet kubeadm
```

#### 4. 시스템 설정
```bash
# Swap 비활성화
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

# 커널 모듈
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter

# 커널 파라미터
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

sudo sysctl --system
```

### CentOS/RHEL/Rocky

#### 1. 기본 패키지
```bash
sudo yum install -y yum-utils device-mapper-persistent-data lvm2 \
  python3 python3-pip net-tools ipset ipvsadm socat conntrack jq wget git
```

#### 2. Containerd
```bash
# Docker 저장소 추가
sudo yum-config-manager --add-repo \
  https://download.docker.com/linux/centos/docker-ce.repo

# 설치
sudo yum install -y containerd.io

# 설정
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd
```

#### 3. Kubernetes 도구
```bash
# 저장소 추가
cat <<EOF | sudo tee /etc/yum.repos.d/kubernetes.repo
[kubernetes]
name=Kubernetes
baseurl=https://pkgs.k8s.io/core:/stable:/v1.30/rpm/
enabled=1
gpgcheck=1
gpgkey=https://pkgs.k8s.io/core:/stable:/v1.30/rpm/repodata/repomd.xml.key
EOF

# 설치 (워커 노드)
sudo yum install -y kubelet kubeadm
sudo systemctl enable kubelet
```

#### 4. 시스템 설정
```bash
# Swap 비활성화
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab

# SELinux 설정
sudo setenforce 0
sudo sed -i 's/^SELINUX=enforcing$/SELINUX=permissive/' /etc/selinux/config

# 커널 모듈 및 파라미터 (Ubuntu와 동일)
# ... (위 Ubuntu 섹션의 4번 참고)
```

## 설치 후 확인

### 패키지 설치 확인
```bash
# Python
python3 --version

# Containerd
containerd --version

# Kubernetes 도구 (워커 노드)
kubeadm version
kubelet --version

# Tailscale (VPN 사용 시)
tailscale version
```

### 서비스 상태 확인
```bash
# Containerd
sudo systemctl status containerd

# Kubelet (조인 후)
sudo systemctl status kubelet
```

### 네트워크 설정 확인
```bash
# 커널 모듈
lsmod | grep br_netfilter
lsmod | grep overlay

# 커널 파라미터
sysctl net.bridge.bridge-nf-call-iptables
sysctl net.ipv4.ip_forward
```

## 문제 해결

### 패키지 설치 실패

**증상**: 저장소를 찾을 수 없음

**해결**:
```bash
# 저장소 캐시 업데이트
sudo apt update    # Ubuntu/Debian
sudo yum update    # CentOS/RHEL
```

### 포트 충돌

**증상**: 포트가 이미 사용 중

**해결**:
```bash
# 포트 사용 확인
sudo netstat -tulpn | grep <port>

# 프로세스 종료
sudo kill -9 <pid>
```

### 권한 오류

**증상**: Permission denied

**해결**:
```bash
# sudo 사용 또는 root로 전환
sudo su -
```

## 추가 리소스

- [Kubernetes 공식 문서](https://kubernetes.io/docs/setup/)
- [Containerd 문서](https://containerd.io/)
- [Tailscale 설치 가이드](https://tailscale.com/kb/1031/install-linux/)

---

**최종 업데이트**: 2025-10-21  
**버전**: 1.0.0

