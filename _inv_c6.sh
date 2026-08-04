#!/bin/bash
P=/home/builder/DobbyCatRomGame
PF=$P/.buildozer/android/platform/python-for-android/pythonforandroid
grep -RIn PREBUILT_SHARED $PF --include=*.py 2>/dev/null | head -40
echo ====1
grep -RIn python_shared $PF --include=*.py 2>/dev/null | head -40
echo ====2
grep -RIn EXTRA_LDLIBS $PF --include=*.py 2>/dev/null | head -40
echo ====3
grep -RIn lpython $PF/bootstraps --include=*.py 2>/dev/null | head -40
echo ====4
grep -RIn ndk-build $PF --include=*.py 2>/dev/null | head -40
echo DONE
