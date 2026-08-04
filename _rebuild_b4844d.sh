#!/bin/bash
set -e
cd /home/builder/DobbyCatRomGame
export PATH=/home/builder/.local/bin:/usr/local/bin:/usr/bin:/bin
export HOME=/home/builder
echo START
date -Is
buildozer android clean
echo CLEAN_OK
date -Is
buildozer -v android debug
echo BUILD_OK
date -Is
ls -la bin/
echo DONE
