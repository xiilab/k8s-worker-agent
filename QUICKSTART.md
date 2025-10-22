# K8s VPN Agent - 빠른 시작 가이드

## 사전 요구사항

### 시스템
- Linux 서버 (Ubuntu 22.04+, Debian 11+, CentOS 8+, RHEL 8+)
- Root 또는 sudo 권한
- 인터넷 연결
- **마스터 노드에서 발급받은 join token 및 CA cert hash**

### 자동 설치될 패키지
설치 스크립트가 자동으로 설치:
- **Python 3.8+**, pip, venv
- **Kubernetes 도구**: kubeadm, kubelet v1.30.x
- **Containerd**: 컨테이너 런타임
- **네트워크 도구**: net-tools, ipset, socat 등

📦 **상세 정보**: [docs/PREREQUISITES.md](docs/PREREQUISITES.md), [docs/PACKAGE_LIST.md](docs/PACKAGE_LIST.md)

---

## ⚠️ 시작하기 전에: 토큰 발급

**반드시 마스터 노드에서 먼저 토큰을 발급받으세요!**

마스터 노드에서 다음 명령을 실행:

```bash
kubeadm token create --print-join-command
```

출력 예시:
```
kubeadm join 10.0.1.100:6443 --token abcdef.0123456789abcdef \
    --discovery-token-ca-cert-hash sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

여기서:
- **마스터 IP**: `10.0.1.100`
- **토큰**: `abcdef.0123456789abcdef`
- **CA 해시**: `sha256:1234...`

📖 **자세한 방법**: [docs/TOKEN_GUIDE.md](docs/TOKEN_GUIDE.md)

---

## 방법 1: 원클릭 설치 (권장) ⭐

### 1단계: 스크립트 편집

토큰 발급 후, 스크립트에 정보를 입력합니다:

```bash
cd /root/k8s-vpn-agent
vi quick-setup.sh
```

**스크립트 상단을 수정:**
```bash
# ================================================================
# 설정 (여기를 수정하세요)
# ================================================================
MASTER_IP="10.0.1.100"          # ← 여기 수정
JOIN_TOKEN="abcdef.0123..."     # ← 여기 수정
CA_CERT_HASH="sha256:1234..."   # ← 여기 수정
VPN_ENABLED="false"             # VPN 사용하면 "true"
# ================================================================
```

### 2단계: 실행

```bash
sudo ./quick-setup.sh
```

스크립트가 자동으로:
1. ✅ 시스템 의존성 설치
2. ✅ Python 에이전트 설치
3. ✅ 설정 파일 생성
4. ✅ 설정 검증
5. ✅ 클러스터 조인

**끝! 🎉**

---

## 방법 2: 단계별 설치

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

**필수 설정 항목 수정:**
```yaml
master:
  ip: "10.0.1.100"                  # ← 마스터 IP
  token: "abcdef.0123456789abcdef"  # ← 토큰
  ca_cert_hash: "sha256:1234..."    # ← CA 해시
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
