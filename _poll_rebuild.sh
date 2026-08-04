#!/bin/bash
tail -n 25 /home/builder/DobbyCatRomGame/_rebuild_b4844d.log
echo ----
pgrep -af buildozer | head -5
echo ----
grep BUILD_OK /home/builder/DobbyCatRomGame/_rebuild_b4844d.log | tail -5
grep CLEAN_OK /home/builder/DobbyCatRomGame/_rebuild_b4844d.log | tail -5
grep DONE /home/builder/DobbyCatRomGame/_rebuild_b4844d.log | tail -5
grep -i error /home/builder/DobbyCatRomGame/_rebuild_b4844d.log | tail -15
