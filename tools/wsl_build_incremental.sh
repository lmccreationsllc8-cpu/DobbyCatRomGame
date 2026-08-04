#!/bin/bash
# Incremental APK build (keeps existing python/pygame caches).
set -euo pipefail
export PATH=/home/builder/.local/bin:/usr/local/bin:/usr/bin:/bin
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PIP_BREAK_SYSTEM_PACKAGES=1
export HOME=/home/builder
export USER=builder

SRC=/mnt/c/Users/Dad/Documents/DobbyCatRomGame
DST=/home/builder/DobbyCatRomGame
LOG=/home/builder/buildozer-build.log

echo "=== incremental build start $(date) ===" | tee "$LOG"

rsync -rltD \
  --exclude '.buildozer' --exclude 'bin' --exclude 'data' \
  --exclude '__pycache__' --exclude '.git' --exclude 'debug-*.log' \
  "$SRC/" "$DST/" || {
    code=$?
    if [ "$code" -ne 23 ] && [ "$code" -ne 24 ]; then
      exit "$code"
    fi
    echo "rsync warning code=$code (continuing)" | tee -a "$LOG"
  }

# Ensure LF line endings on critical files
tr -d '\r' < "$SRC/buildozer.spec" > "$DST/buildozer.spec"
if [ -f "$SRC/p4a-recipes/pygame-ce/__init__.py" ]; then
  tr -d '\r' < "$SRC/p4a-recipes/pygame-ce/__init__.py" > "$DST/p4a-recipes/pygame-ce/__init__.py"
fi

cd "$DST"
mkdir -p bin
grep -E '^(version|package.name|requirements|android.ndk|p4a.branch) ' buildozer.spec | tee -a "$LOG"

buildozer android debug >> "$LOG" 2>&1
echo "BUILD_EXIT=$?" | tee -a "$LOG"

mkdir -p "$SRC/bin"
cp -v "$DST"/bin/*.apk "$SRC/bin/" 2>&1 | tee -a "$LOG"
ls -lah "$DST"/bin/*.apk "$SRC"/bin/*.apk 2>&1 | tee -a "$LOG"
echo "=== incremental build done $(date) ===" | tee -a "$LOG"
