#!/bin/bash
# Build Booth Blaster debug APK inside Ubuntu (Colima/Docker on Mac).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
export PATH="/home/builder/.local/bin:/usr/local/bin:/usr/bin:/bin"
export HOME=/home/builder
export USER=builder
export PIP_BREAK_SYSTEM_PACKAGES=1
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
if [ ! -d "$JAVA_HOME" ]; then
  JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
fi
if [ ! -d "$JAVA_HOME" ]; then
  JAVA_HOME=$(dirname "$(dirname "$(readlink -f "$(which java)")")")
fi
export JAVA_HOME
export PATH="/home/builder/.local/bin:${JAVA_HOME}/bin:/usr/local/bin:/usr/bin:/bin"
unset DOBBY_AGENT_LOG || true

LOG=/home/builder/buildozer-build.log
SRC=/src
DST=/home/builder/DobbyCatRomGame

echo "=== docker buildozer start $(date) ===" | tee "$LOG"
echo "JAVA_HOME=$JAVA_HOME" | tee -a "$LOG"
java -version 2>&1 | tee -a "$LOG"

mkdir -p "$DST" /home/builder/.local/bin /home/builder/.buildozer-cache
rsync -a --delete \
  --exclude '.buildozer' --exclude 'bin' --exclude 'data' \
  --exclude '__pycache__' --exclude '.git' --exclude 'debug-*.log' \
  --exclude 'debug-*.png' --exclude 'debug-*.jpg' \
  --exclude '.venv' --exclude 'web_src' --exclude 'assets/reference' \
  --exclude '.buildozer-docker' --exclude 'keystores' \
  "$SRC/" "$DST/"

cd "$DST"
mkdir -p bin
if [ ! -e .buildozer ]; then
  ln -s /home/builder/.buildozer-cache .buildozer
fi

grep -E '^(version|package.name|requirements|android.ndk|p4a.branch|android.api) ' buildozer.spec | tee -a "$LOG"

if ! command -v buildozer >/dev/null 2>&1; then
  python3 -m pip install --user --upgrade pip wheel setuptools
  python3 -m pip install --user --upgrade "buildozer" "Cython<3" virtualenv \
    appdirs "colorama>=0.3.3" jinja2 "sh>=2,<3.0" meson ninja build toml packaging
fi

patch_ndk_aarch64_host() {
  local ndk_root=""
  for cand in \
    "/home/builder/.buildozer/android/platform"/android-ndk-* \
    "/home/builder/.buildozer-cache/android/platform"/android-ndk-* \
    "$DST/.buildozer/android/platform"/android-ndk-*
  do
    if [ -f "${cand}/build/tools/ndk_bin_common.sh" ]; then
      ndk_root="$cand"
      break
    fi
  done
  [ -z "$ndk_root" ] && return 0
  local file="$ndk_root/build/tools/ndk_bin_common.sh"
  grep -q 'linux-arm64' "$file" 2>/dev/null && return 0
  sed -i 's/  arm64) HOST_ARCH=arm64;;/  arm64|aarch64) HOST_ARCH=arm64;;/' "$file"
  if ! grep -q 'linux-arm64' "$file"; then
    sed -i '/if \[ \$HOST_TAG = darwin-arm64 \]; then/,/fi/{
      /fi/a\
\
if [ $HOST_TAG = linux-arm64 ] || [ $HOST_TAG = linux-aarch64 ]; then\
  HOST_TAG=linux-x86_64\
fi
    }' "$file"
  fi
}

accept_sdk_licenses() {
  local SDK_ROOT="/home/builder/.buildozer/android/platform/android-sdk"
  [ -d "$SDK_ROOT" ] || SDK_ROOT="/home/builder/.buildozer-cache/android/platform/android-sdk"
  [ -d "$SDK_ROOT" ] || return 0
  local SDKMANAGER=""
  if [ -x "$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" ]; then
    SDKMANAGER="$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager"
  else
    SDKMANAGER=$(find "$SDK_ROOT" -type f -name sdkmanager 2>/dev/null | head -1 || true)
  fi
  [ -z "$SDKMANAGER" ] && return 0
  mkdir -p "$HOME/.android"
  touch "$HOME/.android/repositories.cfg"
  yes | "$SDKMANAGER" --sdk_root="$SDK_ROOT" --licenses >>"$LOG" 2>&1 || true
}

apk_count() { ls -1 "$DST"/bin/*.apk 2>/dev/null | wc -l | tr -d ' '; }

patch_ndk_aarch64_host
BUILD_RC=0
set +e
buildozer android debug 2>&1 | tee -a "$LOG"
BUILD_RC=${PIPESTATUS[0]}
set -e
accept_sdk_licenses
patch_ndk_aarch64_host
if [ "$(apk_count)" = "0" ]; then
  set +e
  buildozer android debug 2>&1 | tee -a "$LOG"
  BUILD_RC=${PIPESTATUS[0]}
  set -e
fi

echo "BUILD_EXIT=$BUILD_RC" | tee -a "$LOG"
mkdir -p "$SRC/bin"
cp -v "$DST"/bin/*.apk "$SRC/bin/" 2>&1 | tee -a "$LOG" || true
ls -lah "$DST"/bin/*.apk "$SRC"/bin/*.apk 2>&1 | tee -a "$LOG" || true
echo "=== docker buildozer done $(date) ===" | tee -a "$LOG"
exit "$BUILD_RC"
