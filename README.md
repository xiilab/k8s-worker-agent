# Kubernetes Worker Node Auto Join Agent

kubespray 클러스터에 워커 노드를 자동으로 추가하는 도구입니다.

## ⚠️ kubespray 클러스터 사전 설정 (필수)

**마스터 노드에서 한 번만 실행하세요:**

```bash
MASTER_IP="10.61.3.40"  # 실제 마스터 IP로 변경

# 1. kubernetes-services-endpoint ConfigMap 설정
kubectl patch configmap kubernetes-services-endpoint -n kube-system --type merge \
  -p "{\"data\":{\"KUBERNETES_SERVICE_HOST\":\"$MASTER_IP\",\"KUBERNETES_SERVICE_PORT\":\"6443\"}}"

# 2. kube-proxy ConfigMap 수정 (127.0.0.1 → 실제 마스터 IP)
kubectl get configmap kube-proxy -n kube-system -o yaml | \
  sed "s|server: https://127.0.0.1:6443|server: https://$MASTER_IP:6443|g" | \
  kubectl apply -f -

# 3. 모든 kube-proxy 재시작
kubectl delete pod -n kube-system -l k8s-app=kube-proxy
```

> **왜 필요한가요?**  
> kubespray는 기본적으로 `server: https://127.0.0.1:6443`으로 설정되어 있어 워커 노드에서 API 서버 연결(10.233.0.1:443)이 실패합니다.

## 빠른 설치

```bash
# 1. 저장소 클론
git clone <repository-url>
cd k8s-vpn-agent-jseo

# 2. 설정 수정 (quick_install.sh 파일)
# ⚠️ 실제 마스터 노드 IP, Token, CA Hash로 변경 필요
# MASTER_API="<마스터노드IP>:6443"
# TOKEN="<실제토큰>"
# CA_HASH="sha256:<실제해시>"

# 3. 자동 설치 실행
sudo bash quick_install.sh

# 사용자 이름 입력 (예: user@example.com)
# → 자동으로 added-username=user, added-user-domain=example.com 레이블 생성
```

## 설치 후 작업

### 마스터 노드에서 실행

```bash
# Worker role 레이블 추가
kubectl label node <워커노드이름> node-role.kubernetes.io/worker=worker

# 노드 상태 확인 (2-3분 후)
kubectl get nodes -o wide
```

## 주요 기능

- ✅ Python 환경 자동 설치 (python3, pip, build-essential)
- ✅ CRI-O, Kubernetes 도구 자동 설치
- ✅ 클러스터 자동 조인 (kubeadm)
- ✅ kubespray 클러스터 호환 (ConfigMap 자동 패치)
- ✅ GPU 자동 감지 및 레이블링
- ✅ IP 중복 방지
- ✅ 사용자 레이블 자동 생성
- ✅ Calico CNI 자동 설정
- ✅ 자동 롤백 (실패 시)
- ✅ GPU Operator 디버깅 도구

## 시스템 요구사항

- Ubuntu 20.04 / 22.04
- Root 권한
- 마스터 노드와 네트워크 연결

## 설정 파일

자동 생성된 `config.yaml`:
- 마스터 노드: 코드에 고정값으로 설정됨
- Token: 코드에 고정값으로 설정됨
- 사용자 정의 레이블 지원

> 실제 IP, Token은 `quick_install.sh`에서 수정 필요

## 제거

```bash
sudo bash cleanup.sh
```

## 문제 해결

### 노드가 NotReady 상태인 경우

1. Calico 파드 확인:
   ```bash
   kubectl get pods -n kube-system -l k8s-app=calico-node -o wide
   ```

2. ConfigMap 확인 (마스터 노드):
   ```bash
   kubectl get configmap -n kube-system kubernetes-services-endpoint -o yaml
   ```

3. 비어있다면 패치:
   ```bash
   kubectl patch configmap kubernetes-services-endpoint -n kube-system --type merge -p '{"data":{"KUBERNETES_SERVICE_HOST":"<마스터노드IP>","KUBERNETES_SERVICE_PORT":"6443"}}'
   
   kubectl delete pod -n kube-system -l k8s-app=calico-node --field-selector spec.nodeName=<워커노드>
   ```

### GPU Operator 관련 문제

#### GPU가 없는 워커 노드에서 GPU Operator 파드가 CrashLoopBackOff 발생

**증상:**
- `gpu-operator-node-feature-discovery-worker` 파드가 GPU 없는 노드에서 CrashLoopBackOff
- GPU 관련 데몬셋이 모든 노드에 스케줄링되어 리소스 낭비

**자동 해결:**
- `quick_install.sh`는 자동으로 GPU 유무를 감지하고 레이블을 추가합니다
- GPU가 없는 노드: `nvidia.com/gpu=false` 레이블 자동 추가

**수동 해결 (마스터 노드):**
```bash
# 1. GPU 없는 노드에 레이블 추가
kubectl label node <워커노드이름> nvidia.com/gpu=false --overwrite

# 2. 해당 노드의 GPU Operator 파드 삭제 (자동 재생성 방지)
kubectl delete pod -n gpu-operator --field-selector spec.nodeName=<워커노드이름>

# 3. GPU Operator가 GPU 없는 노드를 스킵하도록 설정 확인
kubectl get daemonset -n gpu-operator -o yaml | grep -A 5 nodeSelector
```

**GPU Operator 디버깅:**
```bash
# 디버깅 스크립트 실행 (워커 노드에서)
bash debug_gpu_operator.sh <워커노드이름>

# 또는 마스터 노드에서 직접 확인
kubectl get pods -n gpu-operator -o wide
kubectl describe pod -n gpu-operator <파드이름>
kubectl logs -n gpu-operator <파드이름> --all-containers
```

**GPU Operator DaemonSet에 nodeSelector 추가 (권장):**
```bash
# GPU가 있는 노드만 선택하도록 설정
kubectl patch daemonset gpu-operator-node-feature-discovery-worker -n gpu-operator --type merge -p '
{
  "spec": {
    "template": {
      "spec": {
        "nodeSelector": {
          "nvidia.com/gpu": "true"
        }
      }
    }
  }
}'
```

### 로그 확인

```bash
# kubelet 상태
sudo systemctl status kubelet

# kubelet 로그
sudo journalctl -u kubelet -f

# CRI-O 로그
sudo journalctl -u crio -f

# 에이전트 로그
sudo tail -f /var/log/k8s-agent.log
```

## 아키텍처

```
quick_install.sh
  ├─ install_dependencies.sh  # CRI-O, kubeadm, kubelet 설치
  ├─ agent.py --auto          # 클러스터 조인
  └─ ConfigMap 자동 패치      # kubespray 호환성
```

## 라이선스

MIT License
