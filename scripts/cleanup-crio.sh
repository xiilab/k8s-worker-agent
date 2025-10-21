#!/bin/bash
#
# CRI-O 설치 오류 정리 스크립트
#

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧹 CRI-O 저장소 정리 중..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 기존 CRI-O 저장소 파일 삭제
echo "🗑️  기존 저장소 파일 삭제..."
rm -f /etc/apt/sources.list.d/devel:kubic:libcontainers:stable.list
rm -f /etc/apt/sources.list.d/devel:kubic:libcontainers:stable:cri-o:*.list

# 기존 GPG 키 삭제
echo "🔑 기존 GPG 키 삭제..."
rm -f /usr/share/keyrings/libcontainers-archive-keyring.gpg
rm -f /usr/share/keyrings/libcontainers-crio-archive-keyring.gpg

# apt 캐시 정리
echo "🧽 APT 캐시 정리..."
apt-get clean

echo ""
echo "✅ 정리 완료!"
echo ""
echo "이제 다시 설치를 진행하세요:"
echo "  sudo ./scripts/install-dependencies.sh"
echo ""
