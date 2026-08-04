# Booth Blaster under RCARS

Deploy the game tree to `/opt/dobby-booth-blaster` on the Pi (or set `RCARS_DOBBY_GAME_DIR` in mock). Install deps from this repo’s `requirements.txt` (`pygame`, `Pillow`, `numpy`).

RCARS launches `python main.py` as a **separate subprocess** (not embedded in Kivy). Fullscreen + TV audio + pad notes: see [controller-pi.md](controller-pi.md). Operator steps: RCARS `docs/runbook.md`.
