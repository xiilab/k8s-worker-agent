# Kubernetes Worker Node Auto Join Agent

kubespray 클러스터에 워커 노드를 자동으로 추가하는 도구입니다.

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

- ✅ CRI-O, Kubernetes 도구 자동 설치
- ✅ 클러스터 자동 조인 (kubeadm)
- ✅ kubespray 클러스터 호환 (ConfigMap 자동 패치)
- ✅ IP 중복 방지
- ✅ 사용자 레이블 자동 생성
- ✅ Calico CNI 자동 설정
- ✅ 자동 롤백 (실패 시)

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

### 로그 확인

```bash
# kubelet 상태
sudo systemctl status kubelet

# kubelet 로그
sudo journalctl -u kubelet -f

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
