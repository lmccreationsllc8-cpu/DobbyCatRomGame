#!/bin/bash
set -e
SRC=/home/builder/DobbyCatRomGame/.buildozer/android/platform/python-for-android/pythonforandroid/recipes/python3
DST=/home/builder/DobbyCatRomGame/p4a-recipes/python3
mkdir -p $DST
if [ -d $SRC/patches ]; then cp -a $SRC/patches $DST/; fi
ls -laR $DST
chown -R builder:builder $DST
echo PATCHES_OK
