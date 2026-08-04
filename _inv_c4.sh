#!/bin/bash
P=/home/builder/DobbyCatRomGame
echo STRINGS_MAIN
strings $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libmain.so | grep -i python
echo READELF_PY
readelf -d $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/libs/arm64-v8a/libpython3.11.so | head -35
echo READELF_PY3
readelf -d $P/.buildozer/android/platform/build-arm64-v8a/build/other_builds/python3/arm64-v8a__ndk_target_24/python3/android-build/libpython3.so 2>/dev/null | head -35
echo P4A_PYTHON_SHARED
grep -RIn python_shared $P/.buildozer/android/platform/python-for-android/pythonforandroid --include=*.py --include=*.mk 2>/dev/null | head -40
echo P4A_LINK_VERSION
grep -RIn link_version $P/.buildozer/android/platform/python-for-android/pythonforandroid --include=*.py 2>/dev/null | head -30
echo DONE
