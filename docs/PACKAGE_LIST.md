# K8s VPN Agent - 패키지 목록

## 빠른 참조

### Ubuntu/Debian 패키지
```bash
# APT 패키지
apt-transport-https
ca-certificates
curl
gnupg
lsb-release
software-properties-common
python3
python3-pip
python3-venv
net-tools
ipset
ipvsadm
socat
conntrack
jq
wget
git
containerd.io          # Docker 저장소에서
kubelet               # Kubernetes 저장소에서
kubeadm               # Kubernetes 저장소에서
kubectl               # Kubernetes 저장소에서
```

### CentOS/RHEL/Rocky 패키지
```bash
# YUM/DNF 패키지
yum-utils
device-mapper-persistent-data
lvm2
python3
python3-pip
net-tools
ipset
ipvsadm
socat
conntrack
jq
wget
git
containerd.io         # Docker 저장소에서
kubelet              # Kubernetes 저장소에서
kubeadm              # Kubernetes 저장소에서
kubectl              # Kubernetes 저장소에서
```

### Python 패키지 (requirements.txt)
```
click>=8.1.7
rich>=13.7.0
pyyaml>=6.0.1
requests>=2.31.0
python-dotenv>=1.0.0
psutil>=5.9.6
tabulate>=0.9.0
jinja2>=3.1.2
```

## 패키지 용도

### 시스템 유틸리티
| 패키지 | 용도 |
|--------|------|
| curl | HTTP 요청, 스크립트 다운로드 |
| wget | 파일 다운로드 |
| git | 버전 관리 |
| jq | JSON 파싱 |

### 네트워크 도구
| 패키지 | 용도 |
|--------|------|
| net-tools | ifconfig, netstat 등 |
| ipset | IP 세트 관리 |
| ipvsadm | IPVS 관리 |
| socat | 소켓 통신 |
| conntrack | 연결 추적 |

### Python 환경
| 패키지 | 용도 |
|--------|------|
| python3 | Python 인터프리터 |
| python3-pip | Python 패키지 관리자 |
| python3-venv | 가상환경 |

### Kubernetes
| 패키지 | 버전 | 용도 |
|--------|------|------|
| kubeadm | 1.30.x | 클러스터 조인 (워커 노드) |
| kubelet | 1.30.x | 노드 에이전트 (필수) |

### 컨테이너 런타임
| 패키지 | 용도 |
|--------|------|
| cri-o | 컨테이너 런타임 (OCI 기반) |
| cri-o-runc | OCI 런타임 |

## 저장소 정보

### Docker 저장소 (Containerd)

**Ubuntu/Debian**:
```
https://download.docker.com/linux/ubuntu
https://download.docker.com/linux/debian
```

**CentOS/RHEL**:
```
https://download.docker.com/linux/centos
```

### Kubernetes 저장소

**모든 OS**:
```
https://pkgs.k8s.io/core:/stable:/v1.30/deb/    # Debian/Ubuntu
https://pkgs.k8s.io/core:/stable:/v1.30/rpm/    # CentOS/RHEL/Fedora
```

### Tailscale 저장소

**자동 설치 스크립트**:
```
https://tailscale.com/install.sh
```

## 디스크 공간 요구사항

| 구성요소 | 공간 |
|----------|------|
| 시스템 패키지 | ~500MB |
| Python 패키지 | ~100MB |
| Containerd | ~200MB |
| Kubernetes 도구 | ~300MB |
| 컨테이너 이미지 | ~2-5GB |
| 로그 및 데이터 | ~1GB |
| **총계** | **~5-10GB** |

여유 공간 20GB 이상 권장

## 설치 순서

1. **시스템 패키지** (5-10분)
   ```bash
   ./scripts/install-dependencies.sh
   ```

2. **Python 패키지** (2-3분)
   ```bash
   ./scripts/install-agent.sh
   ```

3. **VPN 클라이언트** (자동)
   - 에이전트 실행 시 필요하면 자동 설치

## 오프라인 설치

인터넷이 없는 환경에서는 다음을 준비하세요:

### 1. 패키지 다운로드
```bash
# Ubuntu/Debian
apt-get download <package-list>

# CentOS/RHEL
yumdownloader <package-list>
```

### 2. Python 패키지 다운로드
```bash
pip download -r requirements.txt -d packages/
```

### 3. 오프라인 설치
```bash
# APT
sudo dpkg -i *.deb
sudo apt-get install -f

# YUM
sudo rpm -ivh *.rpm

# Python
pip install --no-index --find-links=packages/ -r requirements.txt
```

## 정리 (Cleanup)

불필요한 패키지 제거:

```bash
# Ubuntu/Debian
sudo apt autoremove
sudo apt autoclean

# CentOS/RHEL
sudo yum autoremove
sudo yum clean all
```

---

**참고**: 정확한 패키지 버전은 설치 시점에 따라 다를 수 있습니다.
