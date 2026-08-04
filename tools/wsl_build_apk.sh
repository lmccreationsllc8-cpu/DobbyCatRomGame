#!/bin/bash
set -euxo pipefail
export PATH=/home/builder/.local/bin:/usr/local/bin:/usr/bin:/bin
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PIP_BREAK_SYSTEM_PACKAGES=1

# Sync key project files from Windows mount (LF)
ROOT=/home/builder/DobbyCatRomGame
WIN=/mnt/c/Users/Dad/Documents/DobbyCatRomGame
tr -d '\r' < "$WIN/buildozer.spec" > "$ROOT/buildozer.spec"
tr -d '\r' < "$WIN/p4a-recipes/pygame-ce/__init__.py" > "$ROOT/p4a-recipes/pygame-ce/__init__.py"
rsync -a --exclude '.buildozer' --exclude 'bin' --exclude 'data' --exclude '__pycache__' --exclude '.git' \
  "$WIN/" "$ROOT/"

# Force LF again after rsync for recipe/spec
tr -d '\r' < "$WIN/buildozer.spec" > "$ROOT/buildozer.spec"
tr -d '\r' < "$WIN/p4a-recipes/pygame-ce/__init__.py" > "$ROOT/p4a-recipes/pygame-ce/__init__.py"

# Drop mismatched Python 3.14 host builds so 3.11.11 pin can rebuild
rm -rf "$ROOT/.buildozer/android/platform/build-arm64-v8a/build/other_builds/hostpython3"
rm -rf "$ROOT/.buildozer/android/platform/build-arm64-v8a/build/other_builds/python3"
rm -rf "$ROOT/.buildozer/android/platform/build-arm64-v8a/build/other_builds/pygame-ce"
rm -rf "$ROOT/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster"
rm -rf "$ROOT/.buildozer/android/platform/build-arm64-v8a/packages/hostpython3"
rm -rf "$ROOT/.buildozer/android/platform/build-arm64-v8a/packages/python3"

cd "$ROOT"
rm -f /home/builder/buildozer-build.log
echo "Starting buildozer at $(date)" | tee /home/builder/buildozer-build.log
exec buildozer android debug >> /home/builder/buildozer-build.log 2>&1
