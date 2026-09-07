from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def ensure_temp_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def cleanup_files(paths: list[Path]) -> None:
    for path in paths:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            continue


def cleanup_stale_exports(*, temp_dir: Path, retention_seconds: int) -> int:
    if not temp_dir.exists():
        return 0

    cutoff = datetime.now(timezone.utc).timestamp() - retention_seconds
    removed = 0
    for path in temp_dir.iterdir():
        try:
            if not path.is_file():
                continue
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            removed += 1
        except OSError:
            continue
    return removed
