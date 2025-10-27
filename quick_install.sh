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
# 40번 노드
# MASTER_API="10.61.3.40:6443"  # 마스터 노드 IP:포트
# TOKEN="ajd8xg.oxkw847ckwdevjts"  # kubeadm token (마스터에서: kubeadm token create)
# CA_HASH="sha256:4e3fc11265ae8ebdebee502a1aff7ab05e43375ecd7d10e79e3ee682b76452c4"  # CA 해시

# 1번 노드
MASTER_API="10.61.3.12:6443"  # 마스터 노드 IP:포트
TOKEN="ce3lbp.h3kzqknz8jqacoi5"  # kubeadm token (마스터에서: kubeadm token create)
CA_HASH="sha256:860f691019fdc3a399455eeef000f584fe11579c4e61cda9d228d8a2ade99b6e"  # CA 해시



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
        echo ""
        echo "🔍 기존 Kubernetes 설정 발견..."
        
        # 기존 kubelet.conf가 현재 목표 클러스터를 가리키는지 확인
        EXISTING_SERVER=$(grep 'server:' /etc/kubernetes/kubelet.conf 2>/dev/null | awk '{print $2}' | head -n1 || echo "")
        TARGET_SERVER="https://$MASTER_API"
        
        if [ -n "$EXISTING_SERVER" ] && [ "$EXISTING_SERVER" != "$TARGET_SERVER" ]; then
            echo "⚠️  다른 클러스터의 설정이 발견되었습니다!"
            echo "   기존 클러스터: $EXISTING_SERVER"
            echo "   목표 클러스터: $TARGET_SERVER"
            echo ""
            echo "🧹 기존 설정을 정리하고 새 클러스터에 조인합니다..."
            
            # 기존 설정 정리 (agent.py도 정리하지만, 미리 정리)
            kubeadm reset -f 2>/dev/null || true
            rm -rf /etc/kubernetes 2>/dev/null || true
            rm -rf /var/lib/kubelet/* 2>/dev/null || true
            rm -rf /etc/cni/net.d/* 2>/dev/null || true
            
            echo "✅ 기존 설정 정리 완료. 새 클러스터 조인을 계속합니다."
            echo ""
        else
            # 같은 클러스터 - 정상적으로 IP 중복 체크
            if timeout 5 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf cluster-info >/dev/null 2>&1; then
                echo "   동일한 클러스터 감지. IP 중복 확인 중..."
                
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
                    echo "     마스터 노드에서: kubectl delete node <노드이름>"
                    echo "     워커 노드에서:   sudo bash cleanup.sh && sudo bash quick_install.sh"
                    echo ""
                    echo "  2. 다른 서버에서 실행하기 (다른 IP 사용)"
                    echo ""
                    exit 1
                else
                    echo "✅ IP 중복 없음. 계속 진행합니다."
                fi
            else
                echo "ℹ️  이전 설치 흔적 발견했으나 클러스터 연결 불가."
                echo "   정리 후 계속 진행합니다."
            fi
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
    # 1단계: 클러스터 연결 상태 확인
    echo "   클러스터 연결 테스트 중..."
    set +e
    CLUSTER_CHECK=$(timeout 5 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf get nodes 2>&1)
    CLUSTER_CHECK_EXIT=$?
    set -e
    
    if [ $CLUSTER_CHECK_EXIT -ne 0 ]; then
        # 클러스터 연결 실패 - 이전 조인이 실패했거나 노드가 삭제된 경우
        echo "⚠️  클러스터 연결 실패: 이전 kubelet.conf가 유효하지 않습니다."
        echo "   - 노드가 클러스터에서 삭제되었거나"
        echo "   - 이전 조인 시도가 실패한 상태일 수 있습니다."
        echo ""
        echo "ℹ️  ConfigMap 확인을 건너뜁니다. (클러스터 연결 불가)"
        echo "   새로 조인된 노드는 정상 동작합니다."
    else
        # 클러스터 연결 성공 - ConfigMap 확인 진행
        echo "   ✅ 클러스터 연결 정상"
        echo ""
        
        # 2단계: ConfigMap 존재 여부 및 데이터 확인
        set +e
        CONFIGMAP_DATA=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf get configmap -n kube-system kubernetes-services-endpoint -o jsonpath='{.data}' 2>/dev/null)
        CONFIGMAP_EXIT=$?
        set -e
        
        # exit code가 실패면 빈 문자열로 설정
        if [ $CONFIGMAP_EXIT -ne 0 ]; then
            CONFIGMAP_DATA=""
        fi
        
        # 디버깅: 실제 데이터 값 출력
        echo "   [디버그] ConfigMap 조회 결과: exit=$CONFIGMAP_EXIT"
        echo "   [디버그] 데이터 내용: '$CONFIGMAP_DATA'"
        echo "   [디버그] 데이터 길이: ${#CONFIGMAP_DATA}"
        echo ""
        
        # ConfigMap이 존재하지 않는 경우
        if [ $CONFIGMAP_EXIT -ne 0 ]; then
            echo "ℹ️  kubernetes-services-endpoint ConfigMap이 없습니다. (정상 - 일반 kubeadm 클러스터)"
            echo "   kubespray 클러스터가 아닌 경우 이 ConfigMap은 필요하지 않습니다."
        else
            # ConfigMap 존재 - 데이터 확인
            echo "ℹ️  kubernetes-services-endpoint ConfigMap 발견"
            
            # 데이터가 비어있는지 확인 (더 엄격하게)
            DATA_LENGTH=${#CONFIGMAP_DATA}
            if [ $DATA_LENGTH -eq 0 ] || [ "$CONFIGMAP_DATA" = "null" ] || [ "$CONFIGMAP_DATA" = "{}" ]; then
                # 데이터가 비어있음 - 패치 필요
                echo "   → 데이터 없음 (비어있음)"
                echo ""
                echo "⚠️  ConfigMap이 비어있어 패치가 필요합니다."
                echo "   kubespray 클러스터에서 Calico CNI가 정상 동작하려면 이 데이터가 필요합니다."
                echo ""
                echo "📝 ConfigMap 패치 시도 중..."
                
                # ConfigMap 패치 시도
                set +e
                PATCH_RESULT=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf patch configmap kubernetes-services-endpoint -n kube-system --type merge -p "{\"data\":{\"KUBERNETES_SERVICE_HOST\":\"$MASTER_IP\",\"KUBERNETES_SERVICE_PORT\":\"6443\"}}" 2>&1)
                PATCH_EXIT=$?
                set -e
                
                echo "   패치 결과 코드: $PATCH_EXIT"
                
                if [ $PATCH_EXIT -eq 0 ]; then
                    echo "✅ ConfigMap 패치 성공!"
                    echo ""
                    echo "🔄 Calico 파드 재시작 중..."
                    
                    set +e
                    DELETE_RESULT=$(timeout 10 kubectl --kubeconfig=/etc/kubernetes/kubelet.conf delete pod -n kube-system -l k8s-app=calico-node --field-selector spec.nodeName=$WORKER_HOSTNAME 2>&1)
                    DELETE_EXIT=$?
                    set -e
                    
                    if [ $DELETE_EXIT -eq 0 ]; then
                        echo "✅ Calico 파드 재시작 완료"
                        echo "   2-3분 후 노드가 Ready 상태가 됩니다."
                    else
                        echo "ℹ️  Calico 파드 재시작 결과: $DELETE_RESULT"
                    fi
                else
                    echo ""
                    echo "=========================================="
                    echo "⚠️  예상된 동작: 워커 노드는 ConfigMap 수정 권한이 없습니다"
                    echo "=========================================="
                    if [ -n "$PATCH_RESULT" ]; then
                        echo ""
                        echo "오류 내용: $PATCH_RESULT"
                    fi
                    echo ""
                    echo "✋ 이것은 정상입니다! 쿠버네티스 보안 정책상 워커 노드는"
                    echo "   ConfigMap을 읽을 수만 있고 수정할 수 없습니다."
                    echo ""
                    echo "🔧 해결 방법: 마스터 노드(또는 관리자 권한이 있는 노드)에서"
                    echo "   아래 명령어를 실행하세요."
                    echo ""
                    echo "=========================================="
                    echo "📋 마스터 노드에서 실행할 명령어 (복사하세요)"
                    echo "=========================================="
                    echo ""
                    echo "# 1️⃣  ConfigMap 패치 (한 번만 실행하면 모든 워커 노드에 적용됨)"
                    echo "kubectl patch configmap kubernetes-services-endpoint -n kube-system --type merge -p '{\"data\":{\"KUBERNETES_SERVICE_HOST\":\"$MASTER_IP\",\"KUBERNETES_SERVICE_PORT\":\"6443\"}}'"
                    echo ""
                    echo "# 2️⃣  Worker role 레이블 추가"
                    echo "kubectl label node $WORKER_HOSTNAME node-role.kubernetes.io/worker=worker --overwrite"
                    echo ""
                    echo "# 3️⃣  이 워커 노드의 Calico 파드 재시작 (CNI 문제 해결)"
                    echo "kubectl delete pod -n kube-system -l k8s-app=calico-node --field-selector spec.nodeName=$WORKER_HOSTNAME"
                    echo ""
                    echo "# 4️⃣  2분 대기 후 노드 상태 확인"
                    echo "sleep 120 && kubectl get nodes -o wide"
                    echo ""
                    echo "=========================================="
                    echo ""
                    echo "💡 참고: 1번 명령은 클러스터에 한 번만 실행하면 됩니다."
                    echo "   이후 추가되는 모든 워커 노드에 자동으로 적용됩니다."
                    echo ""
                fi
            else
                # 데이터가 이미 있음 - 패치 건너뜀
                echo "   → 데이터 있음 (설정됨)"
                echo "✅ ConfigMap에 이미 데이터가 있습니다. 패치를 건너뜁니다."
            fi
        fi
    fi
else
    echo "ℹ️  kubelet.conf 파일이 없습니다. (첫 조인)"
    echo "   ConfigMap 확인을 건너뜁니다."
fi

echo ""
echo ""
echo "📝 노드 상태 확인 (2-3분 후):"
echo "   kubectl get nodes -o wide"
echo "   kubectl get pods -n kube-system -l k8s-app=calico-node -o wide"
echo ""
echo "📝 로컬 로그 확인:"
echo "   sudo systemctl status kubelet"
echo "   sudo journalctl -u kubelet -f"
echo ""

