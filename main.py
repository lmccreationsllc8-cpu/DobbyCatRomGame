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
            # #region agent log
            try:
                from core.debug_agent import agent_log

                agent_log(
                    "H4",
                    "main.loop",
                    "scene switch",
                    {
                        "from": type(scene).__name__,
                        "to": type(next_scene).__name__,
                        "web": is_web(),
                        "elapsed": round(elapsed, 3),
                    },
                )
            except Exception:
                pass
            # #endregion
            scene = next_scene
            # Let the browser breathe after splash→title / title→game switches.
            await asyncio.sleep(0)

        # Chunk heavy sprite loads across frames (critical on single-thread WASM).
        load_step = getattr(scene, "load_assets_step", None)
        is_loading = getattr(scene, "assets_loading", None)
        if callable(load_step) and callable(is_loading) and is_loading():
            load_step()
            canvas.fill((20, 16, 32))
            if screen.get_size() != canvas.get_size():
                pygame.transform.scale(canvas, screen.get_size(), screen)
            else:
                screen.blit(canvas, (0, 0))
            pygame.display.flip()
            await asyncio.sleep(0)
            continue

        # #region agent log
        try:
            if type(scene).__name__ == "TitleScene" and elapsed < 8.0:
                from core.debug_agent import agent_log

                agent_log(
                    "H5",
                    "main.loop",
                    "title frame before draw",
                    {
                        "ready": bool(getattr(scene, "_ready", False)),
                        "phase": getattr(scene, "_load_phase", None),
                        "grace": round(float(getattr(scene, "_enter_grace", 0.0)), 3),
                        "elapsed": round(elapsed, 3),
                    },
                )
        except Exception:
            pass
        # #endregion
        scene.draw(canvas)  # type: ignore[union-attr]
        # #region agent log
        try:
            if type(scene).__name__ == "TitleScene" and elapsed < 8.0:
                from core.debug_agent import agent_log

                agent_log(
                    "H5",
                    "main.loop",
                    "title frame after draw",
                    {
                        "ready": bool(getattr(scene, "_ready", False)),
                        "phase": getattr(scene, "_load_phase", None),
                    },
                )
            elif type(scene).__name__ == "LoadingScene" and getattr(scene, "_elapsed", 0) > 2.0:
                from core.debug_agent import agent_log

                agent_log(
                    "H4",
                    "main.loop",
                    "still on LoadingScene late",
                    {"splash_elapsed": round(float(getattr(scene, "_elapsed", 0.0)), 3)},
                )
        except Exception:
            pass
        # #endregion
        if screen.get_size() != canvas.get_size():
            # Prefer nearest on web — smoothscale every frame is expensive.
            if is_web():
                pygame.transform.scale(canvas, screen.get_size(), screen)
            else:
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
