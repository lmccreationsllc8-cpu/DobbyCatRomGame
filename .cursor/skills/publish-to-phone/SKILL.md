---
name: publish-to-phone
description: >-
  Build Booth Blaster as a sideloadable Android debug APK via WSL2 Buildozer and
  get it onto Dad's phone. Use when the user says /publish-to-phone, publish to
  phone, install APK, sideload Android, or asks to put the game on their phone.
disable-model-invocation: true
---

# Publish Booth Blaster to phone

Slash skill for agents that have never shipped this repo to Android. Follow these steps exactly; do not invent Play Store / AAB / release-signing flows.

## Goal

Produce `bin/boothblaster-<version>-arm64-v8a-debug.apk` and install or hand it to the phone for sideload.

## Facts (do not guess)

| Item | Value |
|------|--------|
| Windows project | `C:/Users/Dad/Documents/DobbyCatRomGame` |
| Preferred WSL build dir | `~/DobbyCatRomGame` (Linux FS; faster than `/mnt/c`) |
| Package id | `org.dobbycat.boothblaster` |
| Config | [`buildozer.spec`](../../../buildozer.spec) — version, ABI `arm64-v8a` |
| Full docs | [`docs/android-build.md`](../../../docs/android-build.md) |
| Helper | [`tools/wsl_build_apk.sh`](../../../tools/wsl_build_apk.sh) (sync + `buildozer android debug`) |

Buildozer / python-for-android **do not run natively on Windows**. Always build inside **WSL2 Ubuntu**.

## Checklist

Copy and track:

```
Publish to phone:
- [ ] 1. Confirm WSL Ubuntu works
- [ ] 2. Sync project → ~/DobbyCatRomGame
- [ ] 3. buildozer android debug
- [ ] 4. Copy APK to Windows bin/
- [ ] 5. Optional 16 KB alignment check
- [ ] 6. Install on phone (adb or file copy)
- [ ] 7. Smoke-test on device
```

## Step 1 — WSL ready

From PowerShell:

```powershell
wsl -d Ubuntu -- bash -lc "uname -a && which buildozer || echo 'NO_BUILDOZER'"
```

If Buildozer missing, install deps from [`docs/android-build.md`](../../../docs/android-build.md) (apt packages + `pip3 install --user buildozer …`). Do not skip `PIP_BREAK_SYSTEM_PACKAGES` / pip.conf on Ubuntu 24+.

## Step 2 — Sync + build

Prefer Linux filesystem sync (from Ubuntu):

```bash
rsync -a --exclude '.buildozer' --exclude 'bin' --exclude 'data' \
  --exclude '.git' --exclude 'assets/reference' --exclude '__pycache__' \
  --exclude '_*.sh' \
  /mnt/c/Users/Dad/Documents/DobbyCatRomGame/ ~/DobbyCatRomGame/
cd ~/DobbyCatRomGame
export PATH="$HOME/.local/bin:$PATH"
buildozer android debug
```

Or run the helper if the WSL user/layout matches it:

```bash
bash /mnt/c/Users/Dad/Documents/DobbyCatRomGame/tools/wsl_build_apk.sh
```

First build is long (SDK/NDK/pygame-ce). Later builds are faster.

### License / Aidl failure

If build stops on licenses / Aidl:

```bash
yes | ~/.buildozer/android/platform/android-sdk/tools/bin/sdkmanager \
  --sdk_root=$HOME/.buildozer/android/platform/android-sdk --licenses
~/.buildozer/android/platform/android-sdk/tools/bin/sdkmanager \
  --sdk_root=$HOME/.buildozer/android/platform/android-sdk \
  "platform-tools" "platforms;android-35" "build-tools;35.0.0"
cd ~/DobbyCatRomGame && buildozer android debug
```

## Step 3 — Copy APK to Windows

```bash
mkdir -p /mnt/c/Users/Dad/Documents/DobbyCatRomGame/bin
cp -v ~/DobbyCatRomGame/bin/*.apk /mnt/c/Users/Dad/Documents/DobbyCatRomGame/bin/
ls -la /mnt/c/Users/Dad/Documents/DobbyCatRomGame/bin/*.apk
```

Report the exact APK path to the user (version comes from `buildozer.spec`).

## Step 4 — Optional 16 KB check (WSL)

```bash
cd ~/DobbyCatRomGame
APK=$(ls bin/boothblaster-*-arm64-v8a-debug.apk | head -n1)
SDK_ROOT="$HOME/.buildozer/android/platform/android-sdk"
NDK_ROOT="$HOME/.buildozer/android/platform/android-ndk-r28b"
"$SDK_ROOT/build-tools/35.0.0/zipalign" -c -P 16 -v 4 "$APK"
"$NDK_ROOT/build/tools/check_elf_alignment.sh" "$APK"
```

Treat `UNALIGNED` as failure for release-quality checks; still OK to sideload debug if user only wants a playtest.

## Step 5 — Get it on the phone

**Preferred if USB debugging is on:**

```powershell
adb devices
adb install -r "C:\Users\Dad\Documents\DobbyCatRomGame\bin\<apk-name>.apk"
```

`-r` replaces an existing install. Package: `org.dobbycat.boothblaster`.

**If no adb / no device listed:** tell the user the Windows APK path and that they can copy via USB, Drive, or Messages, then allow install from that source and open the APK.

## Step 6 — Device smoke test

Ask the user (or drive via instructions) to verify:

1. Splash → title
2. Drag to move / hold to fire
3. Game over → initials → restart
4. Leaderboard survives force-stop + reopen
5. Android Back **hold** quits (kiosk-style)

## Agent rules

- Read [`docs/android-build.md`](../../../docs/android-build.md) if anything conflicts with this skill.
- Do not run Buildozer on native Windows Python.
- Do not exclude gameplay `assets/sprites` or `assets/audio` from the sync.
- Do not require Play Console, keystores, or AAB unless the user explicitly asks.
- After success, reply with: APK path, install method used, and any failed smoke items.
