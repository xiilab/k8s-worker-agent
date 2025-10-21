# K8s VPN Agent - 설치 체크리스트

## 설치 전 확인 사항

### ✅ 시스템 요구사항

- [ ] **운영체제**: Ubuntu 20.04+, Debian 11+, CentOS 8+, RHEL 8+, Rocky 8+, Fedora 35+
- [ ] **CPU**: 2 cores 이상
- [ ] **메모리**: 2GB 이상 (4GB 권장)
- [ ] **디스크**: 20GB 이상 여유 공간

### ✅ 권한 확인

```bash
# Root 권한 확인
sudo whoami
# 출력: root
```

- [ ] Root 또는 sudo 권한 있음

### ✅ 네트워크 확인

```bash
# 인터넷 연결
ping -c 3 8.8.8.8

# DNS 확인
nslookup google.com

# 마스터 노드 연결 확인 (VPN 없이)
ping -c 3 <master-node-ip>
```

- [ ] 인터넷 연결 가능
- [ ] DNS 정상 작동
- [ ] 마스터 노드 접근 가능 (또는 VPN 필요 여부 확인)

### ✅ Swap 비활성화

```bash
# Swap 확인
swapon --show
# 출력이 비어있어야 함
```

- [ ] Swap 비활성화 됨

만약 Swap이 활성화되어 있다면:
```bash
sudo swapoff -a
sudo sed -i '/ swap / s/^/#/' /etc/fstab
```

### ✅ 방화벽 상태 확인

```bash
# UFW (Ubuntu/Debian)
sudo ufw status

# firewalld (CentOS/RHEL)
sudo firewall-cmd --state

# iptables
sudo iptables -L -n
```

- [ ] 방화벽 상태 확인 완료

### ✅ 마스터 노드 정보 준비

다음 정보를 마스터 노드에서 가져오세요:

```bash
# 마스터 노드에서 실행
kubeadm token create --print-join-command
```

- [ ] **마스터 IP**: `_________________`
- [ ] **Join Token**: `_________________`
- [ ] **CA Cert Hash**: `_________________`

### ✅ VPN 정보 준비 (필요한 경우)

- [ ] **VPN 타입**: Tailscale / Headscale
- [ ] **VPN 서버 URL**: `_________________`
- [ ] **Auth Key**: `_________________`

## 설치 단계

### 1️⃣ 저장소 복제

```bash
cd /root
git clone <repository-url> k8s-vpn-agent
cd k8s-vpn-agent
```

- [ ] 저장소 복제 완료

### 2️⃣ 시스템 의존성 설치

```bash
sudo ./scripts/install-dependencies.sh
```

**예상 소요 시간**: 5-10분

**설치되는 패키지**:
- Python 3.8+
- Containerd
- Kubernetes 도구 (kubeadm, kubelet, kubectl)
- 네트워크 도구

- [ ] 시스템 의존성 설치 완료

**확인**:
```bash
python3 --version
containerd --version
kubeadm version
kubelet --version
kubectl version --client
```

### 3️⃣ Python 에이전트 설치

```bash
sudo ./scripts/install-agent.sh
```

**예상 소요 시간**: 2-3분

**설치되는 항목**:
- Python 가상환경
- Python 패키지 (click, rich, pyyaml 등)
- k8s-vpn-agent CLI 도구

- [ ] Python 에이전트 설치 완료

**확인**:
```bash
source /root/k8s-vpn-agent/venv/bin/activate
k8s-vpn-agent --version
```

### 4️⃣ 설정 파일 생성

```bash
cp config/config.yaml.sample config/config.yaml
nano config/config.yaml  # 또는 vi
```

**필수 설정**:
```yaml
master:
  ip: "<마스터-노드-IP>"
  token: "<조인-토큰>"
  ca_cert_hash: "<CA-인증서-해시>"

vpn:
  enabled: true  # 또는 false
  type: "headscale"  # 또는 "tailscale"
  server_url: "<VPN-서버-URL>"
  auth_key: "<인증-키>"

firewall:
  enabled: true
```

- [ ] config.yaml 생성 및 편집 완료

### 5️⃣ 설정 검증

```bash
source venv/bin/activate
k8s-vpn-agent validate -c config/config.yaml
```

- [ ] 설정 검증 통과

### 6️⃣ 워커 노드 조인

```bash
k8s-vpn-agent join -c config/config.yaml --interactive
```

또는 비대화형 모드:
```bash
k8s-vpn-agent join -c config/config.yaml
```

**예상 소요 시간**: 5-10분

- [ ] 워커 노드 조인 완료

## 설치 후 확인

### ✅ 노드 상태 확인

마스터 노드에서:
```bash
kubectl get nodes
```

- [ ] 새 노드가 `Ready` 상태로 표시됨

### ✅ 에이전트 로그 확인

```bash
cat logs/k8s-vpn-agent.log
```

- [ ] 로그에 오류 없음

### ✅ VPN 연결 확인 (VPN 사용 시)

```bash
# Tailscale
tailscale status

# 마스터 노드로 ping
ping -c 3 <master-node-ip>
```

- [ ] VPN 연결 정상
- [ ] 마스터 노드 통신 가능

### ✅ 컨테이너 런타임 확인

```bash
sudo systemctl status containerd
sudo crictl ps
```

- [ ] Containerd 정상 실행

### ✅ Kubelet 확인

```bash
sudo systemctl status kubelet
sudo journalctl -u kubelet -f
```

- [ ] Kubelet 정상 실행

## 트러블슈팅 체크리스트

### ❌ 설치 스크립트 실패

- [ ] 인터넷 연결 확인
- [ ] 저장소 접근 가능 확인
- [ ] 디스크 공간 확인: `df -h`
- [ ] 로그 확인: `tail -f /tmp/install-*.log`

### ❌ 노드 조인 실패

- [ ] 마스터 노드 통신 확인
- [ ] Token 유효성 확인 (24시간 유효)
- [ ] CA cert hash 확인
- [ ] 방화벽 설정 확인
- [ ] VPN 연결 확인 (VPN 사용 시)

### ❌ 노드가 NotReady 상태

- [ ] CNI 플러그인 설치 확인 (마스터에서)
- [ ] Kubelet 로그 확인: `journalctl -u kubelet -f`
- [ ] 네트워크 설정 확인
- [ ] Containerd 상태 확인

### ❌ VPN 연결 실패

- [ ] VPN 서버 URL 확인
- [ ] Auth key 유효성 확인
- [ ] 방화벽에서 VPN 포트 열림 확인 (41641/udp)
- [ ] VPN 클라이언트 설치 확인: `tailscale version`

## 정리 (Cleanup)

설치를 취소하거나 재설치하려면:

```bash
# 에이전트 제거
cd /root/k8s-vpn-agent
sudo ./scripts/uninstall.sh  # (있는 경우)

# 수동 제거
sudo kubeadm reset -f
sudo apt remove -y kubeadm kubelet kubectl containerd.io  # Ubuntu/Debian
sudo rm -rf /etc/kubernetes/ /var/lib/kubelet/ /var/lib/etcd/
sudo rm -rf /root/k8s-vpn-agent
```

## 참고 문서

- [PREREQUISITES.md](./PREREQUISITES.md) - 사전 요구사항 상세
- [PACKAGE_LIST.md](./PACKAGE_LIST.md) - 패키지 목록
- [USER_MANUAL.md](./USER_MANUAL.md) - 사용자 매뉴얼
- [QUICKSTART.md](../QUICKSTART.md) - 빠른 시작 가이드

---

**작성일**: 2025-10-21  
**버전**: 1.0.0
