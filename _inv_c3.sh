#!/bin/bash
set +e
P=/home/builder/DobbyCatRomGame
echo PS
grep -RIn python_shared $P/.buildozer/android/platform/build-arm64-v8a --include=*.mk 2>/dev/null | head -50
echo LP314
grep -RIn libpython3.14 $P/.buildozer/android/platform/build-arm64-v8a 2>/dev/null | head -30
echo JNI
ls $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/jni/
ls $P/.buildozer/android/platform/build-arm64-v8a/build/bootstrap_builds/sdl2/jni/
echo FIND_MOD
find $P/.buildozer/android/platform/build-arm64-v8a -name Android.mk -print0 | xargs -0 grep -l python_shared 2>/dev/null
echo SONAME
readelf -d $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libpython3.11.so | grep SONAME
echo LINKMAP
find $P/.buildozer/android/platform/build-arm64-v8a -name *.so.map 2>/dev/null | head
find $P/.buildozer/android/platform/build-arm64-v8a -name *main* 2>/dev/null | head -30
echo BUILD_LOG
ls -lt $P/.buildozer/logs 2>/dev/null | head
ls -lt $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster 2>/dev/null | head
echo DONE
