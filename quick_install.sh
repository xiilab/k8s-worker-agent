#!/bin/bash
set -e

echo "=========================================="
echo "Kubernetes Worker Node Agent"
echo "완전 자동 설치 및 조인 스크립트"
echo "=========================================="
echo ""

# 루트 권한 확인
if [ "$EUID" -ne 0 ]; then 
    echo "❌ 이 스크립트는 root 권한이 필요합니다."
    echo "   sudo bash quick_install.sh 로 실행해주세요."
    exit 1
fi

# 현재 디렉토리로 이동
cd "$(dirname "$0")"

echo "📦 1/4 시스템 의존성 설치 중 (5-10분 소요)..."
echo "   - Python 환경 (python3, pip, build-essential)"
echo "   - CRI-O 컨테이너 런타임"
echo "   - Kubernetes 도구 (kubeadm, kubelet, kubectl)"
echo "   - 네트워크 도구"
echo ""

bash install_dependencies.sh

echo ""
echo "📦 2/4 Python 패키지 설치 중..."
pip3 install -q pyyaml requests rich prompt_toolkit netifaces
echo "✅ Python 패키지 설치 완료"
echo ""

echo "=========================================="
echo "⚙️  3/4 클러스터 조인 설정"
echo "=========================================="
echo ""

# ⚠️ 주의: 실제 환경에 맞게 수정 필요
MASTER_API="10.61.3.40:6443"  # 마스터 노드 IP:포트
TOKEN="ajd8xg.oxkw847ckwdevjts"  # kubeadm token (마스터에서: kubeadm token create)
CA_HASH="sha256:4e3fc11265ae8ebdebee502a1aff7ab05e43375ecd7d10e79e3ee682b76452c4"  # CA 해시

echo "마스터 노드: $MASTER_API"
echo "토큰: ${TOKEN:0:10}..."
echo ""

# 사용자 이름만 입력받기
read -p "사용자 이름 (노드 레이블용, 예: j.seo@xiilab.com): " USERNAME

# VPN 자동 감지 사용
VPN_ENABLED="false"
VPN_AUTO="true"
HEADSCALE_URL=""
HEADSCALE_KEY=""

echo ""
echo "VPN 자동 감지: 활성화"

# config.yaml 생성
echo ""
echo "설정 파일 생성 중..."

# 사용자 이름이 이메일 형식인지 확인하고 레이블 생성
if [[ "$USERNAME" == *@* ]]; then
    # 이메일 형식: username과 domain 분리
    USER_NAME=$(echo "$USERNAME" | cut -d@ -f1)
    USER_DOMAIN=$(echo "$USERNAME" | cut -d@ -f2)
    LABEL_LINES="    - \"node-role.kubernetes.io/worker=worker\"
    - \"added-username=$USER_NAME\"
    - \"added-user-domain=$USER_DOMAIN\""
else
    # 일반 사용자 이름
    LABEL_LINES="    - \"node-role.kubernetes.io/worker=worker\"
    - \"added-by=$USERNAME\""
fi

cat > config.yaml << EOF
# Kubernetes Worker Node Agent Configuration
# 자동 생성된 설정 파일

master_node:
  api_server: "$MASTER_API"
  token: "$TOKEN"
  ca_cert_hash: "$CA_HASH"

vpn:
  enabled: $VPN_ENABLED
  headscale_url: "$HEADSCALE_URL"
  auth_key: "$HEADSCALE_KEY"
  auto_detect: $VPN_AUTO

worker_node:
  hostname_prefix: "worker"
  username: "$USERNAME"
  labels:
$LABEL_LINES

firewall:
  k8s_api_port: 6443
  kubelet_port: 10250
  nodeport_range: "30000-32767"
  auto_configure: true

system:
  log_file: "/var/log/k8s-agent.log"
  auto_reconnect: true
  rollback_on_failure: true
  backup_config: true
EOF

echo "✅ 설정 파일 생성 완료 (config.yaml)"
echo ""

echo "=========================================="
echo "🚀 4/4 클러스터 조인 시작"
echo "=========================================="
echo ""

# 현재 IP 감지 (마스터와 같은 네트워크)
echo "📡 네트워크 환경 확인 중..."
MASTER_IP=$(echo "$MASTER_API" | cut -d: -f1)
CURRENT_IP=$(ip route get "$MASTER_IP" 2>/dev/null | grep -oP 'src \K[\d.]+')

