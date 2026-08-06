"""Source-level regression: executor/service avoid direct status assigns."""

from __future__ import annotations

import re
from pathlib import Path

WHOLE_LESSON = Path(__file__).resolve().parents[2] / "src" / "planning" / "whole_lesson"
FORBIDDEN = {"executor.py", "service.py", "worker.py", "form_agent.py"}


def test_executor_service_worker_no_direct_status_assign() -> None:
    pattern = re.compile(r"generation\.status\s*=(?!=)")
    offenders: list[str] = []
    for name in sorted(FORBIDDEN):
        path = WHOLE_LESSON / name
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{name}:{i}:{line.strip()}")
    assert offenders == [], "direct status assigns outside repository:\n" + "\n".join(
        offenders
    )
