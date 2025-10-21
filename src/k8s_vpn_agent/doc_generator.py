#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K8s VPN Agent - 자동 매뉴얼 생성기

이 모듈은 실행 로그를 기반으로 다음을 자동 생성합니다:
- 실행 매뉴얼 (Markdown)
- 재실행 스크립트 (Shell)
- 트러블슈팅 가이드
"""

import re
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from jinja2 import Template

from .logger import get_logger


class DocGenerator:
    """실행 로그 기반 문서 생성기"""
    
    def __init__(self, log_file: str, output_dir: str = "./docs/generated"):
        """
        Args:
            log_file: 분석할 로그 파일 경로
            output_dir: 출력 디렉토리
        """
        self.log_file = Path(log_file)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.logger = get_logger(__name__)
        
        self.execution_steps = []
        self.errors = []
        self.warnings = []
        self.config_used = {}
        
    def parse_log(self):
        """로그 파일을 파싱하여 실행 단계 추출"""
        self.logger.info(f"로그 파일 파싱: {self.log_file}")
        
        if not self.log_file.exists():
            raise FileNotFoundError(f"로그 파일을 찾을 수 없습니다: {self.log_file}")
        
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                self._parse_line(line)
        
        self.logger.info(f"총 {len(self.execution_steps)}개 단계, {len(self.errors)}개 오류, {len(self.warnings)}개 경고")
    
    def _parse_line(self, line: str):
        """로그 라인 파싱"""
        # 타임스탬프와 메시지 분리
        match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - (\w+) - (.+)', line)
        if not match:
            return
        
        timestamp, level, message = match.groups()
        
        # 단계 추출
        if "시작" in message or "Starting" in message or "수행" in message:
            self.execution_steps.append({
                "timestamp": timestamp,
                "action": message,
                "level": level
            })
        
        # 오류 추출
        if level == "ERROR":
            self.errors.append({
                "timestamp": timestamp,
                "message": message
            })
        
        # 경고 추출
        if level == "WARNING":
            self.warnings.append({
                "timestamp": timestamp,
                "message": message
            })
        
        # 설정 값 추출
        config_match = re.search(r'설정: (.+)', message)
        if config_match:
            try:
                config_data = json.loads(config_match.group(1))
                self.config_used.update(config_data)
            except json.JSONDecodeError:
                pass
    
    def generate_manual(self) -> Path:
        """실행 매뉴얼 생성
        
        Returns:
            Path: 생성된 매뉴얼 파일 경로
        """
        self.logger.info("실행 매뉴얼 생성 중...")
        
        manual_template = """# K8s VPN Agent 실행 매뉴얼
## 자동 생성

**생성 시간**: {{ generation_time }}  
**로그 파일**: {{ log_file }}

---

## 실행 요약

- **총 단계 수**: {{ total_steps }}개
- **발생한 오류**: {{ total_errors }}개
- **발생한 경고**: {{ total_warnings }}개

{% if total_errors > 0 %}
⚠️ **주의**: 실행 중 오류가 발생했습니다. 아래 트러블슈팅 섹션을 참조하세요.
{% endif %}

---

## 실행 단계

{% for step in steps %}
### {{ loop.index }}. {{ step.action }}

- **시간**: {{ step.timestamp }}
- **레벨**: {{ step.level }}

{% endfor %}

---

## 사용된 설정

```yaml
{% for key, value in config.items() %}
{{ key }}: {{ value }}
{% endfor %}
```

---

{% if errors %}
## 발생한 오류

{% for error in errors %}
### 오류 {{ loop.index }}

- **시간**: {{ error.timestamp }}
- **내용**: {{ error.message }}

{% endfor %}
{% endif %}

{% if warnings %}
## 경고 사항

{% for warning in warnings %}
- [{{ warning.timestamp }}] {{ warning.message }}
{% endfor %}
{% endif %}

---

## 재실행 방법

생성된 스크립트를 사용하여 동일한 설정으로 재실행할 수 있습니다:

```bash
./replay_script.sh
```

또는 수동으로:

```bash
k8s-vpn-agent join --config config.yaml
```

