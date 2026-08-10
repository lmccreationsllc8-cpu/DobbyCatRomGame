"""Booth Blaster — Space Invaders-style comic-con booth shooter."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

import pygame

from config import HEIGHT, IDLE_QUIT_SECONDS, SPRITES_DIR, WIDTH
from core import audio, leaderboard, storage
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
    ZIPTIE = auto()
    TEEN = auto()
    ADULT = auto()
    LINECUTTER = auto()
    SELFIE = auto()
    GLOWSTICK = auto()
    MAID = auto()
    MECHA = auto()
    PILLOW = auto()
    BOSS = auto()
    BOSS_KITTEN = auto()
    BOSS_NANA = auto()
    BOSS_PARENT_A = auto()
    BOSS_PARENT_B = auto()


MAID_SPRITES = (
    "enemy_maid_pink.png",
    "enemy_maid_cyan.png",
    "enemy_maid_lime.png",
)

PLAYER_SKINS = (
    "player_dobby_original.png",
    "player_dobby_ugly.png",
    "player_dobby_cute.png",
    "player_dobby_bee.png",
    "player_dobby_hoodie_green.png",
    "player_dobby_dino.png",
    "player_dobby_cape.png",
    "player_dobby_pickle.png",
    "player_dobby_octopus.png",
    "player_dobby_hi_vis.png",
)
_SKIN_STORE = "player_skin.txt"

CAMPAIGN_WAVES = 4
# Perfect clear: w1 1140 + w2 1310 + w3 1450 + w4 800 = 4700
# (formations + pillows + bosses + clear/victory bonuses; wave 4 is boss-only).
CAMPAIGN_MAX_SCORE = 4700

# Base shoot chance per second; LINECUTTER fires ~1.25× adult cadence.
_SHOOT_RATE_ADULT = 0.08
_SHOOT_RATES = {
    EnemyKind.MAID: _SHOOT_RATE_ADULT,
    EnemyKind.ADULT: _SHOOT_RATE_ADULT,
    EnemyKind.LINECUTTER: _SHOOT_RATE_ADULT * 1.25,
    EnemyKind.SELFIE: _SHOOT_RATE_ADULT,
}

_PARENT_KINDS = frozenset({EnemyKind.BOSS_PARENT_A, EnemyKind.BOSS_PARENT_B})
_BOSS_KINDS = frozenset(
    {
        EnemyKind.BOSS,
        EnemyKind.BOSS_KITTEN,
        EnemyKind.BOSS_NANA,
        EnemyKind.BOSS_PARENT_A,
        EnemyKind.BOSS_PARENT_B,
    }
)

# Wave 1 baseline; each later solo boss is ~12.5% faster / hotter.
# Wave 4 parents match wave 3 cadence (difficulty comes from two independent actors).
_BOSS_STEP_BASE = 0.40
_BOSS_FIRE_BASE = 0.35
_BOSS_DIFFICULTY_SCALE = 1.125


def _boss_difficulty_tier(wave: int) -> int:
    """0=wave1, 1=wave2, 2=wave3+ (parents share wave-3 tier)."""
    return min(max(int(wave), 1), 3) - 1


def boss_step_interval(wave: int) -> float:
    return _BOSS_STEP_BASE / (_BOSS_DIFFICULTY_SCALE ** _boss_difficulty_tier(wave))


def boss_shoot_rate(wave: int) -> float:
    return _BOSS_FIRE_BASE * (_BOSS_DIFFICULTY_SCALE ** _boss_difficulty_tier(wave))

ENEMY_STATS = {
    # Wide, high-contrast silhouettes for blue booth backdrop
    EnemyKind.BOX: {"hp": 1, "score": 10, "w": 96, "h": 96, "color": (210, 170, 90), "sprite": "enemy_box.png"},
    EnemyKind.ZIPTIE: {"hp": 2, "score": 20, "w": 100, "h": 110, "color": (40, 220, 180), "sprite": "enemy_ziptie.png"},
    EnemyKind.TEEN: {"hp": 2, "score": 25, "w": 100, "h": 120, "color": (80, 200, 255), "sprite": "enemy_teen.png"},
    EnemyKind.ADULT: {"hp": 3, "score": 35, "w": 110, "h": 130, "color": (255, 120, 40), "sprite": "enemy_adult.png"},
    EnemyKind.LINECUTTER: {"hp": 3, "score": 40, "w": 110, "h": 130, "color": (255, 70, 90), "sprite": "enemy_linecutter.png"},
    EnemyKind.SELFIE: {"hp": 3, "score": 40, "w": 110, "h": 130, "color": (255, 160, 220), "sprite": "enemy_selfie.png"},
    EnemyKind.GLOWSTICK: {"hp": 3, "score": 45, "w": 110, "h": 130, "color": (180, 255, 60), "sprite": "enemy_glowstick.png"},
    EnemyKind.MAID: {"hp": 4, "score": 45, "w": 110, "h": 140, "color": (255, 80, 200), "sprite": "enemy_maid_pink.png"},
    EnemyKind.MECHA: {"hp": 5, "score": 60, "w": 120, "h": 150, "color": (120, 140, 180), "sprite": "enemy_mecha.png"},
    EnemyKind.PILLOW: {"hp": 1, "score": 150, "w": 110, "h": 90, "color": (240, 200, 220), "sprite": "enemy_pillow.png"},
    EnemyKind.BOSS: {"hp": 22, "score": 300, "w": 280, "h": 220, "color": (180, 120, 255), "sprite": "enemy_boss.png"},
    EnemyKind.BOSS_KITTEN: {"hp": 26, "score": 400, "w": 240, "h": 240, "color": (40, 40, 48), "sprite": "enemy_boss_kitten.png"},
    EnemyKind.BOSS_NANA: {"hp": 24, "score": 450, "w": 220, "h": 260, "color": (160, 80, 220), "sprite": "enemy_boss_nana.png"},
    EnemyKind.BOSS_PARENT_A: {"hp": 18, "score": 350, "w": 200, "h": 240, "color": (180, 140, 90), "sprite": "enemy_boss_parent_a.png"},
    EnemyKind.BOSS_PARENT_B: {"hp": 18, "score": 350, "w": 200, "h": 240, "color": (30, 30, 36), "sprite": "enemy_boss_parent_b.png"},
}

BOSS_HUD_LABELS = {
    1: "SCOOTER DOG!",
    2: "SHADOW KITTEN!",
    3: "NANA OF ANNIHILATION!",
    4: "CAT PARENTS!",
}


def load_player_skin_index() -> int:
    raw = storage.read_text(_SKIN_STORE)
    if raw is None:
        return 0
    try:
        idx = int(str(raw).strip())
    except ValueError:
        return 0
    if not PLAYER_SKINS:
        return 0
    return idx % len(PLAYER_SKINS)


def save_player_skin_index(index: int) -> None:
    if not PLAYER_SKINS:
        return
    storage.write_text(_SKIN_STORE, str(int(index) % len(PLAYER_SKINS)))


def player_skin_filename(index: Optional[int] = None) -> str:
    idx = load_player_skin_index() if index is None else int(index)
    if not PLAYER_SKINS:
        return "player_dobby.png"
    return PLAYER_SKINS[idx % len(PLAYER_SKINS)]

PILLOW_FLY_Y = 180.0
PILLOW_SPEED = 160.0
VICTORY_DURATION = 4.0
NET_SLOW_DURATION = 1.0
NET_SPEED_MUL = 0.45


def _knockout_light_bg(surf: pygame.Surface) -> pygame.Surface:
    """Strip studio plates only when connected to the image edge.

    Never blanket-delete light pixels — that ate white fur, eyes, saber cores,
    and other interior fills. Prefers pre-cleaned RGBA assets.
    """
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
        from collections import deque

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
        # Candidate plate: near-white / empty alpha. Interior whites are kept
        # unless flood-fill reaches them from the border.
        plate = ((luma >= 242) & (sat <= 18) & (alpha > 0)) | (alpha < 8)
        # If the sprite already has substantial transparency, skip — assets are
        # pre-cleaned and global light knockout only damages fills.
        if float(np.mean(alpha < 8)) > 0.08:
            alpha[alpha < 8] = 0
            del rgb, alpha
            return out

        # pygame surfarray is indexed [x, y] → shape (width, height).
        width, height = alpha.shape
        visited = np.zeros((width, height), dtype=np.bool_)
        q: deque[tuple[int, int]] = deque()
        for x in range(width):
            for y in (0, height - 1):
                if plate[x, y] and not visited[x, y]:
                    visited[x, y] = True
                    q.append((x, y))
        for y in range(height):
            for x in (0, width - 1):
                if plate[x, y] and not visited[x, y]:
                    visited[x, y] = True
                    q.append((x, y))
        while q:
            x, y = q.popleft()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < width and 0 <= ny < height and not visited[nx, ny] and plate[nx, ny]:
                    visited[nx, ny] = True
                    q.append((nx, ny))
        alpha[visited] = 0
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
    kind: str = "paw"  # "paw" | "treat" | "net"
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
    armored: bool = False  # MECHA: first hit chips armor, no HP loss
    # Independent march state (used by wave-4 parents).
    march_dir: float = 1.0
    step_timer: float = 0.0
    step_interval: float = 0.4
    drop_pending: bool = False

    @property
    def stats(self) -> dict:
        return ENEMY_STATS[self.kind]

    @property
    def rect(self) -> pygame.Rect:
        w, h = self.stats["w"], self.stats["h"]
        return pygame.Rect(int(self.x - w / 2), int(self.y - h / 2), w, h)

    def draw_key(self) -> str:
        return self.sprite_key or f"enemy_{self.kind.name.lower()}"

    @property
    def is_flyer(self) -> bool:
        return self.kind == EnemyKind.PILLOW

    @property
    def is_parent(self) -> bool:
        return self.kind in _PARENT_KINDS


@dataclass
class Barrier:
    x: float
    y: float
    hp: int = 8
    max_hp: int = 8
    w: int = 120
    h: int = 72
    # Slot 0 = leftmost; keeps graffiti frames after other barriers despawn.
    slot: int = 0

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
    slow_timer: float = 0.0

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
        self.campaign_won = False
        self.victory_timer = 0.0
        self.victory_particles: list[dict] = []
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
        self._asset_phase = 0
        self._asset_enemy_kinds = list(ENEMY_STATS.keys())
        self._asset_enemy_i = 0
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

    def assets_loading(self) -> bool:
        return not self._assets_ready

    def load_assets_step(self) -> bool:
        """Load a small asset batch. Returns True while more work remains.

        Call from the async main loop between ``await asyncio.sleep(0)`` so the
        browser stays responsive (WASM has no threads).
        """
        if self._assets_ready:
            return False
        if self._asset_phase == 0:
            self._font = load_font(36)
            self._font_lg = load_font(64, bold=True)
            self._sprites["player"] = _load_sprite(player_skin_filename(), (220, 220), (180, 120, 70))
            self._sprites["bolt"] = _load_sprite("paw_bolt.png", (40, 40), (255, 180, 220))
            self._sprites["enemy_bolt"] = _load_sprite("paw_enemy.png", (36, 36), (255, 90, 70))
            self._sprites["treat"] = _load_sprite("proj_treat.png", (40, 40), (230, 160, 70))
            self._sprites["net"] = _load_sprite("proj_net.png", (44, 44), (90, 200, 255))
            self._asset_phase = 1
            return True
        if self._asset_phase == 1:
            # A few enemy sprites per step keeps each frame under a hitch budget.
            batch = 3
            while batch > 0 and self._asset_enemy_i < len(self._asset_enemy_kinds):
                kind = self._asset_enemy_kinds[self._asset_enemy_i]
                stats = ENEMY_STATS[kind]
                key = f"enemy_{kind.name.lower()}"
                self._sprites[key] = _load_sprite(stats["sprite"], (stats["w"], stats["h"]), stats["color"])
                self._asset_enemy_i += 1
                batch -= 1
            if self._asset_enemy_i >= len(self._asset_enemy_kinds):
                self._asset_phase = 2
            return True
        if self._asset_phase == 2:
            maid_size = (ENEMY_STATS[EnemyKind.MAID]["w"], ENEMY_STATS[EnemyKind.MAID]["h"])
            maid_color = ENEMY_STATS[EnemyKind.MAID]["color"]
            for name in MAID_SPRITES:
                key = name.replace(".png", "")
                self._sprites[key] = _load_sprite(name, maid_size, maid_color)
            self._sprites["barrier"] = _load_sprite("barrier_crate.png", (120, 72), (40, 40, 48))
            self._sprites["barrier_d1"] = _load_sprite("barrier_crate_d1.png", (120, 72), (40, 40, 48))
            self._sprites["barrier_d2"] = _load_sprite("barrier_crate_d2.png", (120, 72), (40, 40, 48))
            self._asset_phase = 3
            return True
        # phase 3: background
        bg_path = SPRITES_DIR / "bg_booth.png"
        if bg_path.is_file():
            try:
                raw = pygame.image.load(str(bg_path)).convert()
                try:
                    from core.platform import is_web

                    scaler = pygame.transform.scale if is_web() else pygame.transform.smoothscale
                except Exception:
                    scaler = pygame.transform.smoothscale
                self._bg = scaler(raw, (WIDTH, HEIGHT))
            except pygame.error:
                self._bg = None
        self._assets_ready = True
        return False

    def _ensure_assets(self) -> None:
        """Load remaining assets. On web, main.py chunks via ``load_assets_step``."""
        if self._assets_ready:
            return
        try:
            from core.platform import is_web

            if is_web():
                return
        except Exception:
            pass
        while self.load_assets_step():
            pass

    def _spawn_barriers(self) -> None:
        ys = HEIGHT - 420
        xs = [WIDTH * 0.18, WIDTH * 0.38, WIDTH * 0.62, WIDTH * 0.82]
        self.barriers = [Barrier(x=x, y=ys, slot=i) for i, x in enumerate(xs)]

    def _barrier_draw_sprite(self, bar: Barrier) -> pygame.Surface:
        """Leftmost barrier: pristine→d1→d2 graffiti frames; others keep alpha fade."""
        if bar.slot == 0:
            ratio = bar.hp / bar.max_hp if bar.max_hp else 0.0
            if ratio > 2.0 / 3.0:
                return self._sprites["barrier"]
            if ratio > 1.0 / 3.0:
                return self._sprites["barrier_d1"]
            return self._sprites["barrier_d2"]
        spr = self._sprites["barrier"].copy()
        if bar.hp < bar.max_hp:
            fade = int(255 * (bar.hp / bar.max_hp))
            spr.set_alpha(max(80, fade))
        return spr

    def _kind_for_cell(self, row: int, col: int, wave_index: int) -> EnemyKind:
        """Formation layout: top MAID/MECHA, mid TEEN/ADULT/LINECUTTER/GLOWSTICK(+SELFIE), bottom BOX/ZIPTIE."""
        if row == 0:
            # Top: MAID; MECHA + SELFIE from wave 2+
            if wave_index >= 2 and col % 4 == 1:
                return EnemyKind.MECHA
            if wave_index >= 2 and col % 5 == 3:
                return EnemyKind.SELFIE
            return EnemyKind.MAID
        if row == 1:
            # Mid: wave 1 TEEN/ADULT; wave 2+ adds LINECUTTER/GLOWSTICK/SELFIE
            if wave_index >= 2 and col % 5 == 0:
                return EnemyKind.SELFIE
            mid_pool = (
                (EnemyKind.TEEN, EnemyKind.ADULT, EnemyKind.LINECUTTER, EnemyKind.GLOWSTICK)
                if wave_index >= 2
                else (EnemyKind.TEEN, EnemyKind.ADULT)
            )
            return mid_pool[col % len(mid_pool)]
        # Bottom: BOX + ZIPTIE
        return EnemyKind.BOX if col % 2 == 0 else EnemyKind.ZIPTIE

    def _spawn_wave(self, wave_index: int) -> None:
        self.enemies.clear()
        self.bolts = [b for b in self.bolts if b.friendly]
        self.dir = 1.0
        self.drop_pending = False
        self.step_interval = max(0.22, 0.55 - (wave_index - 1) * 0.04)
        self.wave.boss_pending = False
        self.wave.boss_active = False
        self.wave.clear_timer = 0.0

        # Final wave is parents-only — no formation or pillow.
        if wave_index >= CAMPAIGN_WAVES:
            self._spawn_boss()
            return

        rows = min(4, 3 + (wave_index - 1) // 2)
        cols = 6
        top = 240
        gap_x = 150
        gap_y = 130
        origin_x = WIDTH / 2 - (cols - 1) * gap_x / 2

        for r in range(rows):
            for c in range(cols):
                kind = self._kind_for_cell(r, c, wave_index)
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
                        armored=(kind == EnemyKind.MECHA),
                    )
                )

        # One pillow flyer per wave (independent of formation march).
        pillow = ENEMY_STATS[EnemyKind.PILLOW]
        self.enemies.append(
            Enemy(
                kind=EnemyKind.PILLOW,
                x=-pillow["w"] / 2,
                y=PILLOW_FLY_Y,
                hp=pillow["hp"],
                col=-1,
                row=-1,
            )
        )

    def _spawn_boss(self) -> None:
        self.wave.boss_active = True
        self.wave.boss_pending = False
        self.enemies.clear()
        wave = self.wave.index
        interval = boss_step_interval(wave)
        if wave <= 1:
            stats = ENEMY_STATS[EnemyKind.BOSS]
            hp = stats["hp"] + (wave - 1) * 4
            self.enemies = [
                Enemy(kind=EnemyKind.BOSS, x=WIDTH / 2, y=320, hp=hp, col=0, row=0)
            ]
        elif wave == 2:
            stats = ENEMY_STATS[EnemyKind.BOSS_KITTEN]
            hp = stats["hp"] + (wave - 1) * 4
            self.enemies = [
                Enemy(kind=EnemyKind.BOSS_KITTEN, x=WIDTH / 2, y=300, hp=hp, col=0, row=0)
            ]
        elif wave == 3:
            stats = ENEMY_STATS[EnemyKind.BOSS_NANA]
            hp = stats["hp"] + (wave - 1) * 4
            self.enemies = [
                Enemy(kind=EnemyKind.BOSS_NANA, x=WIDTH / 2, y=300, hp=hp, col=0, row=0)
            ]
        else:
            # Match Nana cadence; two independent actors make this the hardest fight.
            stats_a = ENEMY_STATS[EnemyKind.BOSS_PARENT_A]
            stats_b = ENEMY_STATS[EnemyKind.BOSS_PARENT_B]
            hp_a = stats_a["hp"] + (wave - 1) * 3
            hp_b = stats_b["hp"] + (wave - 1) * 3
            self.enemies = [
                Enemy(
                    kind=EnemyKind.BOSS_PARENT_A,
                    x=WIDTH / 2 - 180,
                    y=300,
                    hp=hp_a,
                    col=0,
                    row=0,
                    march_dir=1.0,
                    step_timer=0.0,
                    step_interval=interval,
                ),
                Enemy(
                    kind=EnemyKind.BOSS_PARENT_B,
                    x=WIDTH / 2 + 180,
                    y=300,
                    hp=hp_b,
                    col=1,
                    row=0,
                    march_dir=-1.0,
                    step_timer=interval * 0.5,
                    step_interval=interval,
                ),
            ]
        self.step_interval = interval
        self.step_timer = 0.0
        self.dir = 1.0
        self.drop_pending = False
        audio.play_music("boss")
        audio.play("boss_incoming")

    def _start_victory(self) -> None:
        self.wave.boss_active = False
        self.victory_timer = VICTORY_DURATION
        self.bolts.clear()
        self.enemies.clear()
        self.campaign_won = True
        self.score += 100
        audio.play("boss_defeat")
        audio.stop_music(fade_ms=250)
        audio.play("victory_fanfare")
        self.victory_particles = []
        rng = random.Random(7)
        for _ in range(48):
            self.victory_particles.append(
                {
                    "x": float(WIDTH / 2 + rng.uniform(-40, 40)),
                    "y": float(HEIGHT / 2 + 120),
                    "vx": rng.uniform(-220, 220),
                    "vy": rng.uniform(-520, -120),
                    "life": rng.uniform(0.8, 2.2),
                    "color": rng.choice(
                        [(255, 220, 80), (255, 120, 200), (120, 220, 255), (180, 255, 160), (255, 255, 255)]
                    ),
                }
            )

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

    def update(self, dt: float, inp: InputState) -> Optional[object]:
        self._ensure_assets()
        if not self._assets_ready:
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

        if self.victory_timer > 0:
            self.victory_timer -= dt
            for p in self.victory_particles:
                p["x"] += p["vx"] * dt
                p["y"] += p["vy"] * dt
                p["vy"] += 420.0 * dt
                p["life"] -= dt
            self.victory_particles = [p for p in self.victory_particles if p["life"] > 0]
            if self.victory_timer <= 0:
                self.game_over = True
                self._begin_score_entry()
            return self

        if self.game_over:
            if self._block_fire:
                self._block_fire = False
                return self
            if self._entering_score:
                self._update_initials_entry(dt, inp)
            elif inp.confirm_pressed:
                if self.campaign_won:
                    audio.play("ui_confirm")
                    return TitleScene()
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
        self.player.slow_timer = max(0.0, self.player.slow_timer - dt)
        speed = self.PLAYER_SPEED * (NET_SPEED_MUL if self.player.slow_timer > 0 else 1.0)
        margin = self.player.w / 2 + 20
        if inp.aim_x is not None:
            self.player.x = max(margin, min(WIDTH - margin, float(inp.aim_x)))
        else:
            self.player.x += inp.move_x * speed * dt
            self.player.x = max(margin, min(WIDTH - margin, self.player.x))

        if (inp.fire_pressed or (inp.fire_held and self.player.cooldown <= 0)) and self.player.cooldown <= 0:
            self.bolts.append(
                Bolt(self.player.x, self.player.y - self.player.h / 2, self.BOLT_SPEED, True, kind="paw")
            )
            self.player.cooldown = self.FIRE_COOLDOWN
            audio.play("shoot")

        # Enemies march (formation shared; parents each move independently)
        marchers = [e for e in self.enemies if not e.is_flyer]
        parents = [e for e in marchers if e.is_parent]
        formation = [e for e in marchers if not e.is_parent]
        if formation:
            self.step_timer += dt
            if self.step_timer >= self.step_interval:
                self.step_timer = 0.0
                self._march_enemies(formation)
                audio.play("march", volume=0.35 if self.wave.boss_active else 0.22)
        for e in parents:
            e.step_timer += dt
            if e.step_timer >= e.step_interval:
                e.step_timer = 0.0
                self._march_solo(e)
                audio.play("march", volume=0.35)

        for e in marchers:
            rate = self._shoot_rate_for(e)
            if rate is not None and random.random() < rate * dt:
                if e.is_parent:
                    bolt_kind = random.choice(("treat", "net"))
                    bw, bh = (40, 40) if bolt_kind == "treat" else (44, 44)
                else:
                    bolt_kind = "paw"
                    bw, bh = 34, 34
                self.bolts.append(
                    Bolt(
                        e.x,
                        e.y + e.stats["h"] / 2,
                        self.ENEMY_BOLT_SPEED,
                        False,
                        kind=bolt_kind,
                        w=bw,
                        h=bh,
                    )
                )
                audio.play("enemy_shoot", volume=0.45)

        # Pillow flyers drift across; despawn off-screen (no score)
        for e in self.enemies:
            if e.is_flyer:
                e.x += PILLOW_SPEED * dt
        self.enemies = [
            e
            for e in self.enemies
            if not (e.is_flyer and (e.rect.right < -20 or e.rect.left > WIDTH + 20))
        ]

        # Bolts
        for b in self.bolts:
            b.y += b.vy * dt
        self.bolts = [b for b in self.bolts if -40 < b.y < HEIGHT + 40]

        self._resolve_collisions()

        # Wave clear → boss → next wave (or victory after final boss)
        if not self.enemies and not self.game_over and self.won_wave_flash <= 0 and self.victory_timer <= 0:
            if self.wave.boss_active:
                if self.wave.index >= CAMPAIGN_WAVES:
                    self._start_victory()
                else:
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
                and self.victory_timer <= 0
                and not self.campaign_won
            ):
                self._spawn_wave(self.wave.index)

        # Lose if formation enemies reach bottom (flyers stay in the upper lane)
        for e in self.enemies:
            if e.is_flyer:
                continue
            if e.rect.bottom >= self.player.rect.top - 10:
                self._player_hit()
                e.y -= 40  # nudge so we don't multi-hit every frame

        return self

    def _shoot_rate_for(self, e: Enemy) -> Optional[float]:
        if e.kind in _BOSS_KINDS:
            return boss_shoot_rate(self.wave.index)
        return _SHOOT_RATES.get(e.kind)

    def _march_enemies(self, marchers: Optional[list[Enemy]] = None) -> None:
        if marchers is None:
            marchers = [e for e in self.enemies if not e.is_flyer]
        if not marchers:
            return
        step_x = 28 if not self.wave.boss_active else 40
        drop = 36
        min_x = min(e.rect.left for e in marchers)
        max_x = max(e.rect.right for e in marchers)
        if self.drop_pending:
            for e in marchers:
                e.y += drop
            self.dir *= -1
            self.drop_pending = False
            self.step_interval = max(0.18, self.step_interval * 0.97)
            return
        for e in marchers:
            e.x += step_x * self.dir
        if (self.dir > 0 and max_x + step_x >= WIDTH - 40) or (self.dir < 0 and min_x - step_x <= 40):
            self.drop_pending = True

    def _march_solo(self, e: Enemy) -> None:
        """Independent edge-bounce march used by cat parents."""
        step_x = 40
        drop = 36
        if e.drop_pending:
            e.y += drop
            e.march_dir *= -1
            e.drop_pending = False
            e.step_interval = max(0.18, e.step_interval * 0.97)
            return
        e.x += step_x * e.march_dir
        half_w = e.stats["w"] / 2
        if (e.march_dir > 0 and e.x + half_w + step_x >= WIDTH - 40) or (
            e.march_dir < 0 and e.x - half_w - step_x <= 40
        ):
            e.drop_pending = True

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
                        hit = True
                        # MECHA armor chip: first hit while armored strips armor only
                        if e.armored:
                            e.armored = False
                            audio.play("hit")
                            break
                        e.hp -= 1
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
                    self._player_hit(bolt_kind=b.kind)
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

    def _player_hit(self, bolt_kind: str = "paw") -> None:
        if self.player.invuln > 0:
            return
        self.player.lives -= 1
        self.player.invuln = 1.5
        if bolt_kind == "net":
            self.player.slow_timer = NET_SLOW_DURATION
        self.bolts = [b for b in self.bolts if b.friendly]
        audio.play("player_hurt")
        if self.player.lives <= 0:
            self.game_over = True
            self.campaign_won = False
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

    def _submit_initials(self) -> None:
        name = "".join(self._initials)
        leaderboard.submit(name, self.score, self.wave.index)
        self._score_saved = True
        self._entering_score = False
        self._initials_picker = None
        audio.play("ui_confirm")

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
        self.campaign_won = False
        self.victory_timer = 0.0
        self.victory_particles.clear()
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
        if not self._assets_ready or self._font is None or self._font_lg is None:
            self._draw_gradient_bg(surface)
            return
        assert self._font and self._font_lg

        if self._bg:
            surface.blit(self._bg, (0, 0))
        else:
            self._draw_gradient_bg(surface)

        # Barriers — leftmost (slot 0) swaps graffiti damage frames; others alpha-fade.
        for bar in self.barriers:
            spr = self._barrier_draw_sprite(bar)
            surface.blit(spr, spr.get_rect(center=(int(bar.x), int(bar.y))))

        # Enemies
        for e in self.enemies:
            spr = self._sprites[e.draw_key()]
            surface.blit(spr, spr.get_rect(center=(int(e.x), int(e.y))))

        # Player
        if self.victory_timer <= 0 and (self.player.invuln <= 0 or int(self.player.invuln * 10) % 2 == 0):
            spr = self._sprites["player"]
            surface.blit(spr, spr.get_rect(center=(int(self.player.x), int(self.player.y))))

        # Bolts
        for b in self.bolts:
            if b.friendly:
                spr = self._sprites["bolt"]
            elif b.kind == "treat":
                spr = self._sprites["treat"]
            elif b.kind == "net":
                spr = self._sprites["net"]
            else:
                spr = self._sprites["enemy_bolt"]
            surface.blit(spr, spr.get_rect(center=(int(b.x), int(b.y))))

        # HUD
        hud = f"SCORE {self.score:05d}   LIVES {self.player.lives}   WAVE {self.wave.index}/{CAMPAIGN_WAVES}"
        surface.blit(self._font.render(hud, True, HUD_COLOR), (40, 40))
        self._mute_chip.draw(surface)
        if self.wave.boss_active:
            label = BOSS_HUD_LABELS.get(self.wave.index, "BOSS!")
            surface.blit(self._font.render(label, True, ACCENT), (180, 110))

        if self.won_wave_flash > 0:
            msg = "BOSS INCOMING!" if self.wave.boss_pending else "WAVE CLEAR!"
            text = self._font_lg.render(msg, True, OK)
            surface.blit(text, text.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 80)))

        if self.victory_timer > 0:
            self._draw_victory(surface)

        if self.game_over:
            overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            surface.blit(overlay, (0, 0))
            go_y = HEIGHT // 2 - 520 if self._entering_score else HEIGHT // 2 - 280
            headline = "BOOTH CLEARED!" if self.campaign_won else "GAME OVER"
            head_color = OK if self.campaign_won else DANGER
            go = self._font_lg.render(headline, True, head_color)
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
                tip_label = "Title" if self.campaign_won else "Restart"
                tip_text, _, _ = control_prompt_lines(tip_label)
                tip = self._font.render(tip_text, True, HUD_COLOR)
                surface.blit(tip, tip.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))
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

    def _draw_victory(self, surface: pygame.Surface) -> None:
        assert self._font and self._font_lg
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        flash = int(80 + 40 * math.sin(self.victory_timer * 8))
        overlay.fill((20, 10, 40, flash))
        surface.blit(overlay, (0, 0))

        t = VICTORY_DURATION - self.victory_timer
        bob = math.sin(t * 6.0) * 18
        wave_angle = math.sin(t * 9.0) * 12
        spr = self._sprites["player"]
        rotated = pygame.transform.rotozoom(spr, wave_angle, 1.15)
        center = (WIDTH // 2, int(HEIGHT // 2 + 80 + bob))
        surface.blit(rotated, rotated.get_rect(center=center))

        # Victory tube / party popper burst from Dobby
        tube_x = center[0] + 70
        tube_y = center[1] - 40
        pygame.draw.polygon(
            surface,
            (255, 90, 140),
            [(tube_x, tube_y), (tube_x + 50, tube_y - 18), (tube_x + 44, tube_y + 10)],
        )
        pygame.draw.circle(surface, (255, 220, 80), (tube_x + 52, tube_y - 10), 8)

        for p in self.victory_particles:
            size = max(2, int(6 * p["life"]))
            pygame.draw.circle(surface, p["color"], (int(p["x"]), int(p["y"])), size)

        banner = self._font_lg.render("CONGRATULATIONS!", True, ACCENT)
        surface.blit(banner, banner.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 280)))
        sub = self._font.render("BOOTH CLEARED — you beat the Cat Parents!", True, HUD_COLOR)
        surface.blit(sub, sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 200)))

        # Sparkle ring
        for i in range(12):
            ang = t * 2.5 + i * (math.pi * 2 / 12)
            sx = WIDTH // 2 + int(math.cos(ang) * 220)
            sy = HEIGHT // 2 - 40 + int(math.sin(ang) * 90)
            pygame.draw.circle(surface, (255, 255, 200), (sx, sy), 4 + (i % 3))

    _gradient_bg: Optional[pygame.Surface] = None

    @staticmethod
    def _draw_gradient_bg(surface: pygame.Surface) -> None:
        cached = BoothBlaster._gradient_bg
        if cached is None or cached.get_size() != (WIDTH, HEIGHT):
            cached = pygame.Surface((WIDTH, HEIGHT))
            for y in range(0, HEIGHT, 4):
                t = y / HEIGHT
                r = int(BG_TOP[0] * (1 - t) + BG_BOTTOM[0] * t)
                g = int(BG_TOP[1] * (1 - t) + BG_BOTTOM[1] * t)
                b = int(BG_TOP[2] * (1 - t) + BG_BOTTOM[2] * t)
                pygame.draw.rect(cached, (r, g, b), (0, y, WIDTH, 4))
            BoothBlaster._gradient_bg = cached
        surface.blit(cached, (0, 0))


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
                # smoothscale is very costly on WASM; nearest is fine for splash.
                try:
                    from core.platform import is_web

                    scaler = pygame.transform.scale if is_web() else pygame.transform.smoothscale
                except Exception:
                    scaler = pygame.transform.smoothscale
                self._splash = scaler(img, (WIDTH, HEIGHT))
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
            # #region agent log
            try:
                from core.debug_agent import agent_log
                import time as _t

                _t0 = _t.perf_counter()
                agent_log(
                    "H3",
                    "LoadingScene.update",
                    "creating TitleScene",
                    {"elapsed": round(self._elapsed, 3), "confirm": bool(inp.confirm_pressed)},
                )
                _title = TitleScene()
                agent_log(
                    "H3",
                    "LoadingScene.update",
                    "TitleScene created",
                    {"ms": round((_t.perf_counter() - _t0) * 1000, 1)},
                )
                return _title
            except Exception as _exc:
                try:
                    from core.debug_agent import agent_log

                    agent_log("H4", "LoadingScene.update", "TitleScene failed", {"err": repr(_exc)})
                except Exception:
                    pass
                raise
            # #endregion
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

    PHOENIX_WINDOW = 1.5
    PHOENIX_PATTERN = ("up", "up", "fire")
    # Sequence timeline (seconds from trigger).
    _PHOENIX_FLY_DUR = 1.15
    _PHOENIX_BURN_START = 0.45
    _PHOENIX_BURN_DUR = 0.85
    _PHOENIX_HOLD = 0.35
    _PHOENIX_RESTORE = 0.55

    def __init__(self) -> None:
        # #region agent log
        try:
            from core.debug_agent import agent_log
            import time as _t

            _t0 = _t.perf_counter()
            agent_log("H3", "TitleScene.__init__", "begin", {})
        except Exception:
            _t0 = 0.0
        # #endregion
        self.idle_timer = 0.0
        self.exit_requested = False
        self._font: Optional[pygame.font.Font] = None
        self._font_lg: Optional[pygame.font.Font] = None
        self._font_sm: Optional[pygame.font.Font] = None
        self._ready = False
        # Spread title asset work across frames so WASM does not freeze after splash.
        self._load_phase = 0
        self._enter_grace = 0.45
        self.next_scene: Optional[BoothBlaster] = None
        self._audio_panel = AudioPanel((WIDTH - 36, 36), scale=1.15)
        self._block_confirm = True
        # Phoenix title secret (one-shot per visit).
        self._phoenix: Optional[pygame.Surface] = None
        self._phoenix_buf: list[str] = []
        self._phoenix_buf_age = 0.0
        self._phoenix_done = False
        self._phoenix_active = False
        self._phoenix_t = 0.0
        self._prev_up = False
        self._prev_skin_dir = 0
        self._touch_konami = False  # touch handled konami this frame; skip pad/key fire
        self._skin_index = load_player_skin_index()
        self._skin_preview: Optional[pygame.Surface] = None
        self._skin_label = ""
        # #region agent log
        try:
            from core.debug_agent import agent_log
            import time as _t

            agent_log(
                "H3",
                "TitleScene.__init__",
                "end",
                {"ms": round((_t.perf_counter() - _t0) * 1000, 1)},
            )
        except Exception:
            pass
        # #endregion

    def _ensure(self) -> None:
        if self._ready:
            return
        # #region agent log
        try:
            from core.debug_agent import agent_log
            import time as _t

            _phase = self._load_phase
            _t0 = _t.perf_counter()
            agent_log("H2", "TitleScene._ensure", "phase start", {"phase": _phase})
        except Exception:
            _phase = self._load_phase
            _t0 = 0.0
        # #endregion
        # Phase 0: fonts only (cheap). Phase 1: sprites + music (heavier on WASM).
        if self._load_phase == 0:
            self._font = load_font(36)
            self._font_lg = load_font(72, bold=True)
            self._font_sm = load_font(28)
            self._load_phase = 1
            # #region agent log
            try:
                from core.debug_agent import agent_log
                import time as _t

                agent_log(
                    "H2",
                    "TitleScene._ensure",
                    "phase0 fonts done",
                    {"ms": round((_t.perf_counter() - _t0) * 1000, 1)},
                )
            except Exception:
                pass
            # #endregion
            return
        # #region agent log
        try:
            from core.debug_agent import agent_log
            import time as _t

            _t_spr = _t.perf_counter()
        except Exception:
            _t_spr = 0.0
        # #endregion
        self._phoenix = _load_sprite("fx_phoenix.png", (280, 200), (255, 120, 40))
        self._reload_skin_preview()
        # #region agent log
        try:
            from core.debug_agent import agent_log
            import time as _t

            agent_log(
                "H2",
                "TitleScene._ensure",
                "sprites loaded",
                {"ms": round((_t.perf_counter() - _t_spr) * 1000, 1)},
            )
            _t_mus = _t.perf_counter()
        except Exception:
            _t_mus = 0.0
        # #endregion
        audio.play_music("title")
        # #region agent log
        try:
            from core.debug_agent import agent_log
            import time as _t

            agent_log(
                "H1",
                "TitleScene._ensure",
                "play_music returned",
                {"ms": round((_t.perf_counter() - _t_mus) * 1000, 1)},
            )
        except Exception:
            pass
        # #endregion
        self._load_phase = 2
        self._ready = True

    def _reload_skin_preview(self) -> None:
        name = player_skin_filename(self._skin_index)
        self._skin_preview = _load_sprite(name, (180, 180), (180, 120, 70))
        self._skin_label = name.replace("player_dobby_", "").replace(".png", "").replace("_", " ").upper()

    def _cycle_skin(self, delta: int) -> None:
        if not PLAYER_SKINS:
            return
        self._skin_index = (self._skin_index + int(delta)) % len(PLAYER_SKINS)
        save_player_skin_index(self._skin_index)
        self._reload_skin_preview()
        audio.play("ui_blip")
        self.idle_timer = 0.0
        self._block_confirm = True

    def _skin_hit_rects(self) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        """Left arrow, preview, right arrow — title skin cycle touch targets."""
        cy = HEIGHT // 2 + 520
        preview = pygame.Rect(0, 0, 180, 180)
        preview.center = (WIDTH // 2, cy)
        left = pygame.Rect(0, 0, 96, 96)
        left.centery = cy
        left.right = preview.left - 24
        right = pygame.Rect(0, 0, 96, 96)
        right.centery = cy
        right.left = preview.right + 24
        return left, preview, right

    def _phoenix_total_dur(self) -> float:
        return (
            self._PHOENIX_BURN_START
            + self._PHOENIX_BURN_DUR
            + self._PHOENIX_HOLD
            + self._PHOENIX_RESTORE
        )

    def _phoenix_push(self, token: str) -> bool:
        """Push konami token. Returns True if sequence just triggered."""
        if self._phoenix_done or self._phoenix_active:
            return False
        if self._phoenix_buf and self._phoenix_buf_age >= self.PHOENIX_WINDOW:
            self._phoenix_buf.clear()
            self._phoenix_buf_age = 0.0
        if not self._phoenix_buf:
            self._phoenix_buf_age = 0.0
        expected = self.PHOENIX_PATTERN[len(self._phoenix_buf)] if len(self._phoenix_buf) < len(self.PHOENIX_PATTERN) else None
        if token != expected:
            self._phoenix_buf = [token] if token == "up" else []
            self._phoenix_buf_age = 0.0
            return False
        self._phoenix_buf.append(token)
        if tuple(self._phoenix_buf) == self.PHOENIX_PATTERN:
            self._begin_phoenix()
            return True
        return False

    def _begin_phoenix(self) -> None:
        self._phoenix_buf.clear()
        self._phoenix_buf_age = 0.0
        self._phoenix_done = True
        self._phoenix_active = True
        self._phoenix_t = 0.0
        self._block_confirm = True
        self.idle_timer = 0.0
        audio.play("phoenix_screech")

    def _handle_pointer_konami(self, lx: float, ly: float) -> None:
        """Touch/mouse zones: upper third = up; lower third = fire."""
        if self._audio_panel.handle_click((int(lx), int(ly))):
            self.idle_timer = 0.0
            self._block_confirm = True
            return
        self._ensure()
        left, _preview, right = self._skin_hit_rects()
        pt = (int(lx), int(ly))
        if left.collidepoint(pt):
            self._cycle_skin(-1)
            return
        if right.collidepoint(pt):
            self._cycle_skin(1)
            return
        self.idle_timer = 0.0
        if self._phoenix_active:
            # Ignore start confirm while burn sequence plays.
            self._block_confirm = True
            return
        self._touch_konami = True
        if ly < HEIGHT / 3:
            self._phoenix_push("up")
            # Up taps must never start the game.
            self._block_confirm = True
        elif ly > 2 * HEIGHT / 3:
            if self._phoenix_push("fire"):
                self._block_confirm = True
            # else: allow confirm_pressed to start normally
        # Middle third: normal confirm / start via InputState

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
            self._handle_pointer_konami(lx, ly)
        if event.type == pygame.FINGERDOWN:
            lx, ly = event.x * WIDTH, event.y * HEIGHT
            self._handle_pointer_konami(lx, ly)

    def update(self, dt: float, inp: InputState) -> Optional[object]:
        self._ensure()
        # Finish staged load before accepting Start (also drains splash-skip taps).
        if not self._ready:
            self._block_confirm = True
            return self
        if self._enter_grace > 0.0:
            self._enter_grace = max(0.0, self._enter_grace - dt)
            self._block_confirm = True
            return self

        # Phoenix burn sequence: ignore start confirm; keep kiosk idle from firing.
        if self._phoenix_active:
            self.idle_timer = 0.0
            self._phoenix_t += dt
            self._touch_konami = False
            self._block_confirm = False
            if self._phoenix_t >= self._phoenix_total_dur():
                self._phoenix_active = False
            if inp.exit_ready:
                self.exit_requested = True
                return None
            return self

        if self._phoenix_buf:
            self._phoenix_buf_age += dt
            if self._phoenix_buf_age >= self.PHOENIX_WINDOW:
                self._phoenix_buf.clear()
                self._phoenix_buf_age = 0.0

        # Keyboard / pad konami (touch zones handled in handle_event).
        if not self._touch_konami and not self._phoenix_done:
            up_now = inp.move_y < -0.5
            if up_now and not self._prev_up:
                if self._phoenix_push("up"):
                    self._block_confirm = True
            self._prev_up = up_now
            if (inp.fire_pressed or inp.confirm_pressed) and not self._block_confirm:
                if self._phoenix_push("fire"):
                    self._block_confirm = True
        else:
            if not self._touch_konami:
                self._prev_up = inp.move_y < -0.5
        self._touch_konami = False

        # Edge-triggered left/right skin cycle (keyboard / pad).
        skin_dir = 0
        if inp.move_x <= -0.5:
            skin_dir = -1
        elif inp.move_x >= 0.5:
            skin_dir = 1
        if skin_dir and skin_dir != self._prev_skin_dir:
            self._cycle_skin(skin_dir)
        self._prev_skin_dir = skin_dir

        if self._block_confirm:
            self._block_confirm = False
            return self
        if self._phoenix_active:
            # Triggered this frame via push; stay on title.
            self.idle_timer = 0.0
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

    def _draw_title_base(self, surface: pygame.Surface) -> None:
        assert self._font and self._font_lg and self._font_sm
        BoothBlaster._draw_gradient_bg(surface)
        title = self._font_lg.render("BOOTH BLASTER", True, ACCENT)
        sub = self._font.render("Laser Monkey vs the Con Crowd", True, HUD_COLOR)
        tip_text, tip2_text, tip3_text = control_prompt_lines("Start")
        tip = self._font.render(tip_text, True, OK)
        tip2 = self._font.render(tip2_text, True, HUD_COLOR)
        tip3 = self._font.render(tip3_text, True, HUD_COLOR)
        tip4 = self._font.render("M mute · [ ] music · , . sfx", True, HUD_COLOR)
        tip5 = self._font_sm.render("Left/Right — cycle Dobby skin", True, HUD_COLOR)
        surface.blit(title, title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 420)))
        surface.blit(sub, sub.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 340)))
        surface.blit(tip, tip.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 260)))
        surface.blit(tip2, tip2.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 210)))
        surface.blit(tip3, tip3.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 160)))
        surface.blit(tip4, tip4.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 110)))
        surface.blit(tip5, tip5.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 60)))

        self._audio_panel.draw(surface)

        # Reuse leaderboard renderer
        dummy = BoothBlaster.__new__(BoothBlaster)
        dummy._font = self._font
        dummy._font_lg = self._font_lg
        BoothBlaster._draw_leaderboard(dummy, surface, HEIGHT // 2 - 20)

        left, preview, right = self._skin_hit_rects()
        if self._skin_preview is not None:
            surface.blit(self._skin_preview, preview)
        pygame.draw.rect(surface, ACCENT, left, border_radius=12)
        pygame.draw.rect(surface, ACCENT, right, border_radius=12)
        left_lbl = self._font_lg.render("<", True, HUD_COLOR)
        right_lbl = self._font_lg.render(">", True, HUD_COLOR)
        surface.blit(left_lbl, left_lbl.get_rect(center=left.center))
        surface.blit(right_lbl, right_lbl.get_rect(center=right.center))
        skin_name = self._font_sm.render(self._skin_label, True, OK)
        surface.blit(skin_name, skin_name.get_rect(center=(WIDTH // 2, preview.bottom + 28)))

    def _burn_alpha(self) -> float:
        """0..1 opacity of scorch overlay during the phoenix sequence."""
        t = self._phoenix_t
        burn0 = self._PHOENIX_BURN_START
        burn1 = burn0 + self._PHOENIX_BURN_DUR
        hold1 = burn1 + self._PHOENIX_HOLD
        end = hold1 + self._PHOENIX_RESTORE
        if t < burn0:
            return 0.0
        if t < burn1:
            return (t - burn0) / self._PHOENIX_BURN_DUR
        if t < hold1:
            return 1.0
        if t < end:
            return 1.0 - (t - hold1) / self._PHOENIX_RESTORE
        return 0.0

    def _draw_phoenix_fx(self, surface: pygame.Surface) -> None:
        if not self._phoenix_active or self._phoenix is None:
            return
        t = self._phoenix_t
        # Flyer crosses left → right while visible.
        if t <= self._PHOENIX_FLY_DUR + 0.15:
            u = min(1.0, t / self._PHOENIX_FLY_DUR)
            x = -180 + u * (WIDTH + 360)
            y = HEIGHT * 0.28 + math.sin(u * math.pi * 2.0) * 36
            surface.blit(self._phoenix, self._phoenix.get_rect(center=(int(x), int(y))))

        burn = self._burn_alpha()
        if burn <= 0.01:
            return
        # Scorch wipe: charcoal veil + ember edge sweeping downward.
        burn_end = self._PHOENIX_BURN_START + self._PHOENIX_BURN_DUR
        if t >= burn_end:
            wipe_y = HEIGHT
        else:
            wipe_u = max(0.0, (t - self._PHOENIX_BURN_START) / self._PHOENIX_BURN_DUR)
            wipe_y = int(HEIGHT * wipe_u)
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        a = int(210 * burn)
        if wipe_y > 0:
            overlay.fill((28, 12, 8, a), rect=pygame.Rect(0, 0, WIDTH, wipe_y))
            fringe = max(8, min(48, wipe_y))
            for i in range(fringe):
                fa = int(a * (1.0 - i / fringe) * 0.85)
                y = wipe_y - fringe + i
                if 0 <= y < HEIGHT:
                    pygame.draw.line(
                        overlay,
                        (255, int(90 + 80 * (i / fringe)), 30, fa),
                        (0, y),
                        (WIDTH, y),
                    )
        surface.blit(overlay, (0, 0))

    def draw(self, surface: pygame.Surface) -> None:
        # Do not call _ensure here — update advances one load phase per frame.
        if not self._ready or self._font is None or self._font_lg is None or self._font_sm is None:
            BoothBlaster._draw_gradient_bg(surface)
            return
        self._draw_title_base(surface)
        self._draw_phoenix_fx(surface)
