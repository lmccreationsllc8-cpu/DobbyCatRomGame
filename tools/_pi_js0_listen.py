"""Read /dev/input/js0 directly (no X11). Prints button/axis/hat-like events."""
from __future__ import annotations

import os
import struct
import sys
import time

# linux/joystick.h: struct js_event { __u32 time; __s16 value; __u8 type; __u8 number; }
JS_EVENT_BUTTON = 0x01
JS_EVENT_AXIS = 0x02
JS_EVENT_INIT = 0x80
FMT = "IhBB"
SIZE = struct.calcsize(FMT)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else "/dev/input/js0"
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 20.0
    if not os.path.exists(path):
        print("MISSING", path, flush=True)
        return 1

    print("OPEN", path, "for", seconds, "sec — press pad buttons now", flush=True)
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    deadline = time.monotonic() + seconds
    seen_btn: set[int] = set()
    seen_axis: set[int] = set()
    try:
        while time.monotonic() < deadline:
            try:
                data = os.read(fd, SIZE)
            except BlockingIOError:
                time.sleep(0.02)
                continue
            if len(data) < SIZE:
                continue
            _t, value, typ, number = struct.unpack(FMT, data)
            kind = typ & ~JS_EVENT_INIT
            init = bool(typ & JS_EVENT_INIT)
            if kind == JS_EVENT_BUTTON:
                if not init and value:
                    seen_btn.add(number)
                    print("BUTTON", number, "down", flush=True)
                elif not init:
                    print("BUTTON", number, "up", flush=True)
            elif kind == JS_EVENT_AXIS:
                if not init and abs(value) > 10000:
                    seen_axis.add(number)
                    print("AXIS", number, value, flush=True)
    finally:
        os.close(fd)

    print("DONE buttons=", sorted(seen_btn), flush=True)
    print("DONE axes=", sorted(seen_axis), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
