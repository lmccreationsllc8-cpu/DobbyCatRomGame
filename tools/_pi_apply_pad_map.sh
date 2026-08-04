#!/bin/bash
set -euo pipefail

cp /tmp/dobby-pad-sync/config.py /opt/dobby-booth-blaster/config.py
cp /tmp/dobby-pad-sync/core/input.py /opt/dobby-booth-blaster/core/input.py
mkdir -p /opt/dobby-booth-blaster/docs
cp /tmp/dobby-pad-sync/docs/controller-pi.md /opt/dobby-booth-blaster/docs/controller-pi.md
cp /tmp/dobby-pad-sync/rcars.env.example /opt/rcars-kiosk/deploy/rcars.env.example

if ! sudo grep -q DOBBY_PAD_FIRE /etc/rcars/rcars.env 2>/dev/null; then
  sudo tee -a /etc/rcars/rcars.env >/dev/null <<'EOF'

# DragonRise SNES pad (0079:0126) — probed 2026-07-30
DOBBY_PAD_FIRE=0,1,2,3
DOBBY_PAD_SELECT=8
DOBBY_PAD_START=9
EOF
  echo "appended DOBBY_PAD_* to rcars.env"
else
  echo "DOBBY_PAD already in rcars.env"
fi

sudo grep DOBBY_PAD /etc/rcars/rcars.env

sudo systemctl restart rcars-control.service
sleep 1
systemctl is-active rcars-control.service
pid=$(systemctl show -p MainPID --value rcars-control.service)
echo "control pid=$pid"
if [[ -n "$pid" && "$pid" != "0" ]]; then
  tr '\0' '\n' < "/proc/$pid/environ" | grep DOBBY_PAD || echo "WARN: DOBBY_PAD not in control environ"
fi

python3 - <<'PY'
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("cfg", "/opt/dobby-booth-blaster/config.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)
print("defaults fire", sorted(cfg._DEFAULT_PAD_FIRE))
print("defaults select", sorted(cfg._DEFAULT_PAD_SELECT))
print("defaults start", sorted(cfg._DEFAULT_PAD_START))
PY
