# Pause Menu Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans
> to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.
> Superpowers `subagent-driven-development` is Dennis opt-in only (ask first).
> Do **not** commit, push, or install to a device until Dennis ship confirm.

**Goal:** Replace the mid-run TITLE hold-chip with a tap PAUSE chip that opens a frozen pause overlay (Continue, Return to title, Quit).

**Architecture:** Keep pause in `BoothBlaster` (no new scene). Extract overlay hit-test/draw to `core/pause_ui.py`. Add gameplay music pause helpers that do not flip mute. Add `start_pressed` / `pause_pressed` edges in `InputState` so Start/Back/P/T/Esc tap toggles pause without firing every held frame.

**Tech Stack:** pygame / pygame-ce, stdlib `unittest`, existing HUD chip + initials overlay patterns.

## Global Constraints

- Implement on the **current dirty tree**. Do not revert WIP in `games/booth_blaster.py`, `core/audio.py`, `core/platform.py`, `main.py`, or untracked `core/display_mode.py`.
- Do not change game-over **Play again / Title** buttons.
- Hold Select / Esc / Android Back (~1.25s) still quits (`inp.exit_ready`).
- Web quit stops the pygame loop; do not call `window.close`.
- No git commit/push/device install in this plan.
- Test runner is stdlib: `python -m unittest …` (no pytest required).
- Dennis ship gate: skip every “Commit” instinct.

## File map

| File | Role |
| --- | --- |
| Create: `core/pause_ui.py` | `PauseMenu` overlay: layout, click, d-pad choice, draw |
| Create: `tests/test_pause_menu.py` | Unit tests for menu + game pause wiring |
| Modify: `core/audio.py` | `pause_gameplay_music()` / `resume_gameplay_music()` (not mute) |
| Modify: `core/audio_ui.py` | `PauseChip` tap chip (MuteChip-sized); leave `HoldChip` in place |
| Modify: `core/input.py` | `start_pressed`, `pause_pressed` edges |
| Modify: `games/booth_blaster.py` | Swap TITLE hold for pause; freeze sim; wire menu actions |
| Modify: `docs/controller-pi.md` | Start/TITLE docs → pause menu |

---

### Task 1: Gameplay music pause helpers

**Files:**
- Modify: `core/audio.py` (module globals + new functions after `stop_music`)
- Test: `tests/test_pause_menu.py`

**Interfaces:**
- Consumes: existing `_initialized`, `_settings.muted`, `pygame.mixer.music`
- Produces:
  - `pause_gameplay_music() -> None`
  - `resume_gameplay_music() -> None`
  - Must not change `_settings.muted`
  - Must not clear `_music_current`
  - If muted, both are no-ops (music already paused by `set_muted`)

- [ ] **Step 1: Write the failing test**

Create `tests/test_pause_menu.py`:

```python
"""Pause menu + gameplay music pause helpers."""

from __future__ import annotations

import unittest
from unittest import mock

import pygame

from core import audio
from core.input import InputState
from core.pause_ui import PauseMenu
from games.booth_blaster import BoothBlaster, TitleScene


class GameplayMusicPauseTests(unittest.TestCase):
    def test_pause_resume_do_not_flip_mute(self) -> None:
        audio._initialized = True
        audio._settings.muted = False
        with (
            mock.patch.object(pygame.mixer.music, "pause") as paused,
            mock.patch.object(pygame.mixer.music, "unpause") as unpaused,
        ):
            audio.pause_gameplay_music()
            audio.resume_gameplay_music()
        paused.assert_called_once()
        unpaused.assert_called_once()
        self.assertFalse(audio._settings.muted)

    def test_pause_is_noop_when_muted(self) -> None:
        audio._initialized = True
        audio._settings.muted = True
        with mock.patch.object(pygame.mixer.music, "pause") as paused:
            audio.pause_gameplay_music()
        paused.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest tests.test_pause_menu.GameplayMusicPauseTests -v`

Expected: FAIL — `pause_gameplay_music` not defined (or import error on `PauseMenu` — if so, add a stub `core/pause_ui.py` with `class PauseMenu: pass` only after Task 1 tests that do not import it; keep `PauseMenu` import out of this class file until Task 2, or split imports so this class only imports `audio`).

Keep this class’s imports as:

```python
from core import audio
```

