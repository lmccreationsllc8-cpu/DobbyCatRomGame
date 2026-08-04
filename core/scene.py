"""Tiny scene protocol for the main loop."""

from __future__ import annotations

from typing import Optional, Protocol

import pygame

from core.input import InputState


class Scene(Protocol):
    def handle_event(self, event: pygame.event.Event) -> None: ...

    def update(self, dt: float, inp: InputState) -> Optional["Scene"]: ...

    def draw(self, surface: pygame.Surface) -> None: ...
