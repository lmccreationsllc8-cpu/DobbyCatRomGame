#!/bin/bash
set -e
export HOME=/home/builder
export PATH=/home/builder/.local/bin:/usr/local/bin:/usr/bin:/bin
cd /home/builder/DobbyCatRomGame
rm -rf .buildozer/android/platform/build-arm64-v8a/build/other_builds/python3
rm -rf .buildozer/android/platform/build-arm64-v8a/build/bootstrap_builds
echo WIPED
date -Is
buildozer -v android debug
echo BUILD_OK
date -Is
ls -la bin/
echo DONE
