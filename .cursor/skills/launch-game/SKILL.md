---
name: launch-game
description: >-
  Launch Booth Blaster locally with pygame on the Windows host. Use when the
  user says /launch-game, launch the game, run the game, start Booth Blaster,
  or open a playable window.
disable-model-invocation: true
---

# Launch Booth Blaster

Slash skill for starting the desktop game so the user can playtest without hunting commands.

## Goal

Run `python main.py` from the project root so a pygame window opens on the Windows desktop.

## Facts

| Item | Value |
|------|--------|
| Project root | `C:/Users/Dad/Documents/DobbyCatRomGame` |
| Entry | `main.py` |
| Caption / title | Booth Blaster (`config.TITLE`) |
| Typical deps | `pygame` / `pygame-ce` (see `requirements.txt`) |

## Steps

1. **Working directory** must be the project root (so `assets/` resolves).
2. **Check for an existing game process** in the terminals folder; do not start a second copy if one is already running unless the user asks to relaunch.
3. **Launch in background** (do not block the chat on the game loop):

```powershell
python main.py
```

On this Windows host, if the sandbox blocks the window, rerun with full permissions (`all` / unsandboxed). The game needs a real desktop display.

4. **Confirm start** by reading the terminal output for:

```text
pygame ...
Hello from the pygame community
```

If import errors appear, install deps from `requirements.txt` then retry:

```powershell
pip install -r requirements.txt
python main.py
```

5. Tell the user the window should be open. Do not require them to play through a wave unless they ask for a smoke test.

## Optional smoke (only if asked)

```powershell
$env:DOBBY_GAME_SMOKE_SECONDS = "3"; python main.py
```

Exits cleanly after ~3 seconds without a long play session.

## Agent rules

- Prefer one game window at a time.
- Do not run the Android/WSL publish flow for a simple launch (use `/publish-to-phone` for that).
- Do not commit, rebuild APKs, or edit assets unless the user also asked for fixes.
- If the user says "relaunch", kill the prior `python main.py` PID if still running, then start again.
