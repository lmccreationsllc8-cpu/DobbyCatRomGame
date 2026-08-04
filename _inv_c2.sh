#!/bin/bash
P=/home/builder/DobbyCatRomGame
echo FIND_MK
find $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster -name *.mk > /tmp/mks.txt
wc -l /tmp/mks.txt
echo GREP_LIBPYTHON
while IFS= read -r f; do grep -Hn libpython3 "$f" 2>/dev/null; done < /tmp/mks.txt | head -40
echo GREP_PYTHON_SHARED
while IFS= read -r f; do grep -Hn python_shared "$f" 2>/dev/null; done < /tmp/mks.txt | head -40
echo TIMESTAMPS
ls -la --time-style=full-iso $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libmain.so $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libpython3.11.so
echo REMNANTS_314
find $P/.buildozer/android/platform/build-arm64-v8a -name *python3.14* 2>/dev/null | head -40
echo INCLUDE_DIR
ls -la $P/.buildozer/android/platform/build-arm64-v8a/build/other_builds/python3/arm64-v8a__ndk_target_24/python3/android-build/android-root/include/
echo PYTHON_SHARED_FILES
find $P/.buildozer/android/platform/build-arm64-v8a -name *python_shared* 2>/dev/null | head -20
echo BOOTSTRAP_MK
find $P/.buildozer/android/platform/build-arm64-v8a/build/bootstrap_builds/sdl2 -name *.mk > /tmp/bmks.txt
while IFS= read -r f; do grep -Hn python "$f" 2>/dev/null; done < /tmp/bmks.txt | head -50
echo DONE
