# Booth Blaster — Android debug APK (Buildozer)

Build a sideloadable **debug APK** with **Buildozer** inside **WSL2 Ubuntu**. Buildozer / python-for-android do not run natively on Windows.

## Prerequisites (Windows host)

1. Enable WSL2 and install Ubuntu:

```powershell
wsl --install -d Ubuntu
```

Reboot if prompted, then open Ubuntu once to finish user setup.

2. From Ubuntu, install build dependencies and Buildozer:

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
  build-essential libffi-dev libssl-dev autoconf automake libtool \
  pkg-config zlib1g-dev libncurses-dev cmake libltdl-dev ccache rsync

# Ubuntu 24+ / PEP 668: allow pip --user (Buildozer requires it)
printf '[global]\nbreak-system-packages = true\n' | sudo tee /etc/pip.conf

pip3 install --user --upgrade "buildozer" "Cython<3" virtualenv \
  appdirs "colorama>=0.3.3" jinja2 "sh>=2,<3.0" meson ninja build toml packaging
export PATH="$HOME/.local/bin:$PATH"
```

Optional helper scripts in `tools/`:

- `wsl_build_apk.sh` — installs deps and runs `buildozer android debug`
- `wsl_accept_sdk_licenses.sh` — accepts Android SDK licenses + installs build-tools

## Build

Prefer building on the Linux filesystem (faster / fewer permission issues than `/mnt/c`):

```bash
rsync -a --exclude '.buildozer' --exclude 'bin' --exclude 'data' \
  /mnt/c/Users/Dad/Documents/DobbyCatRomGame/ ~/DobbyCatRomGame/
cd ~/DobbyCatRomGame
buildozer android debug
```

Or from the Windows mount:

```bash
cd /mnt/c/Users/Dad/Documents/DobbyCatRomGame
buildozer android debug
```

First build downloads the Android SDK/NDK (r28b for 16 KB page-size support) and compiles pygame-ce via the local recipe in `p4a-recipes/pygame-ce` — expect a long wait. Later builds are faster. `p4a.branch = develop` is required for the NDK r28 toolchain defaults.

If the first run stops on “Aidl not found” / licenses, accept licenses then rebuild:

```bash
yes | ~/.buildozer/android/platform/android-sdk/tools/bin/sdkmanager \
  --sdk_root=$HOME/.buildozer/android/platform/android-sdk --licenses
~/.buildozer/android/platform/android-sdk/tools/bin/sdkmanager \
  --sdk_root=$HOME/.buildozer/android/platform/android-sdk \
  "platform-tools" "platforms;android-34" "build-tools;34.0.0"
buildozer android debug
```

## Output

Debug APK lands at:

```text
bin/boothblaster-0.1.3-arm64-v8a-debug.apk
```

(Exact name follows `package.name` + `version` + arch in `buildozer.spec`.)

`buildozer.spec` pins `hostpython3==3.11.11,python3==3.11.11,pygame-ce` (Ubuntu’s system Python 3.14 is too new for a reliable p4a host build).

Copy back to Windows if built in `~/DobbyCatRomGame`:

```bash
mkdir -p /mnt/c/Users/Dad/Documents/DobbyCatRomGame/bin
cp -v ~/DobbyCatRomGame/bin/*.apk /mnt/c/Users/Dad/Documents/DobbyCatRomGame/bin/
```

## Sideload on a phone

1. Copy the APK to the phone (USB, Drive, Messages, etc.).
2. On the phone: allow install from that source / “unknown apps”.
3. Open the APK and install.
4. Smoke-test: title tap → drag/fire → game over → initials → restart; confirm the leaderboard survives an app restart.

Package id: `org.dobbycat.boothblaster` (portrait, arm64-v8a).

## Notes

- APK requirements are `python3,pygame-ce` only (no numpy / Pillow).
- Keyboard + gamepad still work on desktop; phone uses touch + Android Back (hold for quit).
- Leaderboard JSON is written under Android app-private storage, not into read-only assets.
