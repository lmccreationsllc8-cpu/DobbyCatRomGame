"""List connected joysticks and print live button / hat / axis events.

Run on the Pi with the 2.4G SNES USB dongle plugged in to discover indices
before adjusting DOBBY_PAD_* env overrides or profiles.

  python tools/probe_joystick.py
  python tools/probe_joystick.py --quit-after 30
"""

from __future__ import annotations

import argparse
import sys
import time

import pygame


def _list_joysticks() -> list[pygame.joystick.Joystick]:
    joys: list[pygame.joystick.Joystick] = []
    count = pygame.joystick.get_count()
    print(f"Joysticks connected: {count}")
    for i in range(count):
        joy = pygame.joystick.Joystick(i)
        joy.init()
        joys.append(joy)
        print(
            f"  [{i}] name={joy.get_name()!r} "
            f"buttons={joy.get_numbuttons()} "
            f"axes={joy.get_numaxes()} "
            f"hats={joy.get_numhats()}"
        )
    if not count:
        print("  (none — plug in the USB dongle and re-run)")
    return joys


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe pygame joystick mappings")
    parser.add_argument(
        "--quit-after",
        type=float,
        default=0.0,
        help="Exit after N seconds (0 = run until Ctrl+C)",
    )
    args = parser.parse_args()

    pygame.init()
    pygame.joystick.init()
    # Small window so the event pump works on desktop / Pi desktop sessions.
    pygame.display.set_mode((360, 200))
    pygame.display.set_caption("Joystick probe — press buttons / D-pad")

    _list_joysticks()
    print("Listening for JOYBUTTONDOWN / JOYHATMOTION / JOYAXISMOTION (Ctrl+C to quit)...")
    print("-" * 60)

    deadline = time.monotonic() + args.quit_after if args.quit_after > 0 else None
    last_axis: dict[tuple[int, int], float] = {}

    try:
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                break
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return 0
                if event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
                    print(f"Device change: {pygame.event.event_name(event.type)}")
                    _list_joysticks()
                    continue
                if event.type == pygame.JOYBUTTONDOWN:
                    print(f"JOYBUTTONDOWN  joy={event.instance_id} button={event.button}")
                elif event.type == pygame.JOYBUTTONUP:
                    print(f"JOYBUTTONUP    joy={event.instance_id} button={event.button}")
                elif event.type == pygame.JOYHATMOTION:
                    print(f"JOYHATMOTION   joy={event.instance_id} hat={event.hat} value={event.value}")
                elif event.type == pygame.JOYAXISMOTION:
                    key = (event.instance_id, event.axis)
                    prev = last_axis.get(key)
                    # Debounce tiny stick noise; always print when crossing deadzone.
                    if prev is None or abs(event.value - prev) >= 0.15:
                        last_axis[key] = event.value
                        print(
                            f"JOYAXISMOTION  joy={event.instance_id} "
                            f"axis={event.axis} value={event.value:+.3f}"
                        )
            pygame.time.wait(10)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
