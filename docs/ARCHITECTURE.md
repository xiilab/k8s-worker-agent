# K8s VPN Agent - 아키텍처 문서

## 개요

K8s VPN Agent는 서로 다른 네트워크망에 있는 워커노드를 Kubernetes 클러스터에 안전하게 추가하기 위한 자동화 에이전트입니다.

## 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                    K8s VPN Agent                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐      ┌──────────────┐                   │
│  │  CLI Layer   │──────│   Logging    │                   │
│  │  (Click)     │      │   System     │                   │
│  └──────────────┘      └──────────────┘                   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────┐                 │
│  │     Orchestrator                     │                 │
│  │  (Execution Flow & State Management) │                 │
│  └──────────────────────────────────────┘                 │
│         │                                                   │
│         ├─────────────┬─────────────┬──────────────┐      │
│         ▼             ▼             ▼              ▼      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Network  │  │   VPN    │  │   K8s    │  │Firewall  │ │
│  │ Checker  │  │ Manager  │  │ Manager  │  │ Manager  │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│       │              │              │              │       │
└───────┼──────────────┼──────────────┼──────────────┼───────┘
        │              │              │              │
        ▼              ▼              ▼              ▼
┌─────────────────────────────────────────────────────────────┐
│               External Dependencies                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Ping    │  │Tailscale │  │ kubeadm  │  │   UFW    │  │
│  │  nc      │  │Headscale │  │ kubectl  │  │firewalld │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 핵심 모듈

### 1. CLI Layer (`cli.py`)

**책임**:
- 사용자 인터페이스 제공
- 명령어 파싱 및 검증
- 대화형 모드 지원

**주요 기능**:
- `join`: 워커노드 추가
- `init`: 설정 파일 생성
- `validate`: 설정 검증

### 2. Orchestrator

**책임**:
- 전체 실행 흐름 관리
- 모듈 간 조율
- 상태 관리 및 롤백

**실행 순서**:
1. 네트워크 연결성 체크
2. VPN 설정 (필요시)
3. 방화벽 설정
4. K8s 의존성 확인
5. 호스트명 설정
6. Kubelet 설정
7. 클러스터 조인
8. 상태 검증

### 3. Config Manager (`config.py`)

**책임**:
- 설정 파일 관리 (YAML/JSON)
- 기본값 제공
- 설정 검증

**데이터 구조**:
```python
- MasterConfig: 마스터 노드 정보
- VPNConfig: VPN 설정
- WorkerConfig: 워커 노드 설정
- NetworkConfig: 네트워크 설정
- FirewallConfig: 방화벽 설정
- AgentConfig: 에이전트 설정
- RuntimeConfig: 컨테이너 런타임 설정
```

### 4. Network Checker (`network.py`)

**책임**:
- 네트워크 연결성 검증
- 포트 체크
- DNS 체크

**주요 메서드**:
- `check_ping()`: ICMP 연결 테스트
- `check_port()`: TCP 포트 연결 테스트
- `check_dns()`: DNS 조회 테스트
- `check_interface()`: 네트워크 인터페이스 상태 확인

### 5. VPN Manager (`vpn.py`)

**책임**:
- VPN 클라이언트 설치
- VPN 연결 관리
- 상태 모니터링
- 롤백 지원

**특징**:
- Headscale/Tailscale 지원
- Idempotent 설계
- 자동 재연결

### 6. K8s Manager (`k8s.py`)

**책임**:
- Kubernetes 도구 관리
- 클러스터 조인
- 노드 상태 관리
- 롤백 지원

**특징**:
- Idempotent 설계
- 자동 호스트명 설정
- Kubelet 자동 설정

### 7. Firewall Manager (`firewall.py`)

**책임**:
- 방화벽 타입 자동 감지
- 방화벽 규칙 설정
- 롤백 지원

**지원 방화벽**:
- UFW (Ubuntu/Debian)
- firewalld (CentOS/RHEL/Fedora)
- iptables (범용)

### 8. Logger (`logger.py`)

**책임**:
- 로깅 시스템 관리
- 파일/콘솔 로깅
- 디버그 모드 지원

**로그 파일**:
- 메인 로그: `/var/log/k8s-vpn-agent/agent_*.log`
- 에러 로그: `/var/log/k8s-vpn-agent/error_*.log`

## 데이터 흐름

### 1. 설정 로드

```
config.yaml → Config.load() → dataclass objects
```

### 2. 네트워크 체크

```
NetworkChecker.comprehensive_check()
  ├─ check_ping(master_ip)
  ├─ check_port(master_ip, 6443)
  ├─ check_dns()
  └─ check_interface(vpn_interface)
```

### 3. VPN 연결 (필요시)

```
VPNManager.connect()
  ├─ save_state()
  ├─ is_connected() [idempotent check]
  ├─ install_client()
  ├─ tailscale up --login-server <headscale>
  └─ enable_autostart()
```

### 4. 방화벽 설정

```
FirewallManager.configure()
  ├─ save_state()
  ├─ detect_firewall()
  └─ _configure_xxx()
      ├─ VPN port
      ├─ K8s API port
      ├─ Kubelet port
      └─ NodePort range
```