Do **not** import `PauseMenu` / `BoothBlaster` in this task’s test module header yet. Add them in later tasks.

- [ ] **Step 3: Write minimal implementation**

In `core/audio.py`, after `stop_music`:

```python
def pause_gameplay_music() -> None:
    """Pause BGM for the in-run pause menu. Does not change mute state."""
    if not _initialized or _settings.muted:
        return
    try:
        pygame.mixer.music.pause()
    except pygame.error:
        pass


def resume_gameplay_music() -> None:
    """Resume BGM after Continue. Does not unmute."""
    if not _initialized or _settings.muted:
        return
    try:
        pygame.mixer.music.unpause()
    except pygame.error:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest tests.test_pause_menu.GameplayMusicPauseTests -v`

Expected: `OK`

- [ ] **Step 5: No commit** (Dennis ship gate)

---

### Task 2: PauseMenu overlay

**Files:**
- Create: `core/pause_ui.py`
- Test: `tests/test_pause_menu.py`

**Interfaces:**
- Consumes: `config.WIDTH`, `config.HEIGHT`, `config.SCALE`, `core.platform.load_font`, `core.audio.play`
- Produces:
  - `PauseMenu.CONTINUE: str = "continue"`
  - `PauseMenu.TITLE: str = "title"`
  - `PauseMenu.QUIT: str = "quit"`
  - `PauseMenu()` with `.choice: int` in `{0, 1, 2}`
  - `hit_test(pos: tuple[int, int]) -> Optional[str]`
  - `move(direction: int) -> None` — `-1` up / `+1` down, wrap
  - `confirm() -> str` — action for current `.choice`
  - `handle_click(pos: tuple[int, int]) -> Optional[str]` — debounce 0.28s like `InitialsPicker`
  - `draw(surface: pygame.Surface) -> None`
  - Three stacked buttons, labels exactly: `Continue`, `Return to title`, `Quit`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pause_menu.py`:

```python
class PauseMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

    def test_hit_test_three_actions(self) -> None:
        menu = PauseMenu()
        self.assertEqual(menu.hit_test(menu.button_rects[0].center), PauseMenu.CONTINUE)
        self.assertEqual(menu.hit_test(menu.button_rects[1].center), PauseMenu.TITLE)
        self.assertEqual(menu.hit_test(menu.button_rects[2].center), PauseMenu.QUIT)
        self.assertIsNone(menu.hit_test((0, 0)))

    def test_move_wraps(self) -> None:
        menu = PauseMenu()
        self.assertEqual(menu.choice, 0)
        menu.move(1)
        self.assertEqual(menu.choice, 1)
        menu.move(1)
        self.assertEqual(menu.choice, 2)
        menu.move(1)
        self.assertEqual(menu.choice, 0)
        menu.move(-1)
        self.assertEqual(menu.choice, 2)
        self.assertEqual(menu.confirm(), PauseMenu.QUIT)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest tests.test_pause_menu.PauseMenuTests -v`

Expected: FAIL — `No module named 'core.pause_ui'` or missing attributes.

- [ ] **Step 3: Write `core/pause_ui.py`**

```python
"""In-run pause overlay: Continue / Return to title / Quit."""

from __future__ import annotations

import time
from typing import Optional

import pygame

from config import HEIGHT, SCALE, WIDTH
from core import audio
from core.platform import load_font

ACCENT = (255, 105, 180)
HUD = (245, 235, 210)
OK = (120, 220, 160)
PANEL = (20, 24, 40, 210)


def _sx(value: float) -> int:
    return max(1, int(round(value * SCALE)))


