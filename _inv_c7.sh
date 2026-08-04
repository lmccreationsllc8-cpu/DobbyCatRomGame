#!/bin/bash
P=/home/builder/DobbyCatRomGame
echo G1
grep -RIn python_shared $P/.buildozer/android/platform/python-for-android 2>/dev/null | head -60
echo G2
grep -RIn python_shared $P/.buildozer/android/platform/build-arm64-v8a 2>/dev/null | head -60
echo G3
find $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster -type f -name *.mk -o -name *.properties -o -name *.env -o -name *.sh 2>/dev/null | head
echo G4
cat $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/jni/application/src/Android.mk
echo G5
ls -laR $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/jni/application/
echo G6
find $P/.buildozer/android/platform/build-arm64-v8a/build/bootstrap_builds/sdl2 -name *python* 2>/dev/null | head -40
echo DONE