---

## 트러블슈팅

{% if errors %}
### 발생한 오류 해결 방법

{% for error in errors %}
#### {{ error.message }}

**해결 방법**:
1. 로그 파일 확인: `/var/log/k8s-vpn-agent/`
2. 설정 파일 검증: `k8s-vpn-agent validate -c config.yaml`
3. 네트워크 연결 확인: `ping <master-ip>`

{% endfor %}
{% else %}
오류 없이 성공적으로 완료되었습니다. ✅
{% endif %}

---

**자동 생성**: K8s VPN Agent Doc Generator  
**버전**: 1.0.0
"""
        
        template = Template(manual_template)
        content = template.render(
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            log_file=str(self.log_file),
            total_steps=len(self.execution_steps),
            total_errors=len(self.errors),
            total_warnings=len(self.warnings),
            steps=self.execution_steps,
            config=self.config_used,
            errors=self.errors,
            warnings=self.warnings
        )
        
        output_file = self.output_dir / "EXECUTION_MANUAL.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        self.logger.info(f"매뉴얼 생성 완료: {output_file}")
        return output_file
    
    def generate_replay_script(self) -> Path:
        """재실행 스크립트 생성
        
        Returns:
            Path: 생성된 스크립트 파일 경로
        """
        self.logger.info("재실행 스크립트 생성 중...")
        
        script_template = """#!/bin/bash
# K8s VPN Agent 재실행 스크립트
# 자동 생성: {{ generation_time }}

set -e

echo "========================================"
echo " K8s VPN Agent 재실행"
echo "========================================"
echo ""

# 로그 디렉토리 생성
mkdir -p /var/log/k8s-vpn-agent

# Python venv 활성화
if [ -f "/root/k8s-vpn-agent/venv/bin/activate" ]; then
    source /root/k8s-vpn-agent/venv/bin/activate
    echo "✅ Python venv 활성화"
else
    echo "❌ Python venv를 찾을 수 없습니다."
    exit 1
fi

# 설정 파일 확인
CONFIG_FILE="{{ config_file }}"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 설정 파일을 찾을 수 없습니다: $CONFIG_FILE"
    exit 1
fi

echo "✅ 설정 파일: $CONFIG_FILE"
echo ""

# 설정 검증
echo "설정 검증 중..."
k8s-vpn-agent validate -c "$CONFIG_FILE"

if [ $? -ne 0 ]; then
    echo "❌ 설정 검증 실패"
    exit 1
fi

echo "✅ 설정 검증 통과"
echo ""

# 에이전트 실행
echo "에이전트 실행 중..."
k8s-vpn-agent join -c "$CONFIG_FILE" {{ debug_flag }}

if [ $? -eq 0 ]; then
    echo ""
    echo "========================================"
    echo " ✅ 성공적으로 완료"
    echo "========================================"
else
    echo ""
    echo "========================================"
    echo " ❌ 실행 실패"
    echo "========================================"
    echo ""
    echo "로그 확인:"
    echo "  tail -f /var/log/k8s-vpn-agent/agent_*.log"
    exit 1
fi
"""
        
        template = Template(script_template)
        content = template.render(
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            config_file=self.config_used.get("config_file", "config.yaml"),
            debug_flag="--debug" if self.config_used.get("debug", False) else ""
        )
        
        output_file = self.output_dir / "replay_script.sh"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        # 실행 권한 부여
        output_file.chmod(0o755)
        
        self.logger.info(f"재실행 스크립트 생성 완료: {output_file}")
        return output_file
    
    def generate_troubleshooting_guide(self) -> Path:
        """트러블슈팅 가이드 생성
        
        Returns:
            Path: 생성된 가이드 파일 경로
        """
        self.logger.info("트러블슈팅 가이드 생성 중...")
        
        guide_template = """# 트러블슈팅 가이드
## 자동 생성

**생성 시간**: {{ generation_time }}  
**분석 로그**: {{ log_file }}

---

## 발견된 문제

{% if errors %}
{% for error in errors %}
### 문제 {{ loop.index }}: {{ error.message[:100] }}

