"""Session debug logger for freeze investigation (desktop file + web console)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

_SESSION = "c09524"
_LOG = Path(__file__).resolve().parents[1] / "debug-c09524.log"
_INGEST = "http://127.0.0.1:7319/ingest/a26fd018-190b-4e9e-8c78-2c75b0f5e30e"
_COUNT = 0
# Rate-limit noisy per-frame logs (hypothesis H5/H9).
_LAST_KEY_MS: dict[str, int] = {}


def agent_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[dict[str, Any]] = None,
    run_id: str = "post-fix",
    min_interval_ms: int = 0,
) -> None:
    # #region agent log
    global _COUNT
    now = int(time.time() * 1000)
    if min_interval_ms > 0:
        key = f"{hypothesis_id}:{location}:{message}"
        prev = _LAST_KEY_MS.get(key, 0)
        if now - prev < min_interval_ms:
            return
        _LAST_KEY_MS[key] = now
    _COUNT += 1
    payload = {
        "sessionId": _SESSION,
        "id": f"log_{now}_{_COUNT}",
        "timestamp": now,
        "location": location,
        "message": message,
        "hypothesisId": hypothesis_id,
        "runId": run_id,
        "data": data or {},
    }
    line = json.dumps(payload, ensure_ascii=True)
    try:
        with _LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        pass
    text = f"[agent:{hypothesis_id}] {location} | {message} | {data or {}}"
    try:
        print(text, flush=True)
    except Exception:
        pass
    # Web: console + fire-and-forget ingest (local PC browser debug sessions).
    try:
        from core.platform import is_web

        if is_web():
            import platform as _plat

            _plat.window.console.log(text)
            # Do not await the promise — awaiting unreachable hosts freezes WASM.
            _plat.window.fetch(
                _INGEST,
                {
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json",
                        "X-Debug-Session-Id": _SESSION,
                    },
                    "body": line,
                    "mode": "no-cors",
                    "keepalive": True,
                },
            )
            return
    except Exception:
        pass
    # Desktop native: short-timeout ingest.
    try:
        import urllib.request

        req = urllib.request.Request(
            _INGEST,
            data=line.encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "X-Debug-Session-Id": _SESSION,
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=0.05).read()
    except Exception:
        pass
    # #endregion
