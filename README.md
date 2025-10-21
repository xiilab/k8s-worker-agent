# K8s VPN Worker Node Agent

서로 다른 네트워크망에 있는 워커노드를 VPN(Headscale/Tailscale)을 통해 Kubernetes 클러스터에 추가하는 자동화 에이전트입니다.

## 주요 기능

### 1. 자동화
- ✅ OS 자동 감지 (Ubuntu, Debian, CentOS, RHEL, Rocky, Fedora)
- ✅ 패키지 자동 설치 (apt, yum, dnf)
- ✅ Python venv 자동 활성화
- ✅ 방화벽 자동 설정 (UFW, firewalld, iptables)

### 2. VPN 지원
- ✅ Headscale 기반 VPN 연결
- ✅ Tailscale 지원
- ✅ 마스터 노드와 직접 통신 가능 시 VPN 자동 스킵
- ✅ VPN 연결 상태 모니터링

### 3. 안정성
- ✅ Idempotent 설계 (재실행 시 중복 작업 방지)
- ✅ 자동 롤백 기능 (실패 시 원상 복구)
- ✅ 상세한 로깅 시스템
- ✅ 디버그 모드 지원

### 4. 보안
- ✅ TLS 인증서/토큰 자동 관리
- ✅ 방화벽 규칙 자동 설정
- ✅ 네트워크 헬스체크

### 5. 사용자 경험
- ✅ CLI 형태 제공 (Click 기반)
- ✅ Rich 라이브러리를 활용한 컬러풀한 출력
- ✅ 대화형 모드 지원
- ✅ 설정 파일 유효성 검사

## 시스템 요구사항

### 하드웨어
- **CPU**: 2 cores 이상
- **Memory**: 2GB 이상 (4GB 권장)
- **Disk**: 20GB 이상의 여유 공간

### 운영체제
- Ubuntu 20.04, 22.04, 24.04
- Debian 11, 12
- CentOS 8, 9
- RHEL 8, 9
- Rocky Linux 8, 9
- Fedora 35+

### 필수 패키지
설치 스크립트가 자동으로 설치하는 패키지:

**시스템 기본**:
- Python 3.8+, pip, venv
- curl, wget, git, jq
- net-tools, ipset, ipvsadm, socat, conntrack

**Kubernetes**:
- kubeadm v1.28.x
- kubelet v1.28.x
- kubectl v1.28.x

**컨테이너 런타임**:
- CRI-O v1.28.x (Kubelet과 자동 연동)

**VPN**:
- Tailscale/Headscale (에이전트 실행 시 자동 설치)

**상세 패키지 정보**: [docs/PREREQUISITES.md](docs/PREREQUISITES.md)

## 설치 방법

### 1. 시스템 의존성 설치

```bash
cd /root/k8s-vpn-agent
sudo ./scripts/install-dependencies.sh
```

이 스크립트는 다음을 자동으로 설치합니다:
- Python3, pip, venv
- Kubernetes 도구 (kubeadm, kubelet, kubectl)
- Containerd
- 필수 네트워크 도구

### 2. 에이전트 설치

```bash
sudo ./scripts/install-agent.sh
```

이 스크립트는 다음을 수행합니다:
- Python 가상환경 생성
- 필요한 Python 패키지 설치
- 샘플 설정 파일 생성

## 사용 방법

### 1. 설정 파일 준비

#### 방법 A: 샘플 파일 복사

```bash
cp config/config.yaml.sample config/config.yaml
vi config/config.yaml
```

#### 방법 B: CLI로 생성

```bash
source venv/bin/activate
k8s-vpn-agent init config/config.yaml
```

### 2. 마스터 노드에서 토큰 생성

마스터 노드에서 다음 명령어를 실행하여 조인 토큰과 CA 해시를 확인합니다:

```bash
# 토큰 생성
kubeadm token create --print-join-command

# 출력 예시:
# kubeadm join 10.0.1.100:6443 --token abcdef.0123456789abcdef \
#     --discovery-token-ca-cert-hash sha256:1234567890abcdef...
```

### 3. Headscale 설정 (VPN 사용 시)

Headscale 서버에서 Pre-authentication key를 생성합니다:

```bash
headscale preauthkeys create --namespace default
```

### 4. 에이전트 실행

#### 방법 A: 설정 파일 사용

```bash
source venv/bin/activate
k8s-vpn-agent join --config config/config.yaml
```

#### 방법 B: 대화형 모드

```bash
source venv/bin/activate
k8s-vpn-agent join --interactive
```

#### 방법 C: 디버그 모드

```bash
k8s-vpn-agent join --config config/config.yaml --debug
```

### 5. 설정 파일 검증

```bash
k8s-vpn-agent validate --config config/config.yaml
```

## 설정 파일 예제

