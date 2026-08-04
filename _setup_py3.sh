#!/bin/bash
set -e
mkdir -p /home/builder/DobbyCatRomGame/p4a-recipes/python3
echo IiIiUGluIHB5dGhvbjMgdG8gbWF0Y2ggaG9zdHB5dGhvbjM9PTMuMTEuMTEgKHA0YSBtYXN0ZXIgZGVmYXVsdHMgdG8gMy4xNCkuIiIiCgpmcm9tIHB5dGhvbmZvcmFuZHJvaWQucmVjaXBlcy5weXRob24zIGltcG9ydCBQeXRob24zUmVjaXBlIGFzIF9QeXRob24zUmVjaXBlCgoKY2xhc3MgUHl0aG9uM1JlY2lwZShfUHl0aG9uM1JlY2lwZSk6CiAgICB2ZXJzaW9uID0gIjMuMTEuMTEiCgoKcmVjaXBlID0gUHl0aG9uM1JlY2lwZSgpCg== | base64 -d > /home/builder/DobbyCatRomGame/p4a-recipes/python3/__init__.py
chown -R builder:builder /home/builder/DobbyCatRomGame/p4a-recipes/python3
cat /home/builder/DobbyCatRomGame/p4a-recipes/python3/__init__.py
ls -la /home/builder/DobbyCatRomGame/p4a-recipes/
id
getent passwd builder
sudo -u builder -H bash -lc "command -v buildozer; buildozer --version"
echo DONE
