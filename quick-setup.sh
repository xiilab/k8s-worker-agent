#!/bin/bash
#
# K8s VPN Agent - 원클릭 설치 및 노드 추가 스크립트
#

set -e

# ================================================================
# 설정 (여기를 수정하세요)
# ================================================================
# 토큰 발급 방법: docs/TOKEN_GUIDE.md 참고
# 마스터 노드에서: kubeadm token create --print-join-command
# ================================================================
MASTER_IP="10.61.3.12"
JOIN_TOKEN="yzb9u7.lvd03ttigav26zxv"
CA_CERT_HASH="sha256:8b684de8ec14e8da526b52e4d3e3f2490cbc42a9ec6be45b51bbb4631e67b9d8"
VPN_ENABLED="false"  # VPN 사용 여부: true 또는 false
HEADSCALE_URL=""  # VPN 사용 시: https://headscale.example.com
HEADSCALE_KEY=""  # VPN 사용 시: Pre-auth key
# ================================================================

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
echo "시스템 의존성 설치를 시작합니다."
echo "  • CRI-O 컨테이너 런타임"
echo "  • Kubernetes 도구 (kubeadm, kubelet, kubectl)"
echo "  • 네트워크 도구"
echo ""
read -p "계속하시겠습니까? (y/N): " INSTALL_DEPS
echo ""

if [[ ! "$INSTALL_DEPS" =~ ^[Yy]$ ]]; then
    echo "❌ 시스템 의존성 설치를 건너뛰었습니다."
    echo "   수동으로 설치하려면: sudo ./scripts/install-dependencies.sh"
    exit 0
fi

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

# 3단계: 설정 파일 생성
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  설정 파일 생성"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

CONFIG_FILE="$SCRIPT_DIR/config/config.yaml"

# 토큰 검증 (선택사항 - 이미 올바른 토큰이 설정되어 있음)
# if [ "$JOIN_TOKEN" == "예시토큰" ]; then
#     echo "❌ 오류: 토큰이 예시 값입니다!"
#     exit 1
# fi

if [ -f "$CONFIG_FILE" ]; then
    echo "⚠️  설정 파일이 이미 존재합니다: $CONFIG_FILE"
    echo ""
    read -p "기존 파일을 덮어쓰시겠습니까? (y/N): " OVERWRITE
    echo ""
    if [[ ! "$OVERWRITE" =~ ^[Yy]$ ]]; then
        echo "✅ 기존 설정 파일을 사용합니다."
        echo ""
    else
        rm "$CONFIG_FILE"
        echo "✅ 기존 파일을 삭제했습니다."
        echo ""
    fi
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo "📝 설정 파일을 생성합니다..."
    echo ""
    echo "  • 마스터 IP: $MASTER_IP"
    echo "  • 조인 토큰: ${JOIN_TOKEN:0:6}.***************"
    echo "  • CA 해시: ${CA_CERT_HASH:0:13}***"
    echo "  • VPN 사용: $VPN_ENABLED"
    echo ""
    
    # 설정 파일 생성
    cat > "$CONFIG_FILE" <<EOF
# K8s VPN Agent 설정 파일
# 자동 생성: $(date)

master:
  ip: "${MASTER_IP}"
  hostname: "k8s-master"
  api_endpoint: "https://${MASTER_IP}:6443"
  token: "${JOIN_TOKEN}"
  ca_cert_hash: "${CA_CERT_HASH}"

vpn:
  enabled: ${VPN_ENABLED}
  type: "headscale"
  headscale_url: "${HEADSCALE_URL}"
  auth_key: "${HEADSCALE_KEY}"
  namespace: "default"

worker:
  hostname: "$(hostname)"
  labels:
    - "network=vpn"
    - "zone=remote"
  taints: []

network:
  pod_cidr: "10.244.0.0/16"
  service_cidr: "10.96.0.0/12"
  dns_domain: "cluster.local"

firewall:
  enabled: true
  vpn_port: 41641
  k8s_api_port: 6443
  kubelet_port: 10250
  nodeport_range: "30000-32767"
  additional_ports: []

agent:
  log_dir: "/var/log/k8s-vpn-agent"
  log_level: "INFO"
  health_check_interval: 30
  auto_reconnect: true
  max_retry: 5
  rollback_on_failure: true
  idempotent: true

runtime:
  type: "crio"
  version: "latest"
EOF
    
    echo "✅ 설정 파일이 생성되었습니다: $CONFIG_FILE"
    echo ""
fi

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