**발생 시간**: {{ error.timestamp }}

**상세 내용**:
```
{{ error.message }}
```

**해결 방법**:

1. **로그 확인**
   ```bash
   tail -f /var/log/k8s-vpn-agent/agent_*.log
   ```

2. **시스템 상태 확인**
   ```bash
   k8s-vpn-agent health -c config.yaml
   ```

3. **네트워크 연결 확인**
   ```bash
   ping <master-node-ip>
   nc -zv <master-node-ip> 6443
   ```

4. **서비스 상태 확인**
   ```bash
   systemctl status kubelet
   systemctl status containerd
   ```

---

{% endfor %}
{% else %}
✅ 문제가 발견되지 않았습니다.
{% endif %}

## 일반적인 문제 해결

### VPN 연결 실패

**증상**: VPN 연결이 실패합니다.

**해결**:
- Headscale 서버 URL 확인
- Auth key 유효성 확인
- 방화벽 설정 확인

```bash
sudo ufw allow 41641/udp
```

### 클러스터 조인 실패

**증상**: 클러스터 조인이 실패합니다.

**해결**:
- 토큰 유효성 확인 (마스터에서)
- CA 인증서 해시 확인
- 네트워크 연결 확인

```bash
# 마스터 노드에서
kubeadm token list
kubeadm token create --print-join-command
```

### Kubelet 실행 실패

**증상**: Kubelet이 시작되지 않습니다.

**해결**:
- Swap 비활성화 확인
- SELinux 설정 확인
- 로그 확인

```bash
sudo swapoff -a
sudo journalctl -u kubelet -f
```

---

## 추가 리소스

- [USER_MANUAL.md](../../USER_MANUAL.md)
- [PREREQUISITES.md](../../PREREQUISITES.md)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)

---

**자동 생성**: K8s VPN Agent Doc Generator  
**버전**: 1.0.0
"""
        
        template = Template(guide_template)
        content = template.render(
            generation_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            log_file=str(self.log_file),
            errors=self.errors,
            warnings=self.warnings
        )
        
        output_file = self.output_dir / "TROUBLESHOOTING.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        
        self.logger.info(f"트러블슈팅 가이드 생성 완료: {output_file}")
        return output_file
    
    def generate_all(self) -> Dict[str, Path]:
        """모든 문서 생성
        
        Returns:
            Dict: 생성된 파일들의 경로
        """
        self.parse_log()
        
        return {
            "manual": self.generate_manual(),
            "script": self.generate_replay_script(),
            "troubleshooting": self.generate_troubleshooting_guide()
        }


class ExecutionLogger:
    """실행 과정을 구조화된 형식으로 로깅"""
    
    def __init__(self, output_file: str = "/var/log/k8s-vpn-agent/execution.json"):
        """
        Args:
            output_file: 출력 파일 경로
        """
        self.output_file = Path(output_file)
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        self.execution_log = {
            "start_time": datetime.now().isoformat(),
            "steps": [],
            "errors": [],
            "warnings": [],
            "config": {},
            "end_time": None,
            "status": "running"
        }
    
    def log_step(self, action: str, details: Optional[Dict] = None):
        """단계 로깅"""
        self.execution_log["steps"].append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details or {}
        })
        self._save()
    
    def log_error(self, message: str, details: Optional[Dict] = None):
        """오류 로깅"""
        self.execution_log["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message,
            "details": details or {}
        })
        self._save()
    
    def log_warning(self, message: str):
        """경고 로깅"""
        self.execution_log["warnings"].append({
            "timestamp": datetime.now().isoformat(),
            "message": message
        })
        self._save()
    
    def set_config(self, config: Dict):
        """설정 저장"""
        self.execution_log["config"] = config
        self._save()
    
    def finalize(self, status: str = "completed"):
        """실행 종료"""
        self.execution_log["end_time"] = datetime.now().isoformat()
        self.execution_log["status"] = status
        self._save()
    
    def _save(self):
        """파일에 저장"""
        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(self.execution_log, f, indent=2, ensure_ascii=False)

