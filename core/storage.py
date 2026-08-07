"""Cross-platform tiny key/value text storage (disk or browser localStorage)."""

from __future__ import annotations

from pathlib import Path

from core.platform import is_web, writable_data_dir


def _web_key(name: str) -> str:
    return f"dobbycat:{name}"


def read_text(name: str) -> str | None:
    """Return stored UTF-8 text for ``name``, or None if missing/unreadable."""
    if is_web():
        try:
            import platform as _plat

            raw = _plat.window.localStorage.getItem(_web_key(name))
            if raw is None:
                return None
            return str(raw)
        except Exception:
            return None
    path = writable_data_dir() / name
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def write_text(name: str, text: str) -> None:
    """Persist UTF-8 text under ``name``."""
    if is_web():
        try:
            import platform as _plat

            _plat.window.localStorage.setItem(_web_key(name), text)
        except Exception:
            pass
        return
    path = writable_data_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def exists(name: str) -> bool:
    if is_web():
        return read_text(name) is not None
    return (writable_data_dir() / name).is_file()


def path_for(name: str) -> Path:
    """Filesystem path helper for desktop/Android callers (not used on web)."""
    return writable_data_dir() / name
