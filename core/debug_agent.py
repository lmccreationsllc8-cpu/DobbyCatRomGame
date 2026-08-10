"""Session debug logger for freeze investigation (desktop file + web ingest)."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

_SESSION = "c09524"
_LOG = Path(__file__).resolve().parents[1] / "debug-c09524.log"
_INGEST = "http://127.0.0.1:7319/ingest/a26fd018-190b-4e9e-8c78-2c75b0f5e30e"
_COUNT = 0


def agent_log(
    hypothesis_id: str,
    location: str,
    message: str,
    data: Optional[dict[str, Any]] = None,
    run_id: str = "pre",
) -> None:
    # #region agent log
    global _COUNT
    _COUNT += 1
    payload = {
        "sessionId": _SESSION,
        "id": f"log_{int(time.time() * 1000)}_{_COUNT}",
        "timestamp": int(time.time() * 1000),
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
    # Browser: write to JS console (CDP can see this) + local ingest.
    try:
        import platform as _plat

        _plat.window.console.log(text)
        body = json.dumps(payload)
        _plat.window.fetch(
            _INGEST,
            {
                "method": "POST",
                "headers": {
                    "Content-Type": "application/json",
                    "X-Debug-Session-Id": _SESSION,
                },
                "body": body,
            },
        )
    except Exception:
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
            urllib.request.urlopen(req, timeout=0.3).read()
        except Exception:
            pass
    # #endregion
