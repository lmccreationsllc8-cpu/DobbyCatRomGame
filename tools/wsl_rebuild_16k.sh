#!/bin/bash
# Clean rebuild with NDK 28b / p4a develop for 16 KB page sizes.
set -euo pipefail
export HOME=/home/builder
export USER=builder
export PATH=/home/builder/bin:/home/builder/.local/bin:/usr/local/bin:/usr/bin:/bin
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PIP_BREAK_SYSTEM_PACKAGES=1
export ANDROID_HOME=/home/builder/.buildozer/android/platform/android-sdk

LOG=/home/builder/buildozer-build.log
SRC=/mnt/c/Users/Dad/Documents/DobbyCatRomGame
DST=/home/builder/DobbyCatRomGame

echo "=== rebuild_16k start $(date) uid=$(id -u) ===" | tee "$LOG"

# Ignore rsync attr/time errors on mixed root/builder ownership (code 23).
rsync -rltD --delete \
  --exclude '.buildozer' --exclude 'bin' --exclude 'data' --exclude '_apk_libs' \
  --exclude '__pycache__' --exclude '.git' --exclude 'debug-*.log' \
  --exclude '_*' \
  "$SRC/" "$DST/" || {
    code=$?
    if [ "$code" -ne 23 ] && [ "$code" -ne 24 ]; then
      exit "$code"
    fi
    echo "rsync warning code=$code (continuing)" | tee -a "$LOG"
  }

cd "$DST"
# Prefer wiping only the platform build cache; full .buildozer wipe if present
rm -rf .buildozer
mkdir -p bin

grep -E '^(requirements|android\.ndk|android\.api|p4a\.branch|version) ' buildozer.spec | tee -a "$LOG"

/usr/bin/python3 -m pip install -q --user --break-system-packages \
  appdirs 'colorama>=0.3.3' jinja2 'sh>=2,<3.0' \
  meson ninja build toml packaging setuptools 'wheel~=0.43.0' \
  buildozer 'Cython<3' virtualenv

echo "Starting buildozer android debug at $(date)" | tee -a "$LOG"
buildozer android debug >> "$LOG" 2>&1
echo "Build finished exit=$? at $(date)" | tee -a "$LOG"

ls -la bin/ | tee -a "$LOG"
mkdir -p "$SRC/bin"
cp -v bin/*.apk "$SRC/bin/" | tee -a "$LOG"
echo "=== rebuild_16k done $(date) ===" | tee -a "$LOG"
