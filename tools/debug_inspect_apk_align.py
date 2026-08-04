"""Inspect APK .so LOAD alignment; write NDJSON to debug-b4844d.log."""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "bin" / "boothblaster-0.1.1-arm64-v8a-debug.apk"
if not APK.is_file():
    APK = ROOT / "bin" / "boothblaster-0.1.0-arm64-v8a-debug.apk"
LOG = ROOT / "debug-b4844d.log"
READELF_CANDIDATES = [
    Path("/home/builder/.buildozer/android/platform/android-ndk-r25b/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"),
    Path("/home/builder/.buildozer/android/platform/android-ndk-r28b/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"),
    Path("/home/builder/.buildozer/android/platform/android-ndk-r28/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"),
]


def emit(hid: str, msg: str, data: dict) -> None:
    entry = {
        "sessionId": "b4844d",
        "runId": "pre-fix",
        "hypothesisId": hid,
        "location": "debug_inspect_apk_align.py",
        "message": msg,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry, indent=2))


def find_readelf() -> str:
    for p in READELF_CANDIDATES:
        if p.is_file():
            return str(p)
    return "readelf"


def parse_aligns(text: str) -> list[str]:
    aligns: list[str] = []
    for line in text.splitlines():
        if "LOAD" in line:
            parts = line.split()
            if parts:
                aligns.append(parts[-1])
    return aligns


def align_ok(aligns: list[str]) -> bool:
    for a in aligns:
        try:
            val = int(a, 0)
        except ValueError:
            return False
        if val < 16384:
            return False
    return bool(aligns)


def main() -> int:
    if not APK.is_file():
        emit("D", "APK missing", {"apk": str(APK)})
        return 1
    readelf = find_readelf()
    results: dict = {}
    with tempfile.TemporaryDirectory() as tmp:
        tdir = Path(tmp)
        with zipfile.ZipFile(APK) as z:
            for name in z.namelist():
                if not name.startswith("lib/") or not name.endswith(".so"):
                    continue
                dest = tdir / Path(name).name
                dest.write_bytes(z.read(name))
                try:
                    out = subprocess.check_output(
                        [readelf, "-l", str(dest)], text=True, errors="replace"
                    )
                except subprocess.CalledProcessError as exc:
                    results[dest.name] = {
                        "error": (exc.stderr or exc.stdout or str(exc))[:200],
                        "ok16k": False,
                    }
                    continue
                aligns = parse_aligns(out)
                results[dest.name] = {"load_aligns": aligns, "ok16k": align_ok(aligns)}
    emit("D", "LOAD segment alignment of APK .so files", {"readelf": readelf, "results": results})
    bad = [k for k, v in results.items() if not v.get("ok16k")]
    emit("D", "16k alignment summary", {"bad_count": len(bad), "bad": bad, "good_count": len(results) - len(bad)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
