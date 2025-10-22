# Quick Start Guide

## 설치 전

`quick_install.sh` 파일을 열어서 **실제 값으로 수정**:

```bash
MASTER_API="<마스터노드IP>:6443"
TOKEN="<실제토큰>"
CA_HASH="sha256:<실제해시>"
```

## 1분 설치

```bash
sudo bash quick_install.sh
```

입력: 사용자 이름 (예: `user@example.com`)

끝! 🎉

## 설치 후

**마스터 노드에서:**
```bash
# 레이블 추가
kubectl label node <워커노드> node-role.kubernetes.io/worker=worker

# 확인
kubectl get nodes -o wide
```

## 예상 시간

- 의존성 설치: 5-10분
- 클러스터 조인: 1분
- CNI 준비: 2-3분

**총 소요 시간: 약 10-15분**

## 실패 시

```bash
# 정리
sudo bash cleanup.sh

# 재시도
sudo bash quick_install.sh
```

## 자주 묻는 질문

**Q: ConfigMap 에러가 나와요**
```bash
# 마스터에서 실행
kubectl patch configmap kubernetes-services-endpoint -n kube-system --type merge -p '{"data":{"KUBERNETES_SERVICE_HOST":"<마스터노드IP>","KUBERNETES_SERVICE_PORT":"6443"}}'
```

**Q: IP 충돌 에러가 나와요**
```bash
# 마스터에서 기존 노드 제거
kubectl delete node <기존노드>

# 워커에서 재설치
sudo bash cleanup.sh
sudo bash quick_install.sh
```

**Q: 노드가 NotReady 상태예요**
```bash
# 2-3분 기다려보세요
# 여전히 NotReady면:
kubectl delete pod -n kube-system -l k8s-app=calico-node --field-selector spec.nodeName=<워커노드>
```

