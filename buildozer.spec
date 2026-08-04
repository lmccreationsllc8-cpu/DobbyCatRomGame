[app]

# (str) Title of your application
title = Booth Blaster

# (str) Package name
package.name = boothblaster

# (str) Package domain (needed for android/ios packaging)
package.domain = org.dobbycat

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,jpeg,wav,ogg,ttf,otf,json,txt,md

# (list) List of inclusions using pattern matching
source.include_patterns = assets/*,assets/**/*

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests,bin,venv,.buildozer,.git,tools,__pycache__,data

# (str) Application versioning (method 1)
version = 0.1.9

# (list) Application requirements — no numpy/Pillow in the APK
requirements = hostpython3==3.11.11,python3==3.11.11,pygame-ce

# (str) Custom source folders for requirements
# requirements.source.kivy = ../../kivy

# (str) Presplash of the application (logo splash with BOOTH BLASTER title)
presplash.filename = %(source.dir)s/assets/sprites/splash_booth.png

# (str) Icon of the application (Dobby sprite on brand plate)
icon.filename = %(source.dir)s/assets/icon.png

# (str) Supported orientation
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 1

# (list) The Android archs to build for
android.archs = arm64-v8a

# (int) Target Android API
android.api = 35

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
# r28+ emits 16 KB-aligned ELF by default (required on this Samsung / Android 15+)
android.ndk = 28b

# (bool) enable AndroidX support
android.enable_androidx = True

# (str) python-for-android branch to use
# develop tracks NDK r28 / 16 KB page-size work
p4a.branch = develop

# (str) The directory in which python-for-android should look for your own
# build recipes (if any)
p4a.local_recipes = ./p4a-recipes

# (str) Bootstrap to use for android builds
p4a.bootstrap = sdl2

# (bool) If True, skip stripping debug symbols
#android.skip_strip = False

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

# (str) Path to build artifact storage, absolute or relative to spec file
# build_dir = ./.buildozer

# (str) Path to build output (i.e. .apk, .aab), absolute or relative to spec file
bin_dir = ./bin
