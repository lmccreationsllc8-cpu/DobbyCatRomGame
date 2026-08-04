#!/bin/bash
set -e
RECIPE=/home/builder/DobbyCatRomGame/p4a-recipes/pygame-ce/__init__.py
file "$RECIPE"
python3 - <<'PY'
from pathlib import Path
t = Path("/home/builder/DobbyCatRomGame/p4a-recipes/pygame-ce/__init__.py").read_text()
print("CRLF", "\r\n" in t)
print("has Disabled", "Disabled for Android" in t)
print("has dry_run patch", "dry_run=self.dry_run" in t)
PY

# Inspect packaged pygame-ce source if present
PDIR=$(find /home/builder/DobbyCatRomGame/.buildozer/android/platform/build-arm64-v8a/build/other_builds -type d -name 'pygame-ce' 2>/dev/null | head -1)
echo "PDIR=$PDIR"
if [ -n "$PDIR" ] && [ -f "$PDIR/setup.py" ]; then
  grep -n "CCompiler.spawn\|Disabled for Android\|dry_run\|__spawn" "$PDIR/setup.py" | head -20
  sed -n '118,125p' "$PDIR/setup.py"
fi

# Also check downloaded package cache
ls /home/builder/DobbyCatRomGame/.buildozer/android/platform/build-arm64-v8a/packages/pygame-ce/ 2>/dev/null || true
