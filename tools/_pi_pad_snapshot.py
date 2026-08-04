"""One-shot: list joysticks, then sample buttons/hats/axes for N seconds."""
from __future__ import annotations

import sys
import time

import pygame


def main() -> int:
    seconds = float(sys.argv[1]) if len(sys.argv) > 1 else 20.0
    pygame.init()
    pygame.joystick.init()
    pygame.display.set_mode((320, 180))
    pygame.display.set_caption("Pad snapshot — press buttons")

    count = pygame.joystick.get_count()
    print("joysticks", count, flush=True)
    joys = []
    for i in range(count):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        joys.append(joy)
        print(
            "device",
            i,
            "name=",
            repr(joy.get_name()),
            "buttons=",
            joy.get_numbuttons(),
            "axes=",
            joy.get_numaxes(),
            "hats=",
            joy.get_numhats(),
            flush=True,
        )
    if not joys:
        print("NO_PAD", flush=True)
        return 1

    print("LISTEN", seconds, "sec — press B Y Select Start and D-pad", flush=True)
    seen_buttons: set[tuple[int, int]] = set()
    seen_hats: set[tuple[int, int, tuple]] = set()
    seen_axes: set[tuple[int, int]] = set()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        for event in pygame.event.get():
            if event.type == pygame.JOYBUTTONDOWN:
                key = (event.instance_id, event.button)
                if key not in seen_buttons:
                    seen_buttons.add(key)
                    print("BUTTON", event.instance_id, event.button, flush=True)
            elif event.type == pygame.JOYHATMOTION and event.value != (0, 0):
                key = (event.instance_id, event.hat, event.value)
                if key not in seen_hats:
                    seen_hats.add(key)
                    print("HAT", event.instance_id, event.hat, event.value, flush=True)
            elif event.type == pygame.JOYAXISMOTION and abs(event.value) >= 0.5:
                key = (event.instance_id, event.axis)
                if key not in seen_axes:
                    seen_axes.add(key)
                    print(
                        "AXIS",
                        event.instance_id,
                        event.axis,
                        round(event.value, 3),
                        flush=True,
                    )
        pygame.time.wait(10)

    print("DONE buttons=", sorted(b for _, b in seen_buttons), flush=True)
    print("DONE hats=", sorted((h, v) for _, h, v in seen_hats), flush=True)
    print("DONE axes=", sorted(a for _, a in seen_axes), flush=True)
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