class PauseMenu:
    CONTINUE = "continue"
    TITLE = "title"
    QUIT = "quit"
    _ACTIONS = (CONTINUE, TITLE, QUIT)
    _LABELS = ("Continue", "Return to title", "Quit")

    def __init__(self) -> None:
        self._font = load_font(40)
        self._font_lg = load_font(72, bold=True)
        self.choice = 0
        self.button_rects: list[pygame.Rect] = []
        self.panel_rect = pygame.Rect(0, 0, 1, 1)
        self._last_click_ts = 0.0
        self._click_debounce_s = 0.28
        self._layout()

    def _layout(self) -> None:
        bw, bh, gap = _sx(640), _sx(110), _sx(28)
        total_h = 3 * bh + 2 * gap
        top = HEIGHT // 2 - total_h // 2 + _sx(40)
        cx = WIDTH // 2
        self.button_rects = []
        for i in range(3):
            rect = pygame.Rect(0, 0, bw, bh)
            rect.centerx = cx
            rect.top = top + i * (bh + gap)
            self.button_rects.append(rect)
        pad = _sx(36)
        self.panel_rect = pygame.Rect(
            self.button_rects[0].left - pad,
            self.button_rects[0].top - _sx(160),
            bw + pad * 2,
            total_h + _sx(200),
        )

    def hit_test(self, pos: tuple[int, int]) -> Optional[str]:
        for i, rect in enumerate(self.button_rects):
            if rect.collidepoint(pos):
                return self._ACTIONS[i]
        return None

    def move(self, direction: int) -> None:
        if direction == 0:
            return
        self.choice = (self.choice + (1 if direction > 0 else -1)) % 3
        audio.play("ui_blip")

    def confirm(self) -> str:
        return self._ACTIONS[self.choice]

    def handle_click(self, pos: tuple[int, int]) -> Optional[str]:
        action = self.hit_test(pos)
        if action is None:
            return None
        now = time.time()
        if now - self._last_click_ts < self._click_debounce_s:
            return None
        self._last_click_ts = now
        self.choice = self._ACTIONS.index(action)
        return action

    def draw(self, surface: pygame.Surface) -> None:
        dim = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))
        panel = pygame.Surface(self.panel_rect.size, pygame.SRCALPHA)
        panel.fill(PANEL)
        surface.blit(panel, self.panel_rect.topleft)
        title = self._font_lg.render("PAUSED", True, ACCENT)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, self.panel_rect.top + _sx(80))))
        for i, (rect, label) in enumerate(zip(self.button_rects, self._LABELS)):
            selected = self.choice == i
            color = OK if selected else HUD
            pygame.draw.rect(surface, color, rect, width=3 if selected else 2, border_radius=_sx(12))
            txt = self._font.render(label, True, color)
            surface.blit(txt, txt.get_rect(center=rect.center))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest tests.test_pause_menu.PauseMenuTests -v`

Expected: `OK`

- [ ] **Step 5: No commit** (Dennis ship gate)

---

### Task 3: Input edges for pause / Start

**Files:**
- Modify: `core/input.py` (`InputState` dataclass + `InputManager.poll`)
- Test: `tests/test_pause_menu.py`

**Interfaces:**
- Consumes: existing `start_held`, `_android_back`, keyboard `K_p`
- Produces:
  - `InputState.start_pressed: bool` — True one poll when `start_held` rises
  - `InputState.pause_pressed: bool` — True one poll when `K_p` rises **or** `_android_back` rises
  - Esc / `T` stay as KEYDOWN in the scene (Task 5), not here — Esc is already `select_held` for quit hold
  - `start_pressed` must not be true every frame of a Start hold

- [ ] **Step 1: Write the failing test**

```python
class InputPauseEdgeTests(unittest.TestCase):
    def test_input_state_has_edges(self) -> None:
        inp = InputState()
        self.assertFalse(inp.start_pressed)
        self.assertFalse(inp.pause_pressed)
```

This passes once fields exist. Also add a comment-only reminder: `InputManager.poll` sets them. A full pygame joystick poll test is out of scope; verify fields exist and defaults are False.

- [ ] **Step 2: Run test — expect FAIL** (`start_pressed` missing)

Run: `python -m unittest tests.test_pause_menu.InputPauseEdgeTests -v`

- [ ] **Step 3: Implement**

In `InputState`:

```python
    start_pressed: bool = False
    pause_pressed: bool = False
```

In `InputManager.__init__`:

```python
        self._prev_start = False
        self._prev_pause_key = False
        self._prev_android_back = False
```

In `poll`, after `start_held` is known and before `return InputState(...)`:

```python
        pause_key = bool(keys[pygame.K_p])
        start_pressed = start_held and not self._prev_start
        pause_pressed = (pause_key and not self._prev_pause_key) or (
            self._android_back and not self._prev_android_back
        )
        self._prev_start = start_held
        self._prev_pause_key = pause_key
        self._prev_android_back = self._android_back
