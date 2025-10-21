# K8s VPN Agent - 프로젝트 요약

## 프로젝트 정보

- **이름**: K8s VPN Agent
- **버전**: 1.0.0
- **설명**: 서로 다른 네트워크망의 워커노드를 VPN을 통해 K8s 클러스터에 추가하는 자동화 에이전트
- **언어**: Python 3.8+
- **개발 완료일**: 2025-10-21

## 주요 기능

✅ **자동화**
- OS 자동 감지 (Ubuntu, Debian, CentOS, RHEL, Rocky, Fedora)
- 패키지 자동 설치
- Python venv 자동 활성화
- 방화벽 자동 설정

✅ **VPN 지원**
- Headscale 기반 VPN 연결
- Tailscale 지원
- 마스터와 직접 통신 가능 시 VPN 자동 스킵

✅ **안정성**
- Idempotent 설계
- 자동 롤백 기능
- 상세한 로깅
- 디버그 모드

✅ **보안**
- TLS 인증서/토큰 자동 관리
- 방화벽 자동 설정
- 네트워크 헬스체크

✅ **사용자 경험**
- CLI 형태 (Click 기반)
- Rich를 활용한 컬러풀한 출력
- 대화형 모드
- 설정 파일 검증

## 프로젝트 구조

```
k8s-vpn-agent/
├── src/k8s_vpn_agent/      # 메인 소스 코드
│   ├── cli.py              # CLI 인터페이스
│   ├── config.py           # 설정 관리
│   ├── network.py          # 네트워크 체크
│   ├── vpn.py              # VPN 관리
│   ├── k8s.py              # K8s 조인
│   ├── firewall.py         # 방화벽 관리
│   └── logger.py           # 로깅 시스템
├── scripts/                # 실행 스크립트
│   ├── install-dependencies.sh
│   ├── install-agent.sh
│   └── test.sh
├── config/                 # 설정 파일
│   └── config.yaml.sample
├── docs/                   # 문서
│   ├── ARCHITECTURE.md
│   └── USER_MANUAL.md
├── tests/                  # 테스트
│   ├── test_config.py
│   └── test_network.py
├── README.md              # 메인 README
├── QUICKSTART.md          # 빠른 시작 가이드
└── setup.py               # 설치 설정
```

## 핵심 모듈

| 모듈 | 파일 | 역할 |
|------|------|------|
| CLI | cli.py | 사용자 인터페이스, 명령어 처리 |
| Config | config.py | YAML/JSON 설정 관리 |
| Network | network.py | 네트워크 연결성 체크 |
| VPN | vpn.py | Headscale/Tailscale VPN 관리 |
| K8s | k8s.py | 클러스터 조인 및 노드 관리 |
| Firewall | firewall.py | 방화벽 자동 설정 |
| Logger | logger.py | 로깅 시스템 |

## 주요 명령어

```bash
# 설정 파일 생성
k8s-vpn-agent init config.yaml

# 설정 검증
k8s-vpn-agent validate --config config.yaml

# 클러스터 조인
k8s-vpn-agent join --config config.yaml

# 대화형 모드
k8s-vpn-agent join --interactive

# 디버그 모드
k8s-vpn-agent join --config config.yaml --debug
```

## 설치 방법

### 1. 의존성 설치
```bash
sudo ./scripts/install-dependencies.sh
```

### 2. 에이전트 설치
```bash
sudo ./scripts/install-agent.sh
```

### 3. 설정 및 실행
```bash
cp config/config.yaml.sample config/config.yaml
vi config/config.yaml
source venv/bin/activate
k8s-vpn-agent join --config config.yaml
```

## 기술 스택

- **Language**: Python 3.8+
- **CLI Framework**: Click
- **UI Library**: Rich
- **Config**: PyYAML
- **Container Runtime**: Containerd
- **VPN**: Headscale/Tailscale
- **K8s**: kubeadm, kubelet, kubectl

## 시스템 요구사항

- OS: Ubuntu 22.04+, Debian 11+, CentOS 8+, RHEL 8+, Rocky 8+, Fedora 35+
- CPU: 2 cores 이상
- Memory: 2GB 이상
- Disk: 20GB 이상
- Python: 3.8 이상

## 테스트

```bash
# 유닛 테스트
pytest tests/

# 통합 테스트
./scripts/test.sh

# 설정 검증
k8s-vpn-agent validate --config config.yaml
```

## 로그 파일

- 메인 로그: `/var/log/k8s-vpn-agent/agent_*.log`
- 에러 로그: `/var/log/k8s-vpn-agent/error_*.log`

## 문서

- [README.md](README.md) - 전체 개요 및 사용법
- [QUICKSTART.md](QUICKSTART.md) - 빠른 시작 가이드
- [docs/USER_MANUAL.md](docs/USER_MANUAL.md) - 상세 사용자 매뉴얼
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - 아키텍처 문서

## 산출물

✅ CLI 에이전트 코드 (8개 모듈)
✅ 설치/실행 스크립트 (3개)
✅ 사용 매뉴얼 (자동 생성 포함)
✅ 샘플 config.yaml
✅ 테스트 스크립트
✅ 아키텍처 문서

## 개발 완료 항목

- [x] 프로젝트 구조 생성 및 Python 환경 설정
- [x] 핵심 모듈 구현: 설정 관리자 (YAML/JSON)
- [x] 네트워크 체커 모듈 (ping, 포트, DNS)
- [x] VPN 매니저 (Headscale/Tailscale)
- [x] K8s 조인 모듈 (idempotent, 롤백)
- [x] 방화벽 및 보안 모듈 (자동 설정)
- [x] CLI 인터페이스 (Click, Rich)
- [x] 로깅 및 디버그 시스템
- [x] 테스트 스크립트 작성
- [x] 설치 스크립트 및 문서 완성
- [x] 아키텍처 설계 및 문서화

## 라이선스

MIT License

## 지원

문제가 발생하면 다음을 확인하세요:
1. 로그 파일: `/var/log/k8s-vpn-agent/`
2. Kubelet 로그: `journalctl -u kubelet -f`
3. 네트워크 연결성: `ping <master-ip>`

---

**프로젝트 완료**: 2025-10-21
