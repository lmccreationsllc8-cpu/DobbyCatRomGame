"""DobbyCatRomGame entry — Booth Blaster prototype.

Desktop: ``python main.py``
Web (pygbag): async loop with ``await asyncio.sleep(0)`` each frame.
"""

from __future__ import annotations

import asyncio

import pygame

import config
from core import audio
from core.input import InputManager
from core.platform import (
    apply_mobile_runtime_tweaks,
    create_display,
    is_web,
    mixer_buffer,
    mixer_frequency,
)
from games.booth_blaster import LoadingScene


async def main() -> None:
    # Must run before pygame.init(): otherwise init opens the mixer with a
    # 512-sample buffer and web/Android audio underruns (crackle/distortion).
    pygame.mixer.pre_init(mixer_frequency(), -16, 2, mixer_buffer())
    pygame.init()
    apply_mobile_runtime_tweaks()
    audio.init()
    pygame.display.set_caption(config.TITLE)

    screen = create_display((config.WIDTH, config.HEIGHT))
    canvas = pygame.Surface((config.WIDTH, config.HEIGHT))

    clock = pygame.time.Clock()
    inputs = InputManager()
    scene: object = LoadingScene()
    running = True
    elapsed = 0.0

    while running:
        dt = clock.tick(config.FPS) / 1000.0
        elapsed += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            inputs.handle_device_event(event)
            if hasattr(scene, "handle_event"):
                scene.handle_event(event)  # type: ignore[union-attr]

        if not running:
            break

        inp = inputs.poll(dt)
        audio.tick(dt)
        next_scene = scene.update(dt, inp)  # type: ignore[union-attr]

        if getattr(scene, "exit_requested", False):
            running = False
            break

        if next_scene is not None and next_scene is not scene:
            scene = next_scene

        scene.draw(canvas)  # type: ignore[union-attr]
        if screen.get_size() != canvas.get_size():
            pygame.transform.smoothscale(canvas, screen.get_size(), screen)
        else:
            screen.blit(canvas, (0, 0))
        pygame.display.flip()

        if config.SMOKE_SECONDS > 0 and elapsed >= config.SMOKE_SECONDS:
            running = False

        # Required for pygbag / browser: yield to the event loop each frame.
        await asyncio.sleep(0)

    if not is_web():
        audio.shutdown()
        pygame.quit()


# On pygame-wasm, asyncio.run is non-blocking — do not exit or quit after this.
asyncio.run(main())
