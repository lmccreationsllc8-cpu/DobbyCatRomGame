#!/bin/bash
set -euxo pipefail
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export ANDROID_HOME=/home/builder/.buildozer/android/platform/android-sdk
SDKMANAGER=/home/builder/.buildozer/android/platform/android-sdk/tools/bin/sdkmanager

yes | "$SDKMANAGER" --sdk_root="$ANDROID_HOME" --licenses > /home/builder/sdk-licenses.log 2>&1 || true
tail -5 /home/builder/sdk-licenses.log

"$SDKMANAGER" --sdk_root="$ANDROID_HOME" \
  "platform-tools" \
  "platforms;android-34" \
  "build-tools;34.0.0"

ls -la "$ANDROID_HOME/build-tools" || true
ls -la "$ANDROID_HOME/platforms" || true
echo SDK_READY
