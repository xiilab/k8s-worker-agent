# K8s VPN Agent 사용자 매뉴얼

## 목차

1. [소개](#소개)
2. [설치 가이드](#설치-가이드)
3. [설정 가이드](#설정-가이드)
4. [실행 가이드](#실행-가이드)
5. [트러블슈팅](#트러블슈팅)
6. [고급 기능](#고급-기능)

## 소개

K8s VPN Agent는 서로 다른 네트워크망에 있는 워커노드를 Kubernetes 클러스터에 쉽게 추가할 수 있도록 도와주는 자동화 도구입니다.

### 주요 특징

- **자동화**: 패키지 설치, 방화벽 설정, VPN 연결 등 모든 과정 자동화
- **안전성**: Idempotent 설계와 자동 롤백 기능으로 안전한 운영
- **유연성**: 다양한 OS 및 네트워크 환경 지원
- **사용자 친화**: CLI 기반의 직관적인 인터페이스

## 설치 가이드

### 사전 요구사항

- Root 권한
- 인터넷 연결
- Python 3.8 이상
- 2GB 이상의 메모리
- 20GB 이상의 디스크 공간

### 📦 설치될 패키지 정보

설치 스크립트가 자동으로 다음 패키지를 설치합니다:

**시스템 기본 패키지**:
- curl, wget, git, jq
- net-tools, ipset, ipvsadm, socat, conntrack
- Python 3.8+ (python3, python3-pip, python3-venv)

**Kubernetes 도구**:
- kubeadm v1.30.x (조인용)
- kubelet v1.30.x (필수)

**컨테이너 런타임**:
- Containerd (Docker 저장소)

**VPN 클라이언트**:
- Tailscale (필요 시 자동 설치)

📚 **상세 정보**: 
- [PREREQUISITES.md](./PREREQUISITES.md) - 사전 요구사항 및 수동 설치 가이드
- [PACKAGE_LIST.md](./PACKAGE_LIST.md) - 패키지 목록 빠른 참조
- [INSTALLATION_CHECKLIST.md](./INSTALLATION_CHECKLIST.md) - 설치 체크리스트

### Step 1: 프로젝트 다운로드

```bash
cd /root
# 프로젝트를 다운로드하거나 복사
```

### Step 2: 시스템 의존성 설치

```bash
cd /root/k8s-vpn-agent
sudo ./scripts/install-dependencies.sh
```

이 스크립트는 다음을 설치합니다:
- Kubernetes 도구 (kubeadm, kubelet, kubectl)
- Containerd 컨테이너 런타임
- 필수 시스템 패키지

**소요 시간**: 약 5-10분

### Step 3: 에이전트 설치

```bash
sudo ./scripts/install-agent.sh
```

이 스크립트는 다음을 수행합니다:
- Python 가상환경 생성
- Python 패키지 설치
- 샘플 설정 파일 생성

**소요 시간**: 약 2-3분

## 설정 가이드

### 설정 파일 생성

#### 방법 1: 샘플 파일 복사

```bash
cp config/config.yaml.sample config/config.yaml
vi config/config.yaml
```

#### 방법 2: CLI 명령어 사용

```bash
source venv/bin/activate
k8s-vpn-agent init config/config.yaml
```

### 필수 설정 항목

#### 1. 마스터 노드 정보

마스터 노드에서 다음 명령어를 실행하여 정보를 확인합니다:

```bash
# 조인 명령어 생성
kubeadm token create --print-join-command
```

출력 예시:
```
kubeadm join 10.0.1.100:6443 --token abcdef.0123456789abcdef \
    --discovery-token-ca-cert-hash sha256:1234567890abcdef...
```

이 정보를 config.yaml에 입력:

```yaml
master:
  ip: "10.0.1.100"
  api_endpoint: "https://10.0.1.100:6443"
  token: "abcdef.0123456789abcdef"
  ca_cert_hash: "sha256:1234567890abcdef..."
```

#### 2. VPN 설정 (선택사항)

마스터 노드와 직접 통신이 불가능한 경우에만 필요합니다.

**Headscale 서버에서 Pre-auth key 생성:**

```bash
headscale preauthkeys create --namespace default
```

config.yaml에 입력:

```yaml
vpn:
  enabled: true
  type: "headscale"
  headscale_url: "https://headscale.example.com"
  auth_key: "your-pre-auth-key-here"
```

**VPN이 필요없는 경우:**

```yaml
vpn:
  enabled: false
```

#### 3. 워커 노드 설정

```yaml
worker:
  hostname: "worker-01"  # 비워두면 자동 생성
  labels:
    - "network=vpn"
    - "environment=production"
  taints: []
```

### 설정 파일 검증

```bash
k8s-vpn-agent validate --config config/config.yaml
```

## 실행 가이드

### 기본 실행

```bash
source venv/bin/activate
k8s-vpn-agent join --config config/config.yaml
```

### 대화형 모드

설정 파일 없이 대화형으로 실행:

```bash
k8s-vpn-agent join --interactive
```

질문에 답변하면서 진행합니다:
1. 마스터 노드 IP
2. API 엔드포인트
3. Kubeadm 토큰
4. CA 인증서 해시
5. VPN 사용 여부
6. Headscale URL (VPN 사용 시)

### 디버그 모드

문제 해결을 위한 상세 로그:

```bash
k8s-vpn-agent join --config config/config.yaml --debug
```

### 실행 과정

에이전트는 다음 단계를 자동으로 수행합니다:

1. **네트워크 체크**: 마스터 노드 연결 확인
2. **VPN 설정**: 필요시 VPN 연결
3. **방화벽 설정**: 필요한 포트 자동 개방
4. **의존성 확인**: K8s 도구 설치 확인
5. **호스트명 설정**: 워커 노드 호스트명 설정
6. **Kubelet 설정**: Kubelet 구성
7. **클러스터 조인**: K8s 클러스터에 조인
8. **상태 확인**: 노드 상태 검증

### 결과 확인

#### 워커 노드에서

```bash
# Kubelet 상태 확인
systemctl status kubelet

# VPN 상태 확인 (VPN 사용 시)
tailscale status
```

#### 마스터 노드에서

```bash
# 노드 목록 확인
kubectl get nodes

# 노드 상세 정보
kubectl get nodes -o wide

# 노드 상태 확인
kubectl describe node <worker-node-name>
```

## 트러블슈팅

### 문제 1: VPN 연결 실패

**증상:**
```
✗ VPN 연결 실패: auth key required
```

**해결방법:**

1. Headscale 서버에서 Pre-auth key 생성:
```bash
headscale preauthkeys create --namespace default
```

2. config.yaml에 auth_key 추가:
```yaml
vpn:
  auth_key: "생성된-키-입력"
```

3. 재실행:
```bash
k8s-vpn-agent join --config config/config.yaml
```

### 문제 2: 클러스터 조인 실패

**증상:**
```
✗ 클러스터 조인 실패: token expired
```

**해결방법:**

1. 마스터 노드에서 새 토큰 생성:
```bash
kubeadm token create --print-join-command
```

2. config.yaml 업데이트

3. 워커 노드 리셋 (필요시):
```bash
kubeadm reset -f
```

4. 재실행

### 문제 3: 방화벽 문제

**증상:**
```
✗ 6443 포트 연결 실패
```

**해결방법:**

1. 방화벽 상태 확인:
```bash
# UFW
sudo ufw status

# firewalld
sudo firewall-cmd --list-all
```

2. 수동으로 포트 열기:
```bash
# UFW
sudo ufw allow 6443/tcp
sudo ufw allow 41641/udp

# firewalld
sudo firewall-cmd --permanent --add-port=6443/tcp
sudo firewall-cmd --permanent --add-port=41641/udp
sudo firewall-cmd --reload
```

### 문제 4: 의존성 누락

**증상:**
```
✗ kubeadm이 설치되지 않았습니다.
```

**해결방법:**

```bash
# 의존성 재설치
sudo ./scripts/install-dependencies.sh
```

### 로그 확인

```bash
# 최신 로그 파일 확인
ls -lt /var/log/k8s-vpn-agent/

# 메인 로그 보기
tail -f /var/log/k8s-vpn-agent/agent_*.log

# 에러 로그 보기
tail -f /var/log/k8s-vpn-agent/error_*.log

# Kubelet 로그
journalctl -u kubelet -f
```

## 고급 기능

### Idempotent 실행

에이전트는 idempotent하므로 여러 번 실행해도 안전합니다:

```bash
# 첫 실행
k8s-vpn-agent join --config config/config.yaml

# 재실행 (이미 조인된 경우 스킵)
k8s-vpn-agent join --config config/config.yaml
```

### 자동 롤백

실패 시 자동으로 이전 상태로 복구:

```yaml
agent:
  rollback_on_failure: true  # 기본값
```

롤백 기능:
- VPN 연결 실패 → VPN 설정 제거
- 클러스터 조인 실패 → 모든 변경사항 롤백

### 커스텀 레이블

워커 노드에 커스텀 레이블 추가:

```yaml
worker:
  labels:
    - "environment=production"
    - "workload=gpu"
    - "region=asia"
```

마스터에서 확인:
```bash
kubectl get nodes --show-labels
```

### 노드 테인트

특정 워크로드만 스케줄되도록 테인트 설정:

```yaml
worker:
  taints:
    - "dedicated=gpu:NoSchedule"
```

### 방화벽 커스텀 포트

추가 포트 개방:

```yaml
firewall:
  enabled: true
  additional_ports:
    - "8080/tcp"
    - "9090/tcp"
```

### 로그 레벨 조정

```yaml
agent:
  log_level: "DEBUG"  # DEBUG, INFO, WARN, ERROR
```

### 헬스체크 간격 조정

```yaml
agent:
  health_check_interval: 60  # 초 단위
```

## 베스트 프랙티스

### 1. 설정 파일 버전 관리

```bash
# Git에 설정 파일 저장 (민감 정보 제외)
git add config/config.yaml
git commit -m "Add k8s-vpn-agent config"
```

### 2. 주기적인 상태 확인

```bash
# Cron job으로 정기 체크
# /etc/cron.d/k8s-health-check
*/30 * * * * root kubectl get nodes | grep NotReady && alert-admin
```

### 3. 로그 로테이션

```bash
# /etc/logrotate.d/k8s-vpn-agent
/var/log/k8s-vpn-agent/*.log {
    daily
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 root root
}
```

### 4. 백업

```bash
# 중요 파일 백업
tar czf k8s-vpn-agent-backup.tar.gz \
    /etc/kubernetes/kubelet.conf \
    /root/k8s-vpn-agent/config/config.yaml
```

## FAQ

**Q: VPN 없이 사용할 수 있나요?**

A: 네, 마스터 노드와 직접 통신이 가능하다면 `vpn.enabled: false`로 설정하세요.

**Q: 여러 워커 노드를 추가하려면?**

A: 각 워커 노드에서 에이전트를 실행하되, `worker.hostname`을 다르게 설정하세요.

**Q: 실패 후 재시도하려면?**

A: 단순히 다시 실행하면 됩니다. Idempotent 설계로 안전합니다.

**Q: 노드를 제거하려면?**

A: 마스터에서 `kubectl drain <node-name>` 후 `kubectl delete node <node-name>`, 워커에서 `kubeadm reset -f`

## 지원

문의 사항이나 버그 리포트는 프로젝트 저장소의 Issues를 이용해주세요.

---

**버전**: 1.0.0  
**최종 업데이트**: 2025-10-21

