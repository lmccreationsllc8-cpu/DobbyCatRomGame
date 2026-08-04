#!/bin/bash
P=/home/builder/DobbyCatRomGame
PF=$P/.buildozer/android/platform/python-for-android/pythonforandroid
sed -n 450,520p $PF/recipes/python3/__init__.py
echo ====
sed -n 780,830p $PF/recipe.py
echo ====
sed -n 960,1020p $PF/recipe.py
echo ====
grep -RIn python_shared $PF --include=*.py 2>/dev/null | head -40
echo ====
grep -RIn LOCAL_MODULE $PF/recipes/python3 2>/dev/null | head
echo ====
find $P/.buildozer/android/platform/build-arm64-v8a -name *python*.mk 2>/dev/null
find $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster -name *.mk -path *python* 2>/dev/null
ls -la $P/.buildozer/android/platform/build-arm64-v8a/dists/boothblaster/jni/
echo DONE