```

Pass `start_pressed=start_pressed` and `pause_pressed=pause_pressed` into the `InputState(...)` constructor.

- [ ] **Step 4: Run test**

Run: `python -m unittest tests.test_pause_menu.InputPauseEdgeTests -v`

Expected: `OK`

- [ ] **Step 5: No commit** (Dennis ship gate)

---

### Task 4: PauseChip tap control

**Files:**
- Modify: `core/audio_ui.py` (add `PauseChip` after `MuteChip`; do **not** delete `HoldChip`)
- Test: `tests/test_pause_menu.py`

**Interfaces:**
- Consumes: same chip size as `MuteChip` (`110 * SCALE` × `48 * SCALE`)
- Produces:
  - `PauseChip(topleft: tuple[int, int])`
  - `.rect: pygame.Rect`
  - `handle_click(pos) -> bool` — True if consumed; 0.12s debounce like MuteChip; **no** audio toggle
  - `draw(surface)` — label `PAUSE`

- [ ] **Step 1: Write the failing test**

```python
from core.audio_ui import PauseChip

class PauseChipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()

    def test_click_inside_and_miss(self) -> None:
        chip = PauseChip((40, 100))
        self.assertTrue(chip.handle_click(chip.rect.center))
        self.assertFalse(chip.handle_click((0, 0)))