```yaml
# 필수 설정
master:
  ip: "10.0.1.100"
  api_endpoint: "https://10.0.1.100:6443"
  token: "abcdef.0123456789abcdef"
  ca_cert_hash: "sha256:1234567890abcdef..."

# VPN 설정 (선택사항)
vpn:
  enabled: true
  type: "headscale"
  headscale_url: "https://headscale.example.com"
  auth_key: "your-pre-auth-key"

# 워커 노드 설정
worker:
  hostname: "worker-01"
  labels:
    - "network=vpn"
    - "zone=remote"
```

## CLI 명령어

### join - 클러스터에 조인

```bash
k8s-vpn-agent join [OPTIONS]

Options:
  -c, --config PATH    설정 파일 경로
  -i, --interactive    대화형 모드
  --debug              디버그 모드
  --help               도움말 표시
```

### init - 샘플 설정 파일 생성

```bash
k8s-vpn-agent init [OUTPUT]

Arguments:
  OUTPUT  출력 파일 경로 (기본값: ./config.yaml)
```

### validate - 설정 파일 검증

```bash
k8s-vpn-agent validate [OPTIONS]

Options:
  -c, --config PATH    설정 파일 경로
```

## 로그 파일

에이전트는 다음 위치에 로그를 저장합니다:

- 메인 로그: `/var/log/k8s-vpn-agent/agent_YYYYMMDD_HHMMSS.log`
- 에러 로그: `/var/log/k8s-vpn-agent/error_YYYYMMDD_HHMMSS.log`

디버그 모드에서는 더 상세한 로그가 기록됩니다.

## 트러블슈팅

### 1. VPN 연결 실패

**증상**: VPN 연결이 실패합니다.

**해결방법**:
- Headscale 서버 URL이 올바른지 확인
- Pre-authentication key가 유효한지 확인
- 방화벽에서 VPN 포트(41641)가 열려있는지 확인

```bash
# VPN 상태 확인
tailscale status

# 방화벽 확인 (UFW)
sudo ufw status

# 방화벽 확인 (firewalld)
sudo firewall-cmd --list-all
```

### 2. 클러스터 조인 실패

**증상**: 클러스터 조인이 실패합니다.

**해결방법**:
- 토큰이 유효한지 확인 (마스터에서: `kubeadm token list`)
- CA 인증서 해시가 올바른지 확인
- 마스터 노드 API 서버에 접근 가능한지 확인

```bash
# 네트워크 연결 확인
ping <master-ip>
nc -zv <master-ip> 6443

# Kubelet 로그 확인
journalctl -u kubelet -f
```

### 3. 롤백

실패 후 롤백이 필요한 경우:

```bash
# K8s 노드 리셋
sudo kubeadm reset -f

# VPN 연결 해제
sudo tailscale down
```

## 고급 기능

### Idempotent 실행

에이전트는 idempotent하게 설계되어 있어 여러 번 실행해도 안전합니다:

```bash
# 첫 번째 실행
k8s-vpn-agent join --config config.yaml

# 재실행 (중복 작업 없이 상태 확인)
k8s-vpn-agent join --config config.yaml
```

### 롤백 기능

실패 시 자동 롤백이 활성화되어 있습니다 (`rollback_on_failure: true`):

- VPN 연결 실패 → VPN 설정 롤백
- 클러스터 조인 실패 → 모든 설정 롤백

### 커스텀 레이블 및 테인트

```yaml
worker:
  labels:
    - "environment=production"
    - "workload=gpu"
  taints:
    - "dedicated=gpu:NoSchedule"
```

## 개발

### 테스트

```bash
# 유닛 테스트
python -m pytest tests/

# 설정 검증
k8s-vpn-agent validate --config config/config.yaml
```

### 디버그

```bash
# 디버그 모드로 실행
k8s-vpn-agent join --config config/config.yaml --debug

# 로그 레벨 변경
# config.yaml에서:
agent:
  log_level: "DEBUG"
```

## 라이선스

MIT License

## 지원

문제가 발생하면 다음을 확인하세요:

1. 로그 파일: `/var/log/k8s-vpn-agent/`
2. Kubelet 로그: `journalctl -u kubelet -f`
3. 네트워크 연결성: `ping <master-ip>`

## 기여

Pull Request는 언제나 환영합니다!

## 📚 문서

### 시작하기
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작 가이드 (3분 안에 시작)
- [USER_MANUAL.md](docs/USER_MANUAL.md) - 상세 사용 가이드

### 설치 및 요구사항
- [PREREQUISITES.md](docs/PREREQUISITES.md) - 사전 요구사항 및 수동 설치
- [PACKAGE_LIST.md](docs/PACKAGE_LIST.md) - 패키지 목록 빠른 참조
- [INSTALLATION_CHECKLIST.md](docs/INSTALLATION_CHECKLIST.md) - 설치 체크리스트

### 아키텍처 및 개발
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - 시스템 아키텍처

## 참고 자료

- [Kubernetes 공식 문서](https://kubernetes.io/docs/)
- [Headscale](https://github.com/juanfont/headscale)
- [Tailscale](https://tailscale.com/)