if [ -z "$CURRENT_IP" ]; then
    echo "⚠️  경고: 마스터 노드와 통신 가능한 IP를 감지하지 못했습니다."
    echo "   기본 IP가 사용됩니다."
else
    echo "✅ 감지된 IP: $CURRENT_IP (마스터: $MASTER_IP)"
    
    # IP 중복 등록 방지: 이미 kubelet.conf가 있다면 (이전 조인 이력) IP 중복 체크
    if [ -f /etc/kubernetes/kubelet.conf ]; then
        # kubectl이 정상 작동하는지 먼저 확인
        if timeout 5 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf cluster-info >/dev/null 2>&1; then
            echo ""
            echo "🔍 IP 중복 등록 확인 중..."
            
            CURRENT_HOSTNAME=$(hostname)
            
            # 동일한 IP를 사용하는 노드가 클러스터에 있는지 확인
            EXISTING_NODES=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf get nodes -o custom-columns=NAME:.metadata.name,IP:.status.addresses[0].address --no-headers 2>/dev/null | grep "$CURRENT_IP" || true)
            
            if [ -n "$EXISTING_NODES" ]; then
                echo ""
                echo "⚠️  경고: 동일한 IP($CURRENT_IP)를 가진 노드가 클러스터에 등록되어 있습니다!"
                echo ""
                echo "등록된 노드:"
                echo "$EXISTING_NODES"
                echo ""
                echo "이 IP로 새 노드를 추가하면 네트워크 충돌이 발생할 수 있습니다."
                echo ""
                echo "해결 방법:"
                echo "  1. 기존 노드를 제거하고 재등록:"
                echo "     마스터 노드: kubectl delete node <노드이름>"
                echo "     워커 노드:   sudo bash cleanup.sh && sudo bash quick_install.sh"
                echo ""
                echo "  2. 다른 서버에서 실행하기 (다른 IP 사용)"
                echo ""
                exit 1
            else
                echo "✅ IP 중복 없음. 계속 진행합니다."
            fi
        else
            echo "ℹ️  이전 설치 흔적 발견. 정리 후 계속 진행합니다."
        fi
    fi
fi

echo ""

# Calico CNI를 위한 필수 디렉토리 사전 생성
echo "📁 Calico 필수 디렉토리 생성 중..."
mkdir -p /var/log/calico/cni
mkdir -p /var/lib/calico
mkdir -p /var/run/calico
mkdir -p /var/run/nodeagent
mkdir -p /etc/cni/net.d
mkdir -p /opt/cni/bin
mkdir -p /var/lib/cni/networks

chmod 755 /var/log/calico/cni
chmod 755 /var/lib/calico
chmod 755 /var/run/calico
chmod 755 /var/run/nodeagent

echo "✅ 디렉토리 생성 완료"
echo ""

# 참고: kubespray 클러스터는 조인 후 ConfigMap 설정이 필요할 수 있습니다
# 워커 노드는 ConfigMap 수정 권한이 없으므로 설치 완료 메시지에서 안내합니다

# 에이전트 자동 실행
python3 agent.py --auto

WORKER_HOSTNAME=$(hostname)

echo ""
echo "=========================================="
echo "✅ 워커 노드 조인 완료!"
echo "=========================================="
echo ""

# kubespray 클러스터 호환성: ConfigMap 자동 설정
echo "🔧 kubespray 클러스터 호환성 확인 중..."

