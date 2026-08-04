# Booth Blaster — Raspberry Pi controller (2.4G SNES)

Use a **2.4 GHz wireless SNES-style pad** with its USB dongle. No special Linux driver is required; pygame sees it as a generic HID joystick. DualShock / DualSense over USB or Bluetooth still works via overlapping button indices.

## RCARS kiosk launch

When launched from RCARS (home monkey logo long-press), the control process sets:

| Env | Purpose |
|---|---|
| `DOBBY_GAME_FULLSCREEN=1` | Fullscreen pygame (stage TV) |
| `SDL_VIDEODRIVER=x11` | Pi X11 |
| `SDL_VIDEO_FULLSCREEN_DISPLAY` | pygame `display=` index for the TV (`1` = HDMI-2 on booth) |
| `SDL_VIDEO_WINDOW_POS` | Stage output origin from xrandr (e.g. `720,0` for HDMI-2) |
| `PULSE_SINK` | TV HDMI sink (same as RCARS stage audio) |
| `DOBBY_DATA_DIR` | Writable leaderboard path (default `/var/lib/rcars/booth-blaster`) |

`create_display()` uses `pygame.display.set_mode(..., display=index)` sized from `get_desktop_sizes()[index]` — do not rely on `SDL_VIDEO_FULLSCREEN_DISPLAY` alone (pygame FULLSCREEN without `display=` lands on the primary touch bar).

Idle quit and **Select+Start** exit with code **0** so RCARS restores attract. See RCARS `docs/runbook.md` § Booth Blaster.

## Plug in

1. Insert the USB dongle **before** launching the game (hot-plug refreshes joysticks, but cold-plug is more reliable on the Pi).
2. Start Booth Blaster as usual.
3. On connect you should see a log line like:
   `[input] pad connected name='USB Gamepad' profile=snes buttons=...`

## Controls

Booth pad on LaserMonkeyKiosk2 is a **DragonRise** USB dongle (`lsusb`: `0079:0126`), pygame name `Controller` (13 buttons, axes 0/1 for D-pad).

| Action | SNES (booth DragonRise) | Notes |
|---|---|---|
| Move | D-pad → axes **0** / **1** | Hat may also report; code reads both |
| Fire / confirm | Face buttons **0–3** (X/A/B/Y) | All face buttons fire for booth use |
| Select / Start | **8** / **9** | Quit combo |
| Quit | **Select + Start** hold (~1.25s) | Same combo as DualShock |

Pinned on the Pi in `/etc/rcars/rcars.env` (inherited by the game via control):

```bash
DOBBY_PAD_FIRE=0,1,2,3
DOBBY_PAD_SELECT=8
DOBBY_PAD_START=9
```

## If controls feel wrong — probe

With the dongle plugged in:

```bash
cd /path/to/DobbyCatRomGame
python tools/probe_joystick.py
```

Press each face button and the D-pad. Note the printed `button=` / `hat=` / `axis=` indices.

Override without a code change (comma-separated indices):

```bash
export DOBBY_PAD_FIRE=0,1
export DOBBY_PAD_SELECT=6,8
export DOBBY_PAD_START=7,9
# then launch the game in the same shell
```

## Device missing

1. `lsusb` — confirm the dongle appears.
2. Ensure your user is in the `input` group (`sudo usermod -aG input $USER`, then re-login).
3. Stop anything else that might exclusive-grab the pad (emulators, another pygame instance).
4. Re-run the probe tool.

## DualShock

No extra setup: Cross fires, Share/Options (and common remaps) drive Select/Start for the quit combo.
