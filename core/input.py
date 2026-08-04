"""Keyboard + gamepad (SNES / DualShock) input mapping, plus phone touch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pygame

from config import (
    EXIT_COMBO_HOLD_SECONDS,
    HEIGHT,
    PAD_FIRE_BUTTONS,
    PAD_SELECT_BUTTONS,
    PAD_START_BUTTONS,
    ROOT,
    WIDTH,
)

# #region agent log
_DBG_LAST_MS = 0


def _agent_dbg(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    """NDJSON debug ingest for session 0b90b9 (throttled by caller)."""
    try:
        import json
        import time
        from pathlib import Path

        payload = {
            "sessionId": "0b90b9",
            "runId": "post-fix",
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
            "timestamp": int(time.time() * 1000),
        }
        line = json.dumps(payload)
        for path in (ROOT / "debug-0b90b9.log", Path("debug-0b90b9.log")):
            try:
                with path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except OSError:
                pass
        try:
            from core.platform import writable_data_dir

            with (writable_data_dir() / "debug-0b90b9.log").open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
    except Exception:
        pass


# #endregion

# Common DualShock / XInput-style button indices (kept for readability / docs).
BTN_CROSS = 0  # A / Cross — fire / confirm
BTN_CIRCLE = 1
BTN_SQUARE = 2
BTN_TRIANGLE = 3
BTN_SELECT = 8  # Share / Select / Back
BTN_START = 9  # Options / Start

# Right-side fire zone kept only as a soft hint constant (steering uses full width).
FIRE_ZONE_LEFT_FRAC = 0.78

PadProfile = str  # "snes" | "dualshock" | "generic"


def classify_pad(name: str) -> PadProfile:
    """Heuristic pad profile from pygame joystick name."""
    n = (name or "").lower()
    # SNES / 2.4G clones first — names often also contain "wireless controller".
    # DragonRise USB dongle (0079:0126) reports pygame name "Controller".
    if n == "controller" or any(
        key in n for key in ("snes", "usb gamepad", "2.4g", "retro", "nintendo", "dragonrise")
    ):
        return "snes"
    if any(
        key in n
        for key in (
            "dualshock",
            "dualsense",
            "wireless controller",
            "ps4",
            "ps5",
            "sony",
        )
    ):
        return "dualshock"
    return "generic"


def primary_pad_profile() -> Optional[PadProfile]:
    """Return profile of the first connected joystick, or None if none."""
    try:
        if pygame.joystick.get_count() <= 0:
            return None
        joy = pygame.joystick.Joystick(0)
        return classify_pad(joy.get_name())
    except Exception:
        return None


def control_prompt_lines(action: str) -> tuple[str, str, str]:
    """HUD lines for confirm/start/restart, move, and quit — pad-aware when connected.

    ``action`` is the verb after the em dash, e.g. \"Start\" or \"Restart\".
    """
    profile = primary_pad_profile()
    if profile == "snes":
        return (
            f"Start — {action}",
            "D-pad to move · A/B/X/Y to fire",
            "Hold Select — Quit",
        )
    if profile == "dualshock":
        return (
            f"Options — {action}",
            "Stick / D-pad to move · Cross to fire",
            "Hold Share — Quit",
        )
    if profile == "generic":
        return (
            f"Start — {action}",
            "D-pad / stick to move · A/B/X/Y to fire",
            "Hold Select — Quit",
        )
    # Touch / keyboard (no pad): keep phone + desktop hints.
    return (
        f"Tap / Space — {action}",
        "Drag to move · hold to fire",
        "Esc hold / Back hold — Quit",
    )


@dataclass
class InputState:
    move_x: float = 0.0
    move_y: float = 0.0
    fire_pressed: bool = False
    fire_held: bool = False
    confirm_pressed: bool = False
    exit_held: bool = False
    exit_ready: bool = False
    any_activity: bool = False
    # Absolute finger/mouse X in logical canvas coords while a play touch is held.
    aim_x: Optional[float] = None


def window_to_logical(x: float, y: float) -> tuple[float, float]:
    """Map window/pixel coords to logical 1080x1920 canvas coords."""
    surf = pygame.display.get_surface()
    if surf is None:
        return x, y
    w, h = surf.get_size()
    if w <= 0 or h <= 0:
        return x, y
    return x * WIDTH / w, y * HEIGHT / h


class InputManager:
    def __init__(self) -> None:
        pygame.joystick.init()
        self._joysticks: list[pygame.joystick.Joystick] = []
        self._logged_ids: set[int] = set()
        self._refresh_joysticks()
        self._prev_fire = False
        self._prev_confirm = False
        self._exit_hold = 0.0
        # Touch / pointer state (Android often surfaces touches as mouse).
        self._pointers: dict[int, tuple[float, float]] = {}  # id -> logical (x, y)
        self._touch_confirm_edge = False
        self._android_back = False

    def _log_pad(self, joy: pygame.joystick.Joystick) -> None:
        try:
            instance_id = joy.get_instance_id()
        except Exception:
            instance_id = -1
        if instance_id in self._logged_ids:
            return
        name = joy.get_name()
        profile = classify_pad(name)
        self._logged_ids.add(instance_id)
        print(
            f"[input] pad connected name={name!r} profile={profile} "
            f"buttons={joy.get_numbuttons()} axes={joy.get_numaxes()} hats={joy.get_numhats()}",
            flush=True,
        )

    def _refresh_joysticks(self) -> None:
        self._joysticks = []
        for i in range(pygame.joystick.get_count()):
            joy = pygame.joystick.Joystick(i)
            joy.init()
            self._joysticks.append(joy)
            self._log_pad(joy)

    def _window_to_logical(self, x: float, y: float) -> tuple[float, float]:
        return window_to_logical(x, y)

    def handle_device_event(self, event: pygame.event.Event) -> None:
        if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            if event.type == pygame.JOYDEVICEREMOVED:
                self._logged_ids.clear()
            self._refresh_joysticks()
            return

        # Android hardware back — treat as exit combo so it does not kill mid-run.
        if event.type == pygame.KEYDOWN and getattr(pygame, "K_AC_BACK", None) == event.key:
            self._android_back = True
            return
        if event.type == pygame.KEYUP and getattr(pygame, "K_AC_BACK", None) == event.key:
            self._android_back = False
            return

        # Finger events use normalized 0..1 coords.
        if event.type == pygame.FINGERDOWN:
            lx, ly = event.x * WIDTH, event.y * HEIGHT
            self._pointers[event.finger_id] = (lx, ly)
            self._touch_confirm_edge = True
            return
        if event.type == pygame.FINGERMOTION:
            if event.finger_id in self._pointers:
                self._pointers[event.finger_id] = (event.x * WIDTH, event.y * HEIGHT)
            return
        if event.type == pygame.FINGERUP:
            self._pointers.pop(event.finger_id, None)
            return

        # Mouse / Android touch-as-mouse
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            lx, ly = self._window_to_logical(*event.pos)
            self._pointers[-1] = (lx, ly)
            self._touch_confirm_edge = True
            return
        if event.type == pygame.MOUSEMOTION and event.buttons[0]:
            if -1 in self._pointers:
                self._pointers[-1] = self._window_to_logical(*event.pos)
            return
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._pointers.pop(-1, None)
            return

    def poll(self, dt: float) -> InputState:
        keys = pygame.key.get_pressed()
        move_x = 0.0
        move_y = 0.0
        fire_held = False
        confirm_raw = False
        select_held = False
        start_held = False
        activity = False
        aim_x: Optional[float] = None

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            move_x -= 1.0
            activity = True
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            move_x += 1.0
            activity = True
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            move_y -= 1.0
            activity = True
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            move_y += 1.0
            activity = True
        if keys[pygame.K_SPACE] or keys[pygame.K_z] or keys[pygame.K_RETURN]:
            fire_held = True
            activity = True
        if keys[pygame.K_RETURN] or keys[pygame.K_SPACE]:
            confirm_raw = True
        if keys[pygame.K_ESCAPE]:
            # Escape hold = quit (same as holding Select / Share on a pad).
            select_held = True
            activity = True
        if keys[pygame.K_RSHIFT] or keys[pygame.K_LSHIFT]:
            select_held = True
            activity = True
        if keys[pygame.K_TAB]:
            # Tab = Start / Options — confirm only (quit is Select/Share/Esc).
            start_held = True
            confirm_raw = True
            activity = True

        # Union button sets cover SNES clones + DualShock remaps; env can override.
        fire_btns = PAD_FIRE_BUTTONS
        select_btns = PAD_SELECT_BUTTONS
        start_btns = PAD_START_BUTTONS

        # #region agent log
        pad_samples: list[dict] = []
        # #endregion
        for joy in self._joysticks:
            raw_ax = joy.get_axis(0) if joy.get_numaxes() >= 1 else None
            raw_ay = joy.get_axis(1) if joy.get_numaxes() >= 2 else None
            hat = joy.get_hat(0) if joy.get_numhats() >= 1 else None
            if joy.get_numaxes() >= 1:
                axis = joy.get_axis(0)
                if abs(axis) > 0.25:
                    move_x += max(-1.0, min(1.0, axis))
                    activity = True
            if joy.get_numaxes() >= 2:
                axis_y = joy.get_axis(1)
                if abs(axis_y) > 0.25:
                    move_y += max(-1.0, min(1.0, axis_y))
                    activity = True
            if joy.get_numhats() >= 1:
                hx, hy = joy.get_hat(0)
                if hx:
                    move_x += float(hx)
                    activity = True
                if hy:
                    move_y += float(-hy)  # pygame hat up is +1
                    activity = True

            nbtn = joy.get_numbuttons()
            fire_on = False
            start_on = False
            for idx in fire_btns:
                if nbtn > idx and joy.get_button(idx):
                    fire_held = True
                    activity = True
                    fire_on = True
                    break
            for idx in select_btns:
                if nbtn > idx and joy.get_button(idx):
                    select_held = True
                    activity = True
                    break
            # Start (SNES) / Options (DualShock): confirm start/restart only.
            for idx in start_btns:
                if nbtn > idx and joy.get_button(idx):
                    start_held = True
                    confirm_raw = True
                    activity = True
                    start_on = True
                    break
            # #region agent log
            pad_samples.append(
                {
                    "name": joy.get_name(),
                    "profile": classify_pad(joy.get_name()),
                    "raw_ax": None if raw_ax is None else round(float(raw_ax), 3),
                    "raw_ay": None if raw_ay is None else round(float(raw_ay), 3),
                    "hat": hat,
                    "ax_above_dz": raw_ax is not None and abs(raw_ax) > 0.25,
                    "ax_sub_dz": raw_ax is not None and 0.0 < abs(raw_ax) <= 0.25,
                    "fire_on": fire_on,
                    "start_on": start_on,
                    "select_on": select_held,
                }
            )
            # #endregion

        # Touch / mouse pointers — drag to steer, hold to auto-fire (full width).
        if self._pointers:
            activity = True
            # Always steer to finger X (leftmost if multi-touch). Do not reserve a
            # right-side "fire zone" that drops aim_x and caps movement short of the edge.
            xs = [lx for lx, _ly in self._pointers.values()]
            aim_x = min(xs)
            fire_held = True
            if self._touch_confirm_edge:
                confirm_raw = True
                fire_held = True

        self._touch_confirm_edge = False

        if self._android_back:
            select_held = True
            activity = True

        move_x = max(-1.0, min(1.0, move_x))
        move_y = max(-1.0, min(1.0, move_y))
        fire_pressed = fire_held and not self._prev_fire
        confirm_pressed = confirm_raw and not self._prev_confirm
        self._prev_fire = fire_held
        self._prev_confirm = confirm_raw

        # Hold Select (SNES) / Share (DualShock) to quit — separate from Start/Options confirm.
        exit_held = select_held
        if exit_held:
            self._exit_hold += dt
            activity = True
        else:
            self._exit_hold = 0.0

        # #region agent log
        global _DBG_LAST_MS
        import time as _time

        now_ms = int(_time.time() * 1000)
        pad_active = any(
            (s.get("raw_ax") not in (None, 0.0) and abs(float(s["raw_ax"])) > 0.02)
            or (s.get("raw_ay") not in (None, 0.0) and abs(float(s["raw_ay"])) > 0.02)
            or (s.get("hat") not in (None, (0, 0)))
            or s.get("fire_on")
            or s.get("start_on")
            or s.get("select_on")
            for s in pad_samples
        )
        if pad_active and now_ms - _DBG_LAST_MS >= 100:
            _DBG_LAST_MS = now_ms
            player_speed = 1200.0  # keep in sync with BoothBlaster.PLAYER_SPEED
            eff = abs(move_x) * player_speed
            _agent_dbg(
                "A,B,C,D",
                "input.py:poll",
                "pad poll sample",
                {
                    "move_x": round(move_x, 3),
                    "move_y": round(move_y, 3),
                    "fire_held": fire_held,
                    "fire_pressed": fire_pressed,
                    "confirm_pressed": confirm_pressed,
                    "confirm_raw": confirm_raw,
                    "start_held": start_held,
                    "select_held": select_held,
                    "exit_held": exit_held,
                    "exit_hold": round(self._exit_hold, 2),
                    "exit_ready": self._exit_hold >= EXIT_COMBO_HOLD_SECONDS,
                    "aim_x": aim_x,
                    "pads": pad_samples,
                    "deadzone": 0.25,
                    "player_speed": player_speed,
                    "effective_px_s": round(eff, 1),
                    "cross_screen_s": round(WIDTH / eff, 2) if eff > 1e-6 else None,
                    "touch_mode": aim_x is not None,
                },
            )
        # #endregion

        return InputState(
            move_x=move_x,
            move_y=move_y,
            fire_pressed=fire_pressed,
            fire_held=fire_held,
            confirm_pressed=confirm_pressed,
            exit_held=exit_held,
            exit_ready=self._exit_hold >= EXIT_COMBO_HOLD_SECONDS,
            any_activity=activity,
            aim_x=aim_x,
        )
