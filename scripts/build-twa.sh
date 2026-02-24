#!/usr/bin/env bash
# WeWantPeace Android TWA (Trusted Web Activity) APK 빌드 스크립트
# 필요: Node.js 18+, Java 17+, bubblewrap CLI
#
# 사용법:
#   chmod +x scripts/build-twa.sh
#   ./scripts/build-twa.sh [--release]
#
# 환경변수:
#   KEYSTORE_PASS  - keystore 비밀번호 (기본: 대화형 입력)
#   KEY_ALIAS      - key alias (기본: wewantpeace)
#   KEY_PASS       - key 비밀번호 (기본: KEYSTORE_PASS와 동일)

set -euo pipefail

RELEASE=false
ANDROID_DIR="$(cd "$(dirname "$0")/.." && pwd)/android"
CONFIG_FILE="$ANDROID_DIR/bubblewrap-config.json"

# 인자 파싱
for arg in "$@"; do
  case $arg in
    --release) RELEASE=true ;;
    *) echo "알 수 없는 옵션: $arg" && exit 1 ;;
  esac
done

echo "=== WeWantPeace TWA 빌드 시작 ==="
echo "릴리즈 모드: $RELEASE"

# bubblewrap CLI 확인
if ! command -v bubblewrap &> /dev/null; then
  echo "[설치] bubblewrap CLI 설치 중..."
  npm install -g @bubblewrap/cli
fi

# android/ 디렉토리로 이동
cd "$ANDROID_DIR"

# bubblewrap-config.json 확인
if [ ! -f "$CONFIG_FILE" ]; then
  echo "[오류] bubblewrap-config.json을 찾을 수 없습니다: $CONFIG_FILE"
  exit 1
fi

# Android 프로젝트 초기화 (처음 실행 시)
if [ ! -f "$ANDROID_DIR/build.gradle" ]; then
  echo "[초기화] bubblewrap init..."
  bubblewrap init --manifest "$(jq -r '.webManifestUrl' "$CONFIG_FILE")"
fi

# 빌드
if [ "$RELEASE" = true ]; then
  echo "[빌드] 릴리즈 APK 빌드 중..."

  KEY_ALIAS="${KEY_ALIAS:-wewantpeace}"
  SIGNING_KEY_PATH="$ANDROID_DIR/android/signing-key.jks"

  # 서명키가 없으면 생성
  if [ ! -f "$SIGNING_KEY_PATH" ]; then
    echo "[서명키] signing-key.jks 생성 중..."
    mkdir -p "$ANDROID_DIR/android"
    keytool -genkeypair \
      -v \
      -keystore "$SIGNING_KEY_PATH" \
      -alias "$KEY_ALIAS" \
      -keyalg RSA \
      -keysize 2048 \
      -validity 10000 \
      -dname "CN=WeWantPeace, OU=App, O=WeWantPeace, L=Seoul, S=Seoul, C=KR"
    echo "[서명키] 생성 완료: $SIGNING_KEY_PATH"
    echo "[경고] 이 키파일을 안전하게 보관하고 절대 git에 커밋하지 마세요!"
  fi

  bubblewrap build \
    --skipPwaValidation

  APK_PATH="$ANDROID_DIR/app-release-signed.apk"
  AAB_PATH="$ANDROID_DIR/app-release-bundle/release/app-release.aab"

  echo ""
  echo "=== 빌드 완료 ==="
  [ -f "$APK_PATH" ] && echo "APK: $APK_PATH"
  [ -f "$AAB_PATH" ] && echo "AAB (Play Store용): $AAB_PATH"
else
  echo "[빌드] 디버그 APK 빌드 중..."
  bubblewrap build --skipPwaValidation

  APK_PATH="$ANDROID_DIR/app-debug.apk"
  echo ""
  echo "=== 빌드 완료 ==="
  [ -f "$APK_PATH" ] && echo "APK: $APK_PATH"
fi

echo ""
echo "Play Store 업로드 절차:"
echo "  1. Google Play Console → 앱 만들기"
echo "  2. 내부 테스트 → AAB 업로드: $AAB_PATH"
echo "  3. assetlinks.json 설정: https://wewantpeace.fly.dev/.well-known/assetlinks.json"
echo "  4. SHA-256 핑거프린트: keytool -list -v -keystore $SIGNING_KEY_PATH -alias $KEY_ALIAS"
