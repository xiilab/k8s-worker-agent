#!/bin/bash
#
# K8s VPN Agent - 원클릭 설치 및 노드 추가 스크립트
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 K8s VPN Agent - 원클릭 노드 추가"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Root 권한 확인
if [ "$EUID" -ne 0 ]; then
    echo "❌ 이 스크립트는 root 권한이 필요합니다."
    echo "   sudo ./quick-setup.sh 로 실행하세요."
    exit 1
fi

echo "✅ Root 권한 확인 완료"
echo ""

# 1단계: 시스템 의존성 설치
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  시스템 의존성 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "$SCRIPT_DIR/scripts/install-dependencies.sh" ]; then
    bash "$SCRIPT_DIR/scripts/install-dependencies.sh"
else
    echo "❌ install-dependencies.sh를 찾을 수 없습니다."
    exit 1
fi

echo ""
echo "✅ 시스템 의존성 설치 완료"
echo ""

# 2단계: Python 에이전트 설치
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  Python 에이전트 설치"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "$SCRIPT_DIR/scripts/install-agent.sh" ]; then
    bash "$SCRIPT_DIR/scripts/install-agent.sh"
else
    echo "❌ install-agent.sh를 찾을 수 없습니다."
    exit 1
fi

echo ""
echo "✅ Python 에이전트 설치 완료"
echo ""

# 3단계: 설정 파일 확인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  설정 파일 확인"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

CONFIG_FILE="$SCRIPT_DIR/config/config.yaml"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️  설정 파일이 없습니다. 샘플에서 복사합니다..."
    cp "$SCRIPT_DIR/config/config.yaml.sample" "$CONFIG_FILE"
    echo "✅ config.yaml 파일이 생성되었습니다."
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⚠️  설정 파일을 편집해야 합니다!"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "필수 정보를 입력하세요:"
    echo ""
    
    # 마스터 노드 IP
    read -p "📌 마스터 노드 IP: " MASTER_IP
    
    # 조인 토큰
    echo ""
    echo "💡 마스터 노드에서 다음 명령을 실행하세요:"
    echo "   kubeadm token create --print-join-command"
    echo ""
    read -p "📌 조인 토큰: " JOIN_TOKEN
    
    # CA 인증서 해시
    read -p "📌 CA 인증서 해시 (sha256:...): " CA_HASH
    
    # VPN 사용 여부
    echo ""
    read -p "🔒 VPN을 사용하시겠습니까? (y/N): " USE_VPN
    
    VPN_ENABLED="false"
    VPN_URL=""
    VPN_KEY=""
    
    if [[ "$USE_VPN" =~ ^[Yy]$ ]]; then
        VPN_ENABLED="true"
        read -p "📌 Headscale 서버 URL: " VPN_URL
        read -p "📌 Pre-auth Key: " VPN_KEY
    fi
    
    # 설정 파일 생성
    cat > "$CONFIG_FILE" <<EOF
# K8s VPN Agent 설정 파일
# 자동 생성: $(date)

master:
  ip: "${MASTER_IP}"
  api_endpoint: "https://${MASTER_IP}:6443"
  token: "${JOIN_TOKEN}"
  ca_cert_hash: "${CA_HASH}"

vpn:
  enabled: ${VPN_ENABLED}
  type: "headscale"
  server_url: "${VPN_URL}"
  auth_key: "${VPN_KEY}"

firewall:
  enabled: true
  rules:
    - port: 6443
      protocol: tcp
      description: "Kubernetes API"
    - port: 10250
      protocol: tcp
      description: "Kubelet API"
    - port: 30000-32767
      protocol: tcp
      description: "NodePort Services"
    - port: 41641
      protocol: udp
      description: "Tailscale VPN"

worker:
  hostname: "$(hostname)"
  labels: []
  taints: []

agent:
  log_level: "INFO"
  log_dir: "/var/log/k8s-vpn-agent"
  rollback_on_failure: true
EOF
    
    echo ""
    echo "✅ 설정 파일이 생성되었습니다: $CONFIG_FILE"
else
    echo "✅ 설정 파일이 이미 존재합니다: $CONFIG_FILE"
fi

echo ""

# 4단계: 설정 검증
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  설정 검증"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

source "$SCRIPT_DIR/venv/bin/activate"

k8s-vpn-agent validate -c "$CONFIG_FILE"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ 설정 파일 검증 실패"
    echo "   $CONFIG_FILE 파일을 확인하고 다시 실행하세요."
    exit 1
fi

echo ""
echo "✅ 설정 검증 완료"
echo ""

# 5단계: 클러스터 조인
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  클러스터 조인"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "지금 클러스터에 조인하시겠습니까? (Y/n): " PROCEED
echo ""

if [[ ! "$PROCEED" =~ ^[Nn]$ ]]; then
    k8s-vpn-agent join -c "$CONFIG_FILE"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "🎉 노드 추가 완료!"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""
        echo "마스터 노드에서 확인:"
        echo "  kubectl get nodes"
        echo ""
        echo "헬스체크:"
        echo "  source venv/bin/activate"
        echo "  k8s-vpn-agent health -c config/config.yaml"
        echo ""
    else
        echo ""
        echo "❌ 노드 추가 실패"
        echo ""
        echo "로그 확인:"
        echo "  tail -f /var/log/k8s-vpn-agent/agent_*.log"
        exit 1
    fi
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "⏸️  클러스터 조인을 건너뛰었습니다."
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "나중에 조인하려면:"
    echo "  source venv/bin/activate"
    echo "  k8s-vpn-agent join -c config/config.yaml"
    echo ""
fi

