# K8s VPN Agent - 빠른 시작 가이드

## 사전 요구사항

### 시스템
- Linux 서버 (Ubuntu 22.04+, Debian 11+, CentOS 8+, RHEL 8+)
- Root 또는 sudo 권한
- 인터넷 연결
- 마스터 노드의 join token 및 CA cert hash

### 자동 설치될 패키지
설치 스크립트가 자동으로 설치:
- **Python 3.8+**, pip, venv
- **Kubernetes 도구**: kubeadm, kubelet, kubectl v1.28.x
- **Containerd**: 컨테이너 런타임
- **네트워크 도구**: net-tools, ipset, socat 등

📦 **상세 정보**: [docs/PREREQUISITES.md](docs/PREREQUISITES.md), [docs/PACKAGE_LIST.md](docs/PACKAGE_LIST.md)

---

## 3분 안에 시작하기

### 1단계: 의존성 설치 (5-10분)

```bash
cd /root/k8s-vpn-agent
sudo ./scripts/install-dependencies.sh
```

### 2단계: 에이전트 설치 (2-3분)

```bash
sudo ./scripts/install-agent.sh
```

### 3단계: 설정 파일 생성

```bash
cp config/config.yaml.sample config/config.yaml
vi config/config.yaml
```

**필수 설정 항목:**
- `master.ip`: 마스터 노드 IP
- `master.token`: kubeadm 토큰
- `master.ca_cert_hash`: CA 해시

**마스터 노드에서 토큰 확인:**
```bash
kubeadm token create --print-join-command
```

### 4단계: 실행

```bash
source venv/bin/activate
k8s-vpn-agent join --config config/config.yaml
```

## 대화형 모드 (설정 파일 없이)

```bash
source venv/bin/activate
k8s-vpn-agent join --interactive
```

## 디버그 모드

```bash
k8s-vpn-agent join --config config/config.yaml --debug
```

## 결과 확인

**워커 노드에서:**
```bash
systemctl status kubelet
```

**마스터 노드에서:**
```bash
kubectl get nodes
```

## 문제 해결

로그 확인:
```bash
tail -f /var/log/k8s-vpn-agent/agent_*.log
```

상세 매뉴얼:
```bash
cat docs/USER_MANUAL.md
```

---

더 자세한 내용은 [README.md](README.md)와 [USER_MANUAL.md](docs/USER_MANUAL.md)를 참고하세요.
