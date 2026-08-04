#!/bin/bash
set -e
P=/home/builder/DobbyCatRomGame
echo === p4a python3 version ===
grep -n version $P/.buildozer/android/platform/python-for-android/pythonforandroid/recipes/python3/__init__.py | head -20
echo === p4a hostpython3 version ===
grep -n version $P/.buildozer/android/platform/python-for-android/pythonforandroid/recipes/hostpython3/__init__.py | head -20
echo === local recipes ===
ls -la $P/p4a-recipes/
ECHO === python_shared mk ===
find $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster -name '*.mk' -print0 | xargs -l grep -l python_shared 2>/dev/null | head -20
echo === find python mk files ===
find $P/.buildozer/android/platform/build-arm64-v8a -path '*python* -name '*.mk' 2>/dev/null | head -30
echo === application jri grep ===
grep -RIn 'python' $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/jni/application 2>/dev/null | head -40
echo === libpython in mk/sh ===
grep -RIn 'libpython3' $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster --include='*.mk' --include='*.sh' 2>/dev/null | head -40
echo === bootstrap python mk ===
find $P/.buildozer/android/platform/build-arm64-v8a/build/bootstrap_builds/sdl2 -name '*.mk' -print0 | xargs grep -n python 2>/dev/null | head -40
echo === timestamps ===
ls -la --time-style=full-iso $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libmain.so $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libpython3.11.so $P/.buildozer/android/platform/build-arm64-v8a/build/bootstrap_builds/sdl2/libs/arm64-v8a/libmain.so