if [ -f /etc/kubernetes/kubelet.conf ]; then
    # ConfigMap 존재 여부 확인
    CONFIGMAP_EXISTS=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf get configmap -n kube-system kubernetes-services-endpoint 2>/dev/null && echo "true" || echo "false")
    
    if [ "$CONFIGMAP_EXISTS" = "false" ]; then
        echo "ℹ️  kubernetes-services-endpoint ConfigMap이 없습니다. (정상 - 일반 kubeadm 클러스터)"
        echo "   kubespray 클러스터가 아닌 경우 이 ConfigMap은 필요하지 않습니다."
    else
        # ConfigMap이 존재하면 데이터 확인
        CONFIGMAP_DATA=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf get configmap -n kube-system kubernetes-services-endpoint -o jsonpath='{.data}' 2>/dev/null || echo "")
        
        # 데이터가 비어있거나 "{}" 또는 "null"인지 확인
        NEEDS_PATCH=false
        if [ -z "$CONFIGMAP_DATA" ] || [ "$CONFIGMAP_DATA" = "null" ] || [ "$CONFIGMAP_DATA" = "{}" ]; then
            NEEDS_PATCH=true
        else
            # KUBERNETES_SERVICE_HOST 키가 있는지 확인
            HAS_HOST=$(echo "$CONFIGMAP_DATA" | grep -c "KUBERNETES_SERVICE_HOST" || true)
            if [ "$HAS_HOST" -eq 0 ]; then
                NEEDS_PATCH=true
            fi
        fi
        
        if [ "$NEEDS_PATCH" = "true" ]; then
            echo "⚠️  kubernetes-services-endpoint ConfigMap이 비어있습니다."
            echo "   kubespray 클러스터에서 Calico CNI가 정상 동작하려면 이 ConfigMap이 필요합니다."
            echo ""
            echo "📝 ConfigMap 패치 시도 중..."
            
            # ConfigMap 패치 시도 (set -e 영향 받지 않도록 || true 추가)
            set +e  # 임시로 에러 중단 비활성화
            PATCH_RESULT=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf patch configmap kubernetes-services-endpoint -n kube-system --type merge -p "{\"data\":{\"KUBERNETES_SERVICE_HOST\":\"$MASTER_IP\",\"KUBERNETES_SERVICE_PORT\":\"6443\"}}" 2>&1 || true)
            PATCH_EXIT=$?
            set -e  # 다시 활성화
            
            echo "   패치 결과 코드: $PATCH_EXIT"
            
            if [ $PATCH_EXIT -eq 0 ]; then
                echo "✅ ConfigMap 패치 성공!"
                echo ""
                echo "🔄 Calico 파드 재시작 중..."
                
                set +e
                DELETE_RESULT=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf delete pod -n kube-system -l k8s-app=calico-node --field-selector spec.nodeName=$WORKER_HOSTNAME 2>&1 || true)
                DELETE_EXIT=$?
                set -e
                
                if [ $DELETE_EXIT -eq 0 ]; then
                    echo "✅ Calico 파드 재시작 완료"
                    echo "   2-3분 후 노드가 Ready 상태가 됩니다."
                else
                    echo "ℹ️  Calico 파드 재시작 결과: $DELETE_RESULT"
                fi
            else
                echo "⚠️  ConfigMap 패치 실패 (권한 부족 또는 제한)"
                echo "   상세: $PATCH_RESULT"
                echo ""
                echo "❗ 마스터 노드에서 다음 명령을 실행하세요:"
                echo ""
                echo "------- 복사 시작 -------"
                echo "# 1. ConfigMap 패치 (한 번만 실행하면 이후 모든 노드에 적용)"
                echo "kubectl patch configmap kubernetes-services-endpoint -n kube-system --type merge -p '{\"data\":{\"KUBERNETES_SERVICE_HOST\":\"$MASTER_IP\",\"KUBERNETES_SERVICE_PORT\":\"6443\"}}'"
                echo ""
                echo "# 2. Worker role 레이블 추가"
                echo "kubectl label node $WORKER_HOSTNAME node-role.kubernetes.io/worker=worker"
                echo ""
                echo "# 3. Calico 파드 재시작"
                echo "kubectl delete pod -n kube-system -l k8s-app=calico-node --field-selector spec.nodeName=$WORKER_HOSTNAME"
                echo ""
                echo "# 4. 2분 대기 후 확인"
                echo "sleep 120 && kubectl get nodes -o wide"
                echo "------- 복사 끝 -------"
            fi
        else
            echo "✅ kubernetes-services-endpoint ConfigMap이 이미 설정되어 있습니다."
        fi
    fi
else
    echo "⚠️  kubelet.conf 파일이 없습니다. ConfigMap 확인을 건너뜁니다."
fi

echo ""
echo "⚠️  마스터 노드에서 Worker role 레이블을 추가하세요:"
echo "   kubectl label node $WORKER_HOSTNAME node-role.kubernetes.io/worker=worker"
echo ""
echo "📝 노드 상태 확인 (2-3분 후):"
echo "   kubectl get nodes -o wide"
echo "   kubectl get pods -n kube-system -l k8s-app=calico-node -o wide"
echo ""
echo "📝 로컬 로그 확인:"
echo "   sudo systemctl status kubelet"
echo "   sudo journalctl -u kubelet -f"
echo ""

