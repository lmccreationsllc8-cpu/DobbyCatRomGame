"""Booth Blaster — Space Invaders-style comic-con booth shooter."""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import pygame

from config import HEIGHT, IDLE_QUIT_SECONDS, SPRITES_DIR, WIDTH
from core import audio, leaderboard
from core.audio_ui import AudioPanel, MuteChip
from core.initials_ui import ALPHABET, InitialsPicker
from core.input import InputState, control_prompt_lines, window_to_logical
from core.platform import load_font


# --- Colors / palette (booth vibe) ---
BG_TOP = (28, 42, 72)
BG_BOTTOM = (55, 28, 48)
HUD_COLOR = (245, 235, 210)
ACCENT = (255, 105, 180)
DANGER = (255, 80, 80)
OK = (120, 220, 160)


class EnemyKind(Enum):
    BOX = auto()
    TOTE = auto()
    CHILD = auto()
    ADULT = auto()
    MAID = auto()
    BOSS = auto()


MAID_SPRITES = (
    "enemy_maid_pink.png",
    "enemy_maid_cyan.png",
    "enemy_maid_lime.png",
)

ENEMY_STATS = {
    # Wide, high-contrast silhouettes for blue booth backdrop
    EnemyKind.BOX: {"hp": 1, "score": 10, "w": 96, "h": 96, "color": (210, 170, 90), "sprite": "enemy_box.png"},
    EnemyKind.TOTE: {"hp": 2, "score": 20, "w": 100, "h": 110, "color": (255, 45, 149), "sprite": "enemy_tote.png"},
    EnemyKind.CHILD: {"hp": 2, "score": 25, "w": 100, "h": 120, "color": (80, 200, 255), "sprite": "enemy_child.png"},
    EnemyKind.ADULT: {"hp": 3, "score": 35, "w": 110, "h": 130, "color": (255, 120, 40), "sprite": "enemy_adult.png"},
    EnemyKind.MAID: {"hp": 4, "score": 45, "w": 110, "h": 140, "color": (255, 80, 200), "sprite": "enemy_maid_pink.png"},
    EnemyKind.BOSS: {"hp": 22, "score": 300, "w": 280, "h": 220, "color": (180, 120, 255), "sprite": "enemy_boss.png"},
}


def _knockout_light_bg(surf: pygame.Surface) -> pygame.Surface:
    """Safety net for leftover white studio plates. Prefers pre-cleaned RGBA assets."""
    out = surf.convert_alpha()
    # Avoid packaging numpy for the web build (pygbag scans imports).
    try:
        from core.platform import is_web

        if is_web():
            return out
    except Exception:
        pass
    try:
        import importlib
        import sys

        if sys.platform == "emscripten":
            return out
        np = importlib.import_module("numpy")

        rgb = pygame.surfarray.pixels3d(out)
        alpha = pygame.surfarray.pixels_alpha(out)
        r = rgb[:, :, 0].astype(np.int16)
        g = rgb[:, :, 1].astype(np.int16)
        b = rgb[:, :, 2].astype(np.int16)
        luma = 0.299 * r + 0.587 * g + 0.114 * b
        sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
        # Only strip obvious light plates / empty alpha — never eat dark outlines/vests.
        mask = ((luma >= 230) & (sat <= 30) & (alpha > 0)) | (alpha < 8)
        alpha[mask] = 0
        del rgb, alpha
    except Exception:
        pass
    return out


def _load_sprite(name: str, size: tuple[int, int], fallback_color: tuple[int, int, int]) -> pygame.Surface:
    path = SPRITES_DIR / name
    if path.is_file():
        try:
            img = pygame.image.load(str(path)).convert_alpha()
            img = _knockout_light_bg(img)
            # Nearest-neighbor keeps chunky pixel edges; avoid smoothscale blur/halos.
            return pygame.transform.scale(img, size)
        except pygame.error:
            pass
    surf = pygame.Surface(size, pygame.SRCALPHA)
    if name.startswith("enemy_") or name.startswith("player_") or name.startswith("barrier_"):
        pygame.draw.rect(surf, fallback_color, surf.get_rect(), border_radius=8)
        pygame.draw.rect(surf, (255, 255, 255), surf.get_rect(), width=2, border_radius=8)
    elif name == "bolt.png":
        pygame.draw.ellipse(surf, fallback_color, surf.get_rect())
    else:
        surf.fill(fallback_color)
    return surf