### 5. K8s 조인

```
K8sManager.join_cluster()
  ├─ save_state()
  ├─ check_existing_membership() [idempotent check]
  ├─ setup_hostname()
  ├─ configure_kubelet()
  └─ kubeadm join ...
```

## 상태 관리 및 롤백

### 상태 저장

각 매니저는 작업 전 현재 상태를 저장:

```python
def save_state(self):
    self.original_state = {
        "current_config": ...,
        "is_connected": ...,
        "is_joined": ...
    }
```

### 롤백 메커니즘

실패 시 역순으로 롤백:

```
K8sManager.rollback()
  ├─ kubeadm reset -f
  ├─ restore hostname
  └─ clean up configs

VPNManager.rollback()
  ├─ tailscale down
  └─ remove configs

FirewallManager.rollback()
  └─ iptables-restore
```

## Idempotent 설계

### 원칙

모든 작업은 여러 번 실행해도 동일한 결과:

```python
def operation(self):
    if already_done():
        return True, "Already done"
    
    do_operation()
    return True, "Done"
```

### 구현 예시

**VPN 연결**:
```python
if self.is_connected():
    return True, "Already connected"
```

**K8s 조인**:
```python
if self.check_existing_membership():
    return True, "Already joined"
```

## 에러 처리 전략

### 1. 즉시 실패 (Fail Fast)

치명적 오류는 즉시 중단:
- 필수 의존성 누락
- 설정 파일 불완전

### 2. 재시도 (Retry)

일시적 오류는 재시도:
- 네트워크 타임아웃
- VPN 연결 실패

```python
for attempt in range(max_retry):
    if try_operation():
        break
    time.sleep(backoff)
```

### 3. 롤백 (Rollback)

복구 불가능한 오류는 롤백:
- 클러스터 조인 실패
- VPN 설정 오류

## 보안 고려사항

### 1. 인증 정보 관리

- 설정 파일 권한: `600`
- 토큰은 메모리에만 보관
- 로그에 민감 정보 미포함

### 2. 네트워크 보안

- TLS 인증서 검증
- 방화벽 자동 설정
- 최소 권한 원칙

### 3. 실행 권한

- Root 권한 필요 (시스템 설정 변경)
- 권한 체크 로직 포함

## 확장성

### 새로운 VPN 타입 추가

```python
class VPNManager:
    def connect(self):
        if self.vpn_type == "wireguard":
            return self._connect_wireguard()
        elif self.vpn_type == "openvpn":
            return self._connect_openvpn()
```

### 새로운 방화벽 타입 추가

```python
class FirewallManager:
    def configure(self):
        if self.firewall_type == "nftables":
            return self._configure_nftables()
```

### 커스텀 플러그인

```python
# plugins/custom_check.py
class CustomCheck:
    def check(self):
        # Custom logic
        pass
```

## 성능 최적화

### 1. 병렬 처리

독립적인 작업은 병렬 실행 가능:
- 네트워크 체크 (여러 호스트)
- 패키지 설치 (여러 패키지)

### 2. 캐싱

반복 호출 결과 캐싱:
- OS 정보
- 방화벽 타입
- VPN 상태

### 3. 지연 초기화

필요할 때만 객체 생성:
```python
@property
def vpn_manager(self):
    if not self._vpn_manager:
        self._vpn_manager = VPNManager(...)
    return self._vpn_manager
```

## 테스트 전략

### 1. 유닛 테스트

각 모듈별 독립 테스트:
```python
def test_config_load():
    config = Config("test.yaml")
    assert config.master.ip == "10.0.0.1"
```

### 2. 통합 테스트

모듈 간 상호작용 테스트:
```python
def test_orchestrator_flow():
    orchestrator = AgentOrchestrator(config)
    assert orchestrator.run() == True
```

### 3. 인수 테스트

실제 환경에서의 E2E 테스트:
```bash
./scripts/test.sh
```

## 의존성

### Python 패키지

```
click>=8.1.7      # CLI 프레임워크
rich>=13.7.0      # 컬러풀한 출력
pyyaml>=6.0.1     # YAML 파싱
requests>=2.31.0  # HTTP 요청
psutil>=5.9.6     # 시스템 정보
```

### 시스템 패키지

```
- kubeadm, kubelet, kubectl: K8s 도구
- containerd: 컨테이너 런타임
- tailscale: VPN 클라이언트
- ufw/firewalld: 방화벽
```

## 향후 계획

### Phase 2
- [ ] 웹 UI 추가
- [ ] Prometheus 메트릭 수집
- [ ] 자동 헬스체크 데몬
- [ ] 다중 마스터 지원

### Phase 3
- [ ] Helm 차트 제공
- [ ] Terraform 모듈
- [ ] Ansible 플레이북
- [ ] GitOps 통합

## 참고 자료

- [Kubernetes Architecture](https://kubernetes.io/docs/concepts/architecture/)
- [Headscale Documentation](https://github.com/juanfont/headscale)
- [Click Documentation](https://click.palletsprojects.com/)
- [Rich Documentation](https://rich.readthedocs.io/)

---

**버전**: 1.0.0  
**작성일**: 2025-10-21  
**작성자**: DevOps Team

