#!/bin/bash
#
# Kubespray 스타일 ConfigMap을 표준 형식으로 변환
# name/value 배열 → key:value 맵
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

MASTER_IP="${1:-10.61.3.12}"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}🔧 Kubespray ConfigMap 자동 수정${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}마스터 노드: $MASTER_IP${NC}"
echo ""

# Python 스크립트로 변환
cat > /tmp/fix_configmap.py << 'PYTHON_SCRIPT'
#!/usr/bin/env python3
import sys
import yaml
import json

def convert_extraargs(data):
    """name/value 배열을 key:value 맵으로 변환"""
    if isinstance(data, list):
        result = {}
        for item in data:
            if isinstance(item, dict) and 'name' in item and 'value' in item:
                result[item['name']] = item['value']
            else:
                # 이미 맵 형식이거나 다른 형식
                return data
        return result
    return data

def fix_configmap(configmap_yaml):
    """ConfigMap 수정"""
    try:
        # YAML 파싱
        cm = yaml.safe_load(configmap_yaml)
        
        # ClusterConfiguration 추출
        cluster_config_str = cm['data']['ClusterConfiguration']
        cluster_config = yaml.safe_load(cluster_config_str)
        
        modified = False
        
        # apiServer.extraArgs 변환
        if 'apiServer' in cluster_config and 'extraArgs' in cluster_config['apiServer']:
            old_args = cluster_config['apiServer']['extraArgs']
            new_args = convert_extraargs(old_args)
            if old_args != new_args:
                cluster_config['apiServer']['extraArgs'] = new_args
                modified = True
                print(f"✓ apiServer.extraArgs 변환: {len(new_args)} 항목", file=sys.stderr)
        
        # controllerManager.extraArgs 변환
        if 'controllerManager' in cluster_config and 'extraArgs' in cluster_config['controllerManager']:
            old_args = cluster_config['controllerManager']['extraArgs']
            new_args = convert_extraargs(old_args)
            if old_args != new_args:
                cluster_config['controllerManager']['extraArgs'] = new_args
                modified = True
                print(f"✓ controllerManager.extraArgs 변환: {len(new_args)} 항목", file=sys.stderr)
        
        # scheduler.extraArgs 변환
        if 'scheduler' in cluster_config and 'extraArgs' in cluster_config['scheduler']:
            old_args = cluster_config['scheduler']['extraArgs']
            new_args = convert_extraargs(old_args)
            if old_args != new_args:
                cluster_config['scheduler']['extraArgs'] = new_args
                modified = True
                print(f"✓ scheduler.extraArgs 변환: {len(new_args)} 항목", file=sys.stderr)
        
        if not modified:
            print("이미 올바른 형식입니다.", file=sys.stderr)
            return None
        
        # 다시 YAML로 변환
        cm['data']['ClusterConfiguration'] = yaml.dump(cluster_config, default_flow_style=False)
        
        return yaml.dump(cm, default_flow_style=False)
        
    except Exception as e:
        print(f"에러: {e}", file=sys.stderr)
        return None

if __name__ == "__main__":
    configmap_yaml = sys.stdin.read()
    result = fix_configmap(configmap_yaml)
    if result:
        print(result)
        sys.exit(0)
    else:
        sys.exit(1)
PYTHON_SCRIPT

chmod +x /tmp/fix_configmap.py

echo -e "${BLUE}1️⃣  현재 ConfigMap 백업 중...${NC}"
kubectl get cm kubeadm-config -n kube-system -o yaml > /tmp/kubeadm-config-backup-$(date +%Y%m%d-%H%M%S).yaml
echo -e "${GREEN}✓ 백업 완료: /tmp/kubeadm-config-backup-*.yaml${NC}"
echo ""

echo -e "${BLUE}2️⃣  ConfigMap 변환 중...${NC}"
kubectl get cm kubeadm-config -n kube-system -o yaml | python3 /tmp/fix_configmap.py > /tmp/kubeadm-config-fixed.yaml

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ 변환 완료${NC}"
    echo ""
    
    echo -e "${BLUE}3️⃣  변환된 ConfigMap 미리보기:${NC}"
    echo ""
    cat /tmp/kubeadm-config-fixed.yaml | grep -A 30 "extraArgs:"
    echo ""
    
    echo -e "${YELLOW}적용하시겠습니까? (y/N):${NC}"
    read -p "> " APPLY
    
    if [[ "$APPLY" =~ ^[Yy]$ ]]; then
        echo ""
        echo -e "${BLUE}4️⃣  ConfigMap 적용 중...${NC}"
        kubectl apply -f /tmp/kubeadm-config-fixed.yaml
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo -e "${GREEN}✅ ConfigMap 수정 완료!${NC}"
            echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
            echo ""
            echo -e "${YELLOW}이제 워커 노드에서 join을 시도하세요:${NC}"
            echo "  sudo ./quick-setup.sh"
            echo ""
        else
            echo -e "${RED}✗ 적용 실패${NC}"
            exit 1
        fi
    else
        echo -e "${YELLOW}취소됨${NC}"
        echo "수동으로 적용하려면:"
        echo "  kubectl apply -f /tmp/kubeadm-config-fixed.yaml"
    fi
else
    echo -e "${RED}✗ 변환 실패${NC}"
    echo "이미 올바른 형식이거나 변환할 수 없습니다."
fi

# 정리
rm -f /tmp/fix_configmap.py

echo ""
echo -e "${BLUE}백업 파일 위치:${NC}"
ls -lh /tmp/kubeadm-config-backup-*.yaml 2>/dev/null | tail -1