@dataclass
class Bolt:
    x: float
    y: float
    vy: float
    friendly: bool
    w: int = 36
    h: int = 36

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)


@dataclass
class Enemy:
    kind: EnemyKind
    x: float
    y: float
    hp: int
    col: int = 0
    row: int = 0
    sprite_key: str = ""

    @property
    def stats(self) -> dict:
        return ENEMY_STATS[self.kind]

    @property
    def rect(self) -> pygame.Rect:
        w, h = self.stats["w"], self.stats["h"]
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), w, h)

    def draw_key(self) -> str:
        return self.sprite_key or f"enemy_{self.kind.name.lower()}"


@dataclass
class Barrier:
    x: float
    y: float
    hp: int = 8
    max_hp: int = 8
    w: int = 120
    h: int = 72

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)


@dataclass
class Player:
    x: float
    y: float
    lives: int = 3
    w: int = 220
    h: int = 220
    cooldown: float = 0.0
    invuln: float = 0.0

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(int(self.x - self.w / 2), int(self.y - self.h / 2), self.w, self.h)


@dataclass
class WaveState:
    index: int = 1
    boss_pending: bool = False
    boss_active: bool = False
    clear_timer: float = 0.0


class BoothBlaster:
    """Playable Booth Blaster scene (also usable as a standalone scene)."""

    # Pad/keyboard use velocity; 1200 crosses 1080px in ~0.9s (was 520 / ~2.1s).
    PLAYER_SPEED = 1200.0
    FIRE_COOLDOWN = 0.22
    BOLT_SPEED = -900.0
    ENEMY_BOLT_SPEED = 420.0

    def __init__(self, from_title: bool = True) -> None:
        self.from_title = from_title
        self.score = 0
        self.wave = WaveState()
        self.player = Player(x=WIDTH / 2, y=HEIGHT - 280)
        self.bolts: list[Bolt] = []
        self.enemies: list[Enemy] = []
        self.barriers: list[Barrier] = []
        self.idle_timer = 0.0
        self.game_over = False
        self.won_wave_flash = 0.0
        self.dir = 1.0
        self.step_timer = 0.0
        self.step_interval = 0.55
        self.drop_pending = False
        self.exit_requested = False
        self._font: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._sprites: dict[str, pygame.Surface] = {}
        self._bg: Optional[pygame.Surface] = None
        self._assets_ready = False
        self._entering_score = False
        self._score_saved = False
        self._initials = ["A", "A", "A"]
        self._initial_idx = 0
        self._letter_cooldown = 0.0
        self._mute_chip = MuteChip((40, 100))
        self._initials_picker: Optional[InitialsPicker] = None
        self._block_fire = False
        self._spawn_barriers()
        self._spawn_wave(self.wave.index)
        audio.play_music("game")

    def _ensure_assets(self) -> None:
        if self._assets_ready:
            return
        self._font = load_font(36)
        self._font_lg = load_font(64, bold=True)
        self._sprites["player"] = _load_sprite("player_dobby.png", (220, 220), (180, 120, 70))
        self._sprites["bolt"] = _load_sprite("paw_bolt.png", (40, 40), (255, 180, 220))
        self._sprites["enemy_bolt"] = _load_sprite("paw_enemy.png", (36, 36), (255, 90, 70))
        for kind, stats in ENEMY_STATS.items():
            key = f"enemy_{kind.name.lower()}"
            self._sprites[key] = _load_sprite(stats["sprite"], (stats["w"], stats["h"]), stats["color"])
        maid_size = (ENEMY_STATS[EnemyKind.MAID]["w"], ENEMY_STATS[EnemyKind.MAID]["h"])
        maid_color = ENEMY_STATS[EnemyKind.MAID]["color"]
        for name in MAID_SPRITES:
            key = name.replace(".png", "")
            self._sprites[key] = _load_sprite(name, maid_size, maid_color)
        self._sprites["barrier"] = _load_sprite("barrier_crate.png", (120, 72), (40, 40, 48))
        bg_path = SPRITES_DIR / "bg_booth.png"
        if bg_path.is_file():
            try:
                self._bg = pygame.transform.smoothscale(
                    pygame.image.load(str(bg_path)).convert(), (WIDTH, HEIGHT)
                )
            except pygame.error:
                self._bg = None
        self._assets_ready = True

    def _spawn_barriers(self) -> None:
        ys = HEIGHT - 420
        xs = [WIDTH * 0.18, WIDTH * 0.38, WIDTH * 0.62, WIDTH * 0.82]
        self.barriers = [Barrier(x=x, y=ys) for x in xs]

    def _spawn_wave(self, wave_index: int) -> None:
        self.enemies.clear()
        self.bolts = [b for b in self.bolts if b.friendly]
        self.dir = 1.0
        self.drop_pending = False
        self.step_interval = max(0.22, 0.55 - (wave_index - 1) * 0.04)
        self.wave.boss_pending = False
        self.wave.boss_active = False
        self.wave.clear_timer = 0.0

        rows = min(4, 3 + (wave_index - 1) // 2)
        cols = 6
        top = 240
        gap_x = 150
        gap_y = 130
        origin_x = WIDTH / 2 - (cols - 1) * gap_x / 2

        for r in range(rows):
            for c in range(cols):
                if r == 0:
                    kind = EnemyKind.MAID if c % 3 == 0 else EnemyKind.ADULT
                elif r == 1:
                    kind = EnemyKind.CHILD if c % 2 == 0 else EnemyKind.TOTE
                else:
                    kind = EnemyKind.BOX
                if wave_index >= 3 and r == 0 and c % 2 == 0:
                    kind = EnemyKind.MAID
                stats = ENEMY_STATS[kind]
                sprite_key = ""
                if kind == EnemyKind.MAID:
                    sprite_key = random.choice(MAID_SPRITES).replace(".png", "")
                self.enemies.append(
                    Enemy(
                        kind=kind,
                        x=origin_x + c * gap_x,
                        y=top + r * gap_y,
                        hp=stats["hp"] + (wave_index - 1) // 3,
                        col=c,
                        row=r,
                        sprite_key=sprite_key,
                    )
                )

    def _spawn_boss(self) -> None:
        self.wave.boss_active = True
        self.wave.boss_pending = False
        stats = ENEMY_STATS[EnemyKind.BOSS]
        hp = stats["hp"] + (self.wave.index - 1) * 4
        self.enemies = [
            Enemy(kind=EnemyKind.BOSS, x=WIDTH / 2, y=320, hp=hp, col=0, row=0)
        ]
        self.step_interval = 0.4
        self.dir = 1.0
        audio.play_music("boss")
        audio.play("boss_incoming")

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.idle_timer = 0.0
            if event.key == pygame.K_m:
                audio.toggle_mute()
                audio.play("ui_blip")

        pos: Optional[tuple[int, int]] = None
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if getattr(event, "touch", False):
                return
            lx, ly = window_to_logical(*event.pos)
            pos = (int(lx), int(ly))
        elif event.type == pygame.FINGERDOWN:
            pos = (int(event.x * WIDTH), int(event.y * HEIGHT))

        if pos is None:
            return

        if self._entering_score and self._initials_picker is not None:
            consumed, self._initial_idx = self._initials_picker.handle_click(
                pos,
                self._initials,
                self._initial_idx,
                on_done=self._submit_initials,
            )
            if consumed:
                self.idle_timer = 0.0
                self._block_fire = True
                return

        if self._mute_chip.handle_click(pos):
            self.idle_timer = 0.0
            self._block_fire = True

    def update(self, dt: float, inp: InputState) -> Optional["BoothBlaster"]:
        self._ensure_assets()

        if inp.any_activity:
            self.idle_timer = 0.0
        else:
            self.idle_timer += dt
            if self.idle_timer >= IDLE_QUIT_SECONDS:
                self.exit_requested = True
                return None

        if inp.exit_ready:
            self.exit_requested = True
            return None

        if self.game_over:
            if self._block_fire:
                self._block_fire = False
                return self
            if self._entering_score:
                self._update_initials_entry(dt, inp)
            elif inp.confirm_pressed:
                self._restart()
            return self

        if self.won_wave_flash > 0:
            self.won_wave_flash -= dt
            if self.won_wave_flash <= 0 and self.wave.boss_pending:
                self._spawn_boss()
            return self

        # Player
        self.player.cooldown = max(0.0, self.player.cooldown - dt)
        self.player.invuln = max(0.0, self.player.invuln - dt)
        margin = self.player.w / 2 + 20
        if inp.aim_x is not None:
            self.player.x = max(margin, min(WIDTH - margin, float(inp.aim_x)))
        else:
            self.player.x += inp.move_x * self.PLAYER_SPEED * dt
            self.player.x = max(margin, min(WIDTH - margin, self.player.x))

        if (inp.fire_pressed or (inp.fire_held and self.player.cooldown <= 0)) and self.player.cooldown <= 0:
            self.bolts.append(Bolt(self.player.x, self.player.y - self.player.h / 2, self.BOLT_SPEED, True))
            self.player.cooldown = self.FIRE_COOLDOWN
            audio.play("shoot")

        # Enemies march
        if self.enemies:
            self.step_timer += dt
            if self.step_timer >= self.step_interval:
                self.step_timer = 0.0
                self._march_enemies()
                audio.play("march", volume=0.35 if self.wave.boss_active else 0.22)

            # Selfie / boss shooting
            for e in self.enemies:
                if e.kind in (EnemyKind.MAID, EnemyKind.ADULT, EnemyKind.BOSS) and random.random() < (0.35 if e.kind == EnemyKind.BOSS else 0.08) * dt:
                    self.bolts.append(
                        Bolt(e.x, e.y + e.stats["h"] / 2, self.ENEMY_BOLT_SPEED, False, w=34, h=34)
                    )
                    audio.play("enemy_shoot", volume=0.45)

        # Bolts
        for b in self.bolts:
            b.y += b.vy * dt
        self.bolts = [b for b in self.bolts if -40 < b.y < HEIGHT + 40]

        self._resolve_collisions()

        # Wave clear → boss → next wave
        if not self.enemies and not self.game_over and self.won_wave_flash <= 0:
            if self.wave.boss_active:
                self.wave.boss_active = False
                self.wave.index += 1
                self.won_wave_flash = 1.2
                self.score += 100
                self.wave.clear_timer = 1.2
                audio.play("boss_defeat")
                audio.play_music("game")
            elif not self.wave.boss_pending and self.wave.clear_timer <= 0:
                self.wave.boss_pending = True
                self.won_wave_flash = 1.0
                self.score += 50
                audio.play("wave_clear")

        if self.wave.clear_timer > 0:
            self.wave.clear_timer -= dt
            if (
                self.wave.clear_timer <= 0
                and not self.wave.boss_pending
                and not self.wave.boss_active
                and not self.enemies
            ):
                self._spawn_wave(self.wave.index)

        # Lose if enemies reach bottom
        for e in self.enemies:
            if e.rect.bottom >= self.player.rect.top - 10:
                self._player_hit()
                e.y -= 40  # nudge so we don't multi-hit every frame

        return self

    def _march_enemies(self) -> None:
        if not self.enemies:
            return
        step_x = 28 if not self.wave.boss_active else 40
        drop = 36
        min_x = min(e.rect.left for e in self.enemies)
        max_x = max(e.rect.right for e in self.enemies)
        if self.drop_pending:
            for e in self.enemies:
                e.y += drop
            self.dir *= -1
            self.drop_pending = False
            self.step_interval = max(0.18, self.step_interval * 0.97)
            return
        for e in self.enemies:
            e.x += step_x * self.dir
        if (self.dir > 0 and max_x + step_x >= WIDTH - 40) or (self.dir < 0 and min_x - step_x <= 40):
            self.drop_pending = True

    def _resolve_collisions(self) -> None:
        remaining_bolts: list[Bolt] = []
        dead_enemies: list[Enemy] = []
        for b in self.bolts:
            hit = False
            if b.friendly:
                for e in self.enemies:
                    if e in dead_enemies:
                        continue
                    if b.rect.colliderect(e.rect):
                        e.hp -= 1
                        hit = True
                        if e.hp <= 0:
                            self.score += e.stats["score"]
                            dead_enemies.append(e)
                            audio.play("enemy_die")
                        else:
                            audio.play("hit")
                        break
                if not hit:
                    for bar in self.barriers:
                        if bar.hp > 0 and b.rect.colliderect(bar.rect):
                            bar.hp -= 1
                            hit = True
                            audio.play("barrier_hit")
                            break
            else:
                if self.player.invuln <= 0 and b.rect.colliderect(self.player.rect):
                    self._player_hit()
                    hit = True
                if not hit:
                    for bar in self.barriers:
                        if bar.hp > 0 and b.rect.colliderect(bar.rect):
                            bar.hp -= 1
                            hit = True
                            audio.play("barrier_hit")
                            break
            if not hit:
                remaining_bolts.append(b)
        self.bolts = remaining_bolts
        if dead_enemies:
            dead = set(id(e) for e in dead_enemies)
            self.enemies = [e for e in self.enemies if id(e) not in dead]
        self.barriers = [b for b in self.barriers if b.hp > 0]

    def _player_hit(self) -> None:
        if self.player.invuln > 0:
            return
        self.player.lives -= 1
        self.player.invuln = 1.5
        self.bolts = [b for b in self.bolts if b.friendly]
        audio.play("player_hurt")
        if self.player.lives <= 0:
            self.game_over = True
            audio.play("game_over")
            audio.stop_music(fade_ms=600)
            self._begin_score_entry()

    def _begin_score_entry(self) -> None:
        self._score_saved = False
        self._initials = ["A", "A", "A"]
        self._initial_idx = 0
        self._letter_cooldown = 0.0
        self._entering_score = leaderboard.qualifies(self.score)
        self._initials_picker = (
            InitialsPicker(center=(WIDTH // 2, HEIGHT // 2 + 280), width=920)
            if self._entering_score
            else None
        )
        self._block_fire = False
        # #region agent log
        try:
            import json as _json
            from pathlib import Path as _Path
            import time as _time

            _p = _Path(__file__).resolve().parents[1] / "debug-b4844d.log"
            with _p.open("a", encoding="utf-8") as _f:
                _f.write(
                    _json.dumps(
                        {
                            "sessionId": "b4844d",
                            "runId": "initials-picker",
                            "hypothesisId": "A",
                            "location": "booth_blaster.py:_begin_score_entry",
                            "message": "score entry started",
                            "data": {
                                "score": self.score,
                                "qualifies": self._entering_score,
                                "picker": self._initials_picker is not None,
                            },
                            "timestamp": int(_time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

    def _submit_initials(self) -> None:
        name = "".join(self._initials)
        leaderboard.submit(name, self.score, self.wave.index)
        self._score_saved = True
        self._entering_score = False
        self._initials_picker = None
        audio.play("ui_confirm")
        # #region agent log
        try:
            import json as _json
            from pathlib import Path as _Path
            import time as _time

            _p = _Path(__file__).resolve().parents[1] / "debug-b4844d.log"
            with _p.open("a", encoding="utf-8") as _f:
                _f.write(
                    _json.dumps(
                        {
                            "sessionId": "b4844d",
                            "runId": "initials-picker",
                            "hypothesisId": "D",
                            "location": "booth_blaster.py:_submit_initials",
                            "message": "initials submitted",
                            "data": {"name": name, "score": self.score},
                            "timestamp": int(_time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion

    def _update_initials_entry(self, dt: float, inp: InputState) -> None:
        """Navigate the on-screen letter grid on both stick/D-pad axes."""
        cols = InitialsPicker.COLS
        rows = InitialsPicker.ROWS
        self._letter_cooldown = max(0.0, self._letter_cooldown - dt)
        if self._letter_cooldown <= 0:
            mx, my = inp.move_x, inp.move_y
            if abs(mx) > 0.4 or abs(my) > 0.4:
                cur = ALPHABET.index(self._initials[self._initial_idx])
                row, col = divmod(cur, cols)
                moved = False
                # Prefer the dominant axis so diagonal stick input does not zigzag.
                if abs(mx) >= abs(my) and abs(mx) > 0.4:
                    new_col = col + (1 if mx > 0 else -1)
                    if new_col < 0:
                        if self._initial_idx > 0:
                            self._initial_idx -= 1
                            moved = True
                    elif new_col >= cols:
                        if self._initial_idx < 2:
                            self._initial_idx += 1
                            moved = True
                    else:
                        self._initials[self._initial_idx] = ALPHABET[row * cols + new_col]
                        moved = True
                elif abs(my) > 0.4:
                    new_row = row + (1 if my > 0 else -1)
                    if 0 <= new_row < rows:
                        self._initials[self._initial_idx] = ALPHABET[new_row * cols + col]
                        moved = True
                if moved:
                    self._letter_cooldown = 0.18
                    audio.play("ui_blip")
        # Controller/keyboard confirm still works; touch uses DONE on the picker.
        if inp.fire_pressed or inp.confirm_pressed:
            if self._initial_idx < 2:
                self._initial_idx += 1
                audio.play("ui_confirm")
            else:
                self._submit_initials()

    def _restart(self) -> None:
        self.score = 0
        self.wave = WaveState()
        self.player = Player(x=WIDTH / 2, y=HEIGHT - 280)
        self.bolts.clear()
        self.game_over = False
        self.won_wave_flash = 0.0
        self.idle_timer = 0.0
        self._entering_score = False
        self._score_saved = False
        self._initials_picker = None
        self._block_fire = False
        self._spawn_barriers()
        self._spawn_wave(1)
        audio.play("ui_confirm")
        audio.play_music("game")

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_assets()
        assert self._font and self._font_lg

        if self._bg:
            surface.blit(self._bg, (0, 0))
        else:
            self._draw_gradient_bg(surface)

        # Barriers
        for bar in self.barriers:
            spr = self._sprites["barrier"].copy()
            if bar.hp < bar.max_hp:
                # Chip effect via alpha / darken
                fade = int(255 * (bar.hp / bar.max_hp))
                spr.set_alpha(max(80, fade))
            surface.blit(spr, spr.get_rect(center=(int(bar.x), int(bar.y))))

        # Enemies
        for e in self.enemies:
            spr = self._sprites[e.draw_key()]
            surface.blit(spr, spr.get_rect(center=(int(e.x), int(e.y))))

        # Player
        if self.player.invuln <= 0 or int(self.player.invuln * 10) % 2 == 0:
            spr = self._sprites["player"]
            surface.blit(spr, spr.get_rect(center=(int(self.player.x), int(self.player.y))))

        # Bolts
        for b in self.bolts:
            spr = self._sprites["bolt"] if b.friendly else self._sprites["enemy_bolt"]
            surface.blit(spr, spr.get_rect(center=(int(b.x), int(b.y))))

        # HUD
        hud = f"SCORE {self.score:05d}   LIVES {self.player.lives}   WAVE {self.wave.index}"
        surface.blit(self._font.render(hud, True, HUD_COLOR), (40, 40))
        self._mute_chip.draw(surface)
        if self.wave.boss_active:
            surface.blit(self._font.render("SCOOTER DOG!", True, ACCENT), (180, 110))

        if self.won_wave_flash > 0:
            msg = "BOSS INCOMING!" if self.wave.boss_pending else "WAVE CLEAR!"
            text = self._font_lg.render(msg, True, OK)
            surface.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))

        if self.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surface.blit(overlay, (0, 0))
            go_y = HEIGHT // 2 - 520 if self._entering_score else HEIGHT // 2 - 280
            go = self._font_lg.render("GAME OVER", True, DANGER)
            score_line = self._font.render(f"SCORE {self.score:05d}   WAVE {self.wave.index}", True, HUD_COLOR)
            surface.blit(go, go.get_rect(center=(WIDTH // 2, go_y)))
            surface.blit(score_line, score_line.get_rect(center=(WIDTH // 2, go_y + 80)))

            if self._entering_score:
                prompt = self._font.render("NEW HIGH SCORE — enter initials", True, ACCENT)
                surface.blit(prompt, prompt.get_rect(center=(WIDTH // 2, go_y + 150)))
                if self._initials_picker is not None:
                    self._initials_picker.draw(surface, self._initials, self._initial_idx)
                else:
                    letters = "  ".join(self._initials)
                    init_surf = self._font_lg.render(letters, True, OK)
                    surface.blit(init_surf, init_surf.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 40)))
            else:
                if self._score_saved:
                    saved = self._font.render("Score saved!", True, OK)
                    surface.blit(saved, saved.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 120)))
                tip_text, _, _ = control_prompt_lines("Restart")
                tip = self._font.render(tip_text, True, HUD_COLOR)
                surface.blit(tip, tip.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
                # #region agent log
                if getattr(self, "_dbg_last_restart_tip", None) != tip_text:
                    self._dbg_last_restart_tip = tip_text
                    try:
                        import pygame as _pg

                        from core.input import _agent_dbg, classify_pad

                        pads = []
                        for i in range(_pg.joystick.get_count()):
                            j = _pg.joystick.Joystick(i)
                            pads.append({"name": j.get_name(), "profile": classify_pad(j.get_name())})
                        _agent_dbg(
                            "E",
                            "booth_blaster.py:draw",
                            "restart tip shown",
                            {"tip_text": tip_text, "pad_count": len(pads), "pads": pads},
                        )
                    except Exception:
                        pass
                # #endregion
                self._draw_leaderboard(surface, HEIGHT // 2 + 20)

    def _draw_leaderboard(self, surface: pygame.Surface, top_y: int) -> None:
        assert self._font and self._font_lg
        title = self._font.render("LEADERBOARD", True, ACCENT)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, top_y)))
        entries = leaderboard.load_scores()
        if not entries:
            empty = self._font.render("No scores yet — be the first!", True, HUD_COLOR)
            surface.blit(empty, empty.get_rect(center=(WIDTH // 2, top_y + 60)))
            return
        y = top_y + 50
        for i, entry in enumerate(entries[:10], start=1):
            rank_color = OK if i == 1 else HUD_COLOR
            line = f"{i:2d}.  {entry.name}   {entry.score:05d}   W{entry.wave}"
            text = self._font.render(line, True, rank_color)
            surface.blit(text, text.get_rect(center=(WIDTH // 2, y)))
            y += 44

    @staticmethod
    def _draw_gradient_bg(surface: pygame.Surface) -> None:
        for y in range(0, HEIGHT, 4):
            t = y / HEIGHT
            r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
            g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
            b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
            pygame.draw.rect(surface, (r, g, b), (0, y, WIDTH, 4))


class LoadingScene:
    """Splash (logo + title) shown briefly before the main menu."""

    DURATION = 2.2

    def __init__(self) -> None:
        self.exit_requested = False
        self._elapsed = 0.0
        self._splash: Optional[pygame.Surface] = None
        self._ready = False

    def _ensure(self) -> None:
        if self._ready:
            return
        path = SPRITES_DIR / "splash_booth.png"
        if path.is_file():
            try:
                img = pygame.image.load(str(path)).convert()
                self._splash = pygame.transform.smoothscale(img, (WIDTH, HEIGHT))
            except pygame.error:
                self._splash = None
        self._ready = True

    def handle_event(self, event: pygame.event.Event) -> None:
        return

    def update(self, dt: float, inp: InputState) -> Optional[object]:
        self._ensure()
        self._elapsed += dt
        # Tap/confirm skips splash early
        if self._elapsed >= self.DURATION or inp.confirm_pressed or inp.fire_pressed:
            return TitleScene()
        if inp.exit_ready:
            self.exit_requested = True
            return None
        return self

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure()
        if self._splash is not None:
            surface.blit(self._splash, (0, 0))
        else:
            BoothBlaster._draw_gradient_bg(surface)
            font = load_font(72, bold=True)
            title = font.render("BOOTH BLASTER", True, ACCENT)
            surface.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2)))


class TitleScene:
    """Simple title → Booth Blaster launcher."""

    def __init__(self) -> None:
        self.idle_timer = 0.0
        self.exit_requested = False
        self._font: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._ready = False
        self.next_scene: Optional[BoothBlaster] = None
        self._audio_panel = AudioPanel((WIDTH - 36, 36), scale=1.15)
        self._block_confirm = False
        audio.play_music("title")

    def _ensure(self) -> None:
        if self._ready:
            return
        self._font = load_font(36)
        self._font_lg = load_font(72, bold=True)
        self._ready = True

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.idle_timer = 0.0
            if event.key == pygame.K_m:
                audio.toggle_mute()
                audio.play("ui_blip")
                self._block_confirm = True
            if event.key in (pygame.K_LEFTBRACKET, pygame.K_MINUS):
                audio.nudge_music_volume(-0.1)
                audio.play("ui_blip")
                self._block_confirm = True
            if event.key in (pygame.K_RIGHTBRACKET, pygame.K_EQUALS):
                audio.nudge_music_volume(0.1)
                audio.play("ui_blip")
                self._block_confirm = True
            if event.key == pygame.K_COMMA:
                audio.nudge_sfx_volume(-0.1)
                audio.play("ui_blip")
                self._block_confirm = True
            if event.key == pygame.K_PERIOD:
                audio.nudge_sfx_volume(0.1)
                audio.play("ui_blip")
                self._block_confirm = True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Skip mouse events synthesized from touch (FINGERDOWN handles those).
            if getattr(event, "touch", False):
                return
            lx, ly = window_to_logical(*event.pos)
            # #region agent log
            try:
                import json
                import time
                from pathlib import Path

                from core.platform import writable_data_dir

                payload = {
                    "sessionId": "b4844d",
                    "runId": "mute-post",
                    "hypothesisId": "D",
                    "location": "TitleScene.handle_event",
                    "message": "MOUSEBUTTONDOWN",
                    "data": {"raw": list(event.pos), "logical": [lx, ly], "touch": getattr(event, "touch", None)},
                    "timestamp": int(time.time() * 1000),
                }
                line = json.dumps(payload)
                print(f"AGENT_DEBUG {line}", flush=True)
                for path in (writable_data_dir() / "debug-b4844d.log", Path("debug-b4844d.log")):
                    try:
                        with path.open("a", encoding="utf-8") as f:
                            f.write(line + "\n")
                    except OSError:
                        pass
            except Exception:
                pass
            # #endregion
            if self._audio_panel.handle_click((int(lx), int(ly))):
                self.idle_timer = 0.0
                self._block_confirm = True
        if event.type == pygame.FINGERDOWN:
            lx, ly = event.x * WIDTH, event.y * HEIGHT
            # #region agent log
            try:
                import json
                import time
                from pathlib import Path

                from core.platform import writable_data_dir

                payload = {
                    "sessionId": "b4844d",
                    "runId": "mute-post",
                    "hypothesisId": "D",
                    "location": "TitleScene.handle_event",
                    "message": "FINGERDOWN",
                    "data": {"norm": [event.x, event.y], "logical": [lx, ly]},
                    "timestamp": int(time.time() * 1000),
                }
                line = json.dumps(payload)
                print(f"AGENT_DEBUG {line}", flush=True)
                for path in (writable_data_dir() / "debug-b4844d.log", Path("debug-b4844d.log")):
                    try:
                        with path.open("a", encoding="utf-8") as f:
                            f.write(line + "\n")
                    except OSError:
                        pass
            except Exception:
                pass
            # #endregion
            if self._audio_panel.handle_click((int(lx), int(ly))):
                self.idle_timer = 0.0
                self._block_confirm = True

    def update(self, dt: float, inp: InputState) -> Optional[object]:
        self._ensure()
        if self._block_confirm:
            self._block_confirm = False
            return self
        if inp.any_activity:
            self.idle_timer = 0.0
        else:
            self.idle_timer += dt
            if self.idle_timer >= IDLE_QUIT_SECONDS:
                self.exit_requested = True
                return None
        if inp.exit_ready:
            self.exit_requested = True
            return None
        if inp.confirm_pressed:
            audio.play("ui_confirm")
            return BoothBlaster(from_title=True)
        return self

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure()
        assert self._font and self._font_lg
        BoothBlaster._draw_gradient_bg(surface)
        title = self._font_lg.render("BOOTH BLASTER", True, ACCENT)
        sub = self._font.render("Laser Monkey vs the Con Crowd", True, HUD_COLOR)
        tip_text, tip2_text, tip3_text = control_prompt_lines("Start")
        tip = self._font.render(tip_text, True, OK)
        tip2 = self._font.render(tip2_text, True, HUD_COLOR)
        tip3 = self._font.render(tip3_text, True, HUD_COLOR)
        # #region agent log
        if getattr(self, "_dbg_last_start_tip", None) != tip_text:
            self._dbg_last_start_tip = tip_text
            try:
                import pygame as _pg

                from core.input import _agent_dbg, classify_pad

                pads = []
                for i in range(_pg.joystick.get_count()):
                    j = _pg.joystick.Joystick(i)
                    pads.append({"name": j.get_name(), "profile": classify_pad(j.get_name())})
                _agent_dbg(
                    "E",
                    "booth_blaster.py:TitleScene.draw",
                    "start tip shown",
                    {
                        "tip_text": tip_text,
                        "tip2": tip2_text,
                        "tip3": tip3_text,
                        "pad_count": len(pads),
                        "pads": pads,
                    },
                )
            except Exception:
                pass
        # #endregion
        tip4 = self._font.render("M mute · [ ] music · , . sfx", True, HUD_COLOR)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 420)))
        surface.blit(sub, sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 340)))
        surface.blit(tip, tip.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 260)))
        surface.blit(tip2, tip2.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 210)))
        surface.blit(tip3, tip3.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 160)))
        surface.blit(tip4, tip4.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 110)))

        self._audio_panel.draw(surface)

        # Reuse leaderboard renderer
        dummy = BoothBlaster.__new__(BoothBlaster)
        dummy._font = self._font
        dummy._font_lg = self._font_lg
        BoothBlaster._draw_leaderboard(dummy, surface, HEIGHT // 2 - 40)
