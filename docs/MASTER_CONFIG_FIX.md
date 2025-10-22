# kubeadm-config ConfigMap 수정 가이드

## 문제 증상

워커 노드 조인 시 다음 에러 발생:
```
error unmarshaling configuration: json: cannot unmarshal array into Go struct field APIServer.apiServer.extraArgs of type map[string]string
```

## 원인

마스터 노드의 `kubeadm-config` ConfigMap에서 `apiServer.extraArgs`가 **배열(array)** 형식으로 되어 있음.

Kubernetes는 이 필드를 **맵(map[string]string)** 형식으로 기대합니다.

## 해결 방법

### 방법 1: 자동 스크립트 사용 (권장) ⭐

**마스터 노드에서 실행:**

```bash
cd /root/k8s-vpn-agent
chmod +x scripts/fix-master-config.sh
sudo ./scripts/fix-master-config.sh
```

스크립트가 자동으로:
1. ✅ 현재 설정 확인
2. ✅ 백업 생성
3. ✅ 수정 가이드 제공
4. ✅ 수정 후 검증

### 방법 2: 수동 수정

#### 1단계: 백업 생성

```bash
kubectl get cm kubeadm-config -n kube-system -o yaml > kubeadm-config-backup.yaml
```

#### 2단계: ConfigMap 편집

```bash
kubectl edit cm kubeadm-config -n kube-system
```

#### 3단계: 형식 변경

**변경 전 (잘못된 배열 형식):**
```yaml
apiVersion: v1
data:
  ClusterConfiguration: |
    apiServer:
      extraArgs:
        - authorization-mode=Node,RBAC
        - enable-admission-plugins=NodeRestriction
        - some-other-arg=value
```

**변경 후 (올바른 맵 형식):**
```yaml
apiVersion: v1
data:
  ClusterConfiguration: |
    apiServer:
      extraArgs:
        authorization-mode: Node,RBAC
        enable-admission-plugins: NodeRestriction
        some-other-arg: value
```

#### 변경 규칙:
1. **`-` 제거** - 배열 표시 제거
2. **`=` → `:`** - 등호를 콜론으로 변경
3. **공백 추가** - 콜론 뒤에 공백
4. **들여쓰기 유지** - YAML 들여쓰기 규칙 준수

#### 4단계: 저장 및 종료

- vi/vim: `:wq`
- nano: `Ctrl+O`, `Enter`, `Ctrl+X`

#### 5단계: 검증

```bash
kubectl get cm kubeadm-config -n kube-system -o yaml | grep -A 10 extraArgs
```

출력이 맵 형식인지 확인:
```yaml
extraArgs:
  authorization-mode: Node,RBAC
  enable-admission-plugins: NodeRestriction
```

### 방법 3: YAML 파일로 수정

#### 1단계: ConfigMap 추출

```bash
kubectl get cm kubeadm-config -n kube-system -o yaml > config.yaml
```

#### 2단계: 파일 편집

```bash
vi config.yaml
```

#### 3단계: extraArgs 부분 수정

```yaml
# 배열 (-)을 맵 (key: value)으로 변경
```

#### 4단계: 적용

```bash
kubectl replace -f config.yaml
```

## 수정 후 확인

### 1. ConfigMap 확인

```bash
kubectl get cm kubeadm-config -n kube-system -o jsonpath='{.data.ClusterConfiguration}' | grep -A 5 extraArgs
```

### 2. 워커 노드에서 재시도

```bash
# 워커 노드에서
cd /root/k8s-vpn-agent
sudo ./quick-setup.sh
```

## 일반적인 예시

### 예시 1: 기본 설정

**변경 전:**
```yaml
extraArgs:
  - authorization-mode=Node,RBAC
  - enable-admission-plugins=NodeRestriction
```

**변경 후:**
```yaml
extraArgs:
  authorization-mode: Node,RBAC
  enable-admission-plugins: NodeRestriction
```

### 예시 2: 여러 인증 플러그인

**변경 전:**
```yaml
extraArgs:
  - authorization-mode=Node,RBAC
  - enable-admission-plugins=NodeRestriction,PodSecurityPolicy
  - allow-privileged=true
```

**변경 후:**
```yaml
extraArgs:
  authorization-mode: Node,RBAC
  enable-admission-plugins: NodeRestriction,PodSecurityPolicy
  allow-privileged: "true"
```

### 예시 3: OIDC 설정

**변경 전:**
```yaml
extraArgs:
  - oidc-issuer-url=https://example.com
  - oidc-client-id=kubernetes
  - oidc-username-claim=email
```

**변경 후:**
```yaml
extraArgs:
  oidc-issuer-url: https://example.com
  oidc-client-id: kubernetes
  oidc-username-claim: email
```

## 문제 해결

### Q1: 백업 파일을 복원하려면?

```bash
kubectl apply -f kubeadm-config-backup.yaml
```

### Q2: controllerManager, scheduler도 같은 문제가 있다면?

똑같이 수정:

```yaml
controllerManager:
  extraArgs:
    node-cidr-mask-size: "24"  # 배열 → 맵

scheduler:
  extraArgs:
    bind-address: "0.0.0.0"  # 배열 → 맵
```

### Q3: 수정 후에도 같은 에러가 발생한다면?

1. ConfigMap이 제대로 저장되었는지 확인
2. API 서버 재시작 (보통 자동)
3. 워커 노드에서 에이전트 재설치

```bash
cd /root/k8s-vpn-agent
source venv/bin/activate
pip install -e .
sudo ./quick-setup.sh
```

## 예방

### 클러스터 초기화 시 올바른 형식 사용

`kubeadm-config.yaml` 파일:

```yaml
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
apiServer:
  extraArgs:
    authorization-mode: Node,RBAC
    enable-admission-plugins: NodeRestriction
  # 배열 형식 사용하지 않음!
```

클러스터 초기화:

```bash
kubeadm init --config kubeadm-config.yaml
```

## 추가 정보

- [Kubernetes kubeadm Configuration API](https://kubernetes.io/docs/reference/config-api/kubeadm-config.v1beta3/)
- [kube-apiserver Extra Args](https://kubernetes.io/docs/reference/command-line-tools-reference/kube-apiserver/)

## 도움말

문제가 지속되면:
1. 마스터 노드 로그 확인: `journalctl -u kubelet -n 100`
2. API 서버 로그: `kubectl logs -n kube-system kube-apiserver-<master-node>`
3. 스크립트 디버그 모드: `bash -x ./scripts/fix-master-config.sh`

