# Kubernetes 토큰 발급 가이드

## 마스터 노드에서 토큰 생성

워커 노드를 클러스터에 추가하려면 마스터 노드에서 조인 토큰과 CA 인증서 해시가 필요합니다.

### 1. 조인 명령어 전체 출력

마스터 노드에서 다음 명령을 실행하세요:

```bash
kubeadm token create --print-join-command
```

**출력 예시:**
```
kubeadm join 10.0.1.100:6443 --token abcdef.0123456789abcdef \
    --discovery-token-ca-cert-hash sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

### 2. 토큰과 해시 추출

위 출력에서:
- **토큰**: `abcdef.0123456789abcdef`
- **CA 해시**: `sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef`

### 3. 토큰 확인

현재 유효한 토큰 목록 확인:

```bash
kubeadm token list
```

**출력 예시:**
```
TOKEN                     TTL         EXPIRES                USAGES                   DESCRIPTION
abcdef.0123456789abcdef   23h         2025-10-22T12:00:00Z   authentication,signing   <none>
```

### 4. CA 인증서 해시 확인

토큰과 별도로 CA 해시를 확인하려면:

```bash
openssl x509 -pubkey -in /etc/kubernetes/pki/ca.crt | \
    openssl rsa -pubin -outform der 2>/dev/null | \
    openssl dgst -sha256 -hex | sed 's/^.* //'
```

**출력 예시:**
```
1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

실제 사용 시 앞에 `sha256:`을 붙여야 합니다:
```
sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef
```

### 5. 영구적인 토큰 생성 (선택사항)

기본 토큰은 24시간 후 만료됩니다. 만료 시간이 없는 토큰을 생성하려면:

```bash
kubeadm token create --ttl 0
```

**주의**: 보안상의 이유로 프로덕션 환경에서는 권장하지 않습니다.

### 6. 특정 토큰 생성

원하는 토큰 값을 지정하여 생성:

```bash
kubeadm token create abcdef.0123456789abcdef --ttl 24h
```

토큰 형식: `[a-z0-9]{6}.[a-z0-9]{16}`

## quick-setup.sh에 적용하기

생성한 토큰과 CA 해시를 `quick-setup.sh` 파일 상단의 상수에 입력하세요:

```bash
# === 설정 (여기를 수정하세요) ===
MASTER_IP="10.0.1.100"
JOIN_TOKEN="abcdef.0123456789abcdef"
CA_CERT_HASH="sha256:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef"
```

## 문제 해결

### 토큰이 만료된 경우

```bash
kubeadm token create --print-join-command
```

### 마스터 노드 접근 불가능한 경우

1. 마스터 노드 관리자에게 연락
2. 위의 명령어 실행을 요청
3. 토큰과 CA 해시를 전달받음

### CA 해시 불일치

만약 CA 해시가 맞지 않다면, 마스터 노드에서 다시 확인:

```bash
kubeadm token create --print-join-command
```

이 명령어는 항상 올바른 CA 해시를 함께 출력합니다.

## 보안 주의사항

⚠️ **토큰은 민감한 정보입니다!**

- 토큰을 가진 누구나 클러스터에 노드를 추가할 수 있습니다
- 토큰을 안전하게 보관하세요
- 사용하지 않는 토큰은 삭제하세요: `kubeadm token delete <token>`
- Git 저장소에 토큰을 커밋하지 마세요
- 프로덕션 환경에서는 짧은 TTL을 사용하세요

## 추가 정보

- [Kubeadm Token 관리 공식 문서](https://kubernetes.io/docs/reference/setup-tools/kubeadm/kubeadm-token/)
- [클러스터 조인 공식 가이드](https://kubernetes.io/docs/setup/production-environment/tools/kubeadm/create-cluster-kubeadm/)