```

- [ ] **Step 2: Run — expect FAIL** (`PauseChip` missing)

- [ ] **Step 3: Implement `PauseChip`**

Copy `MuteChip` structure. `handle_click` only returns True/False (debounce). `draw` uses OK border and text `PAUSE`. No `audio.toggle_mute`.

- [ ] **Step 4: Run test — expect `OK`**

- [ ] **Step 5: No commit** (Dennis ship gate)

---

### Task 5: Wire pause into BoothBlaster

**Files:**
- Modify: `games/booth_blaster.py`
- Test: `tests/test_pause_menu.py`

**Interfaces:**
- Consumes: `PauseMenu`, `PauseChip`, `audio.pause_gameplay_music`, `audio.resume_gameplay_music`, `InputState.pause_pressed`, `InputState.start_pressed`
- Produces on `BoothBlaster`:
  - `_paused: bool`
  - `_pause_menu: PauseMenu`
  - `_pause_chip: PauseChip` (same topleft as current TITLE chip)
  - `_pause_cooldown: float` — ignore Start/confirm for 0.2s after opening
  - `_open_pause() -> None`
  - `_close_pause() -> None`
  - `_apply_pause_action(action: str) -> Optional[object]` — `continue` closes; `title` returns `self._return_to_title()`; `quit` sets `exit_requested = True` and returns `None`
- Removes mid-run use of `HoldChip`, `TITLE_CHIP_HOLD`, `TITLE_RETURN_HOLD`, `_title_chip`, `_title_start_hold`, `_pending_title_return`
- Game-over Title path (`_end_choice == 1` → `_return_to_title()`) stays

**Behavior (must match):**

1. PAUSE chip visible only when `not self.game_over`.
2. Tap PAUSE / `pause_pressed` / `start_pressed` / KEYDOWN `K_t` or `K_ESCAPE` while running and not initials → `_open_pause`.
3. `_open_pause`: `_paused = True`, reset menu choice to 0, `pause_gameplay_music()`, `_block_fire = True`, `_pause_cooldown = 0.2`, play `ui_confirm`.
4. While `_paused`: no sim (player/enemies/bolts/idle). Still honor `inp.exit_ready`. Still draw world + overlay. MUTE chip still works.
5. Continue: `_close_pause` → `resume_gameplay_music()`, `_block_fire = True` until next pointer-up / one frame, `_paused = False`.
6. While paused, Up/Down or `move_y` (after cooldown, with 0.2s repeat lock like `_end_choice_cooldown`) moves menu. `confirm_pressed` / `start_pressed` confirms current choice.
7. KEYDOWN `K_t` / `K_ESCAPE` / `pause_pressed` / `start_pressed` while paused and cooldown elapsed → Continue (do not confirm Title/Quit by accident).
8. `_restart` must reset `_paused` and close music pause if needed.

**handle_event order:** game-over clicks → initials → mute → if paused: pause menu click → return; else pause chip.

If `MOUSEBUTTONDOWN` has `event.touch` True, keep existing `return` (finger path supplies pos).

- [ ] **Step 1: Write the failing tests**

```python
class BoothBlasterPauseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            pass

    def test_pause_freezes_player(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        x0 = game.player.x
        game._open_pause()
        nxt = game.update(0.05, InputState(move_x=1.0, aim_x=x0 + 200))
        self.assertIs(nxt, game)
        self.assertTrue(game._paused)
        self.assertEqual(game.player.x, x0)

    def test_title_action_returns_title_scene(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        game._open_pause()
        nxt = game._apply_pause_action(PauseMenu.TITLE)
        self.assertIsInstance(nxt, TitleScene)
        self.assertFalse(game.exit_requested)

    def test_quit_action_requests_exit(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        nxt = game._apply_pause_action(PauseMenu.QUIT)
        self.assertIsNone(nxt)
        self.assertTrue(game.exit_requested)

    def test_exit_ready_still_quits_while_paused(self) -> None:
        game = BoothBlaster()
        game._assets_ready = True
        game._open_pause()
        nxt = game.update(0.05, InputState(exit_ready=True))
        self.assertIsNone(nxt)
        self.assertTrue(game.exit_requested)
```

- [ ] **Step 2: Run — expect FAIL** (`_open_pause` missing)

Run: `python -m unittest tests.test_pause_menu.BoothBlasterPauseTests -v`

- [ ] **Step 3: Implement wiring**

Concrete edit points in `games/booth_blaster.py` (line numbers will shift; search these symbols):

1. Imports: drop `HoldChip`; add `PauseChip` from `core.audio_ui` and `PauseMenu` from `core.pause_ui`.
2. Delete `TITLE_RETURN_HOLD` and `TITLE_CHIP_HOLD`.
3. In `__init__`, replace `_title_chip` / hold fields with:

```python
        self._pause_chip = PauseChip((title_x, _sx(100)))
        self._pause_menu = PauseMenu()
        self._paused = False
        self._pause_cooldown = 0.0
        self._pause_nav_cooldown = 0.0
```

4. Add methods:

```python
    def _open_pause(self) -> None:
        if self.game_over or self._entering_score or self._paused:
            return
        self._paused = True
        self._pause_menu.choice = 0
        self._pause_cooldown = 0.2
        self._pause_nav_cooldown = 0.2
        self._block_fire = True
        audio.play("ui_confirm")
        audio.pause_gameplay_music()

    def _close_pause(self) -> None:
        if not self._paused:
            return
        self._paused = False
        self._pause_cooldown = 0.2
        self._block_fire = True
        audio.resume_gameplay_music()

    def _apply_pause_action(self, action: str):
        if action == PauseMenu.CONTINUE:
            self._close_pause()
            return self
        if action == PauseMenu.TITLE:
            # Do not resume BGM — _return_to_title() fades/stops it.
            self._paused = False
            return self._return_to_title()
        if action == PauseMenu.QUIT:
            self.exit_requested = True
            return None
        return self
```

5. `handle_event`:
   - `K_t` / `K_ESCAPE`: if not `_entering_score` and not `game_over`: if `_paused` and cooldown <= 0: `_close_pause`; else `_open_pause`. Remove `_pending_title_return = True` on `K_t`.
   - Remove `_title_chip.end_hold` on mouse/finger up.
   - After mute chip, if `_paused`: `action = self._pause_menu.handle_click(pos)`; if action: stash `_pending_pause_action = action` (or apply immediately if you also handle it in `update` — prefer stashing so `update` is the only scene-switch site, matching title-return). Also `_block_fire = True`.
   - Else if not `game_over` and `_pause_chip.handle_click(pos)`: `_open_pause()`.

   Add `self._pending_pause_action: Optional[str] = None` in `__init__`.

6. `update` — **immediately after** `_ensure_assets` / music start, **before** title-return block, replace the title-return block with:

```python
        if self._pending_pause_action:
            action = self._pending_pause_action
            self._pending_pause_action = None
            nxt = self._apply_pause_action(action)
            if nxt is not self:
                return nxt

        if inp.exit_ready:
            self.exit_requested = True
            return None

        can_pause = not self._entering_score and not self.game_over
        toggle = False
        if can_pause and (inp.pause_pressed or inp.start_pressed):
            toggle = True
        if toggle:
            if self._paused:
                if self._pause_cooldown <= 0:
                    self._close_pause()
            else:
                self._open_pause()

        if self._paused:
            self._pause_cooldown = max(0.0, self._pause_cooldown - dt)
            self._pause_nav_cooldown = max(0.0, self._pause_nav_cooldown - dt)
            if self._pause_cooldown <= 0:
                if abs(inp.move_y) > 0.4 and self._pause_nav_cooldown <= 0:
                    self._pause_menu.move(1 if inp.move_y > 0 else -1)
                    self._pause_nav_cooldown = 0.2
                if inp.confirm_pressed:
                    return self._apply_pause_action(self._pause_menu.confirm())
            return self
```

Delete the old `_title_chip.update` / `start_held` / `_pending_title_return` block.

Keep the later `if inp.exit_ready` only if you did **not** already handle it above — do not duplicate. Move idle-quit **after** the paused early-return so pause freezes idle.

7. `_restart`: drop title-chip reset; set `_paused = False`, `_pending_pause_action = None`, `_pause_cooldown = 0.0`.

8. `draw`: `self._pause_chip.draw` instead of `_title_chip` when `not self.game_over`. After HUD, if `_paused`: `self._pause_menu.draw(surface)`.

- [ ] **Step 4: Run pause + campaign tests**

Run:

```
python -m unittest tests.test_pause_menu tests.test_campaign_bosses -v
```

Expected: all `OK`. If `BoothBlaster()` constructor fails without a display, follow existing `test_campaign_bosses` pattern (it already constructs `BoothBlaster()`).

- [ ] **Step 5: No commit** (Dennis ship gate)

---

### Task 6: Docs + regression sweep

**Files:**
- Modify: `docs/controller-pi.md` (lines 20, 37–38)
- Touch only those TITLE/Start sentences

- [ ] **Step 1: Update copy**

Line 20: replace mid-run TITLE chip / hold Start sentence with: mid-run **PAUSE** chip (tap) or **Start** tap opens the pause menu (Continue / Return to title / Quit). Hold Select still quits.

Table:

| Return to title | Pause menu → Return to title | Does not exit the process |
| Pause | Tap **PAUSE** chip, Start, P, T, or Esc | Does not exit the process |
| Quit app | Hold **Select** (~1.25s) or pause menu **Quit** | Esc / Share / Back hold; same as DualShock |

Keep Select / Start row but drop “title-return” wording.

- [ ] **Step 2: Grep leftover TITLE-hold**

Run: `rg -n "TITLE_CHIP|_title_chip|TITLE_RETURN|_pending_title_return|HoldChip" --glob '!docs/superpowers/**'`

Expected: `HoldChip` class still in `core/audio_ui.py` only. No game references.

- [ ] **Step 3: Full unittest**

Run: `python -m unittest discover -s tests -v`

Expected: `OK`

- [ ] **Step 4: No commit** (Dennis ship gate)

---

### Task 7: Desktop launch gate (UAT later)

**Files:** none (runtime)

**Resolver:** repo `.cursor/skills/launch-game/SKILL.md` (Windows paths in that file). This workspace is macOS — same command, this repo root.

- [ ] **Step 1:** Follow launch-game: one `python main.py` from `/Users/lasermonkey/Developer/Repos/dobby-cat-rom-game`. Do not start a second copy. Do not publish APK.

- [ ] **Step 2:** Confirm pygame hello / window. Stop after UAT: kill that PID.

This task runs only when Dennis reaches UAT (phase 7), not during Execute coding.

---

## Success criteria / DoD

- Mid-run TITLE hold-chip is gone; PAUSE tap chip sits next to MUTE.
- Pause overlay offers Continue, Return to title, Quit.
- Gameplay (movement, shots, waves, idle quit clock) frozen while paused.
- Continue resumes play and music; mute state unchanged.
- Return to title uses existing `TitleScene` handoff (process stays up).
- Quit sets `exit_requested` (same path as hold-Select).
- Start tap / P / T / Esc tap / Android Back tap toggle pause; hold-Select still quits.
- Game-over Play again / Title unchanged.
- `python -m unittest discover -s tests -v` passes.
- `docs/controller-pi.md` matches the new controls.

## Definition of done (human)

Manual script is Dennis phase 8. Minimum playtest: start a run → tap PAUSE → Continue → pause again → Return to title → start again → pause → Quit.
