from __future__ import annotations

import json
import sys
from typing import Any


def force_console_log(channel: str, event: str, **fields: Any) -> None:
    sys.stderr.write(
        f"{channel}::{event}::{json.dumps(fields, default=str, sort_keys=True)}\n"
    )
    sys.stderr.flush()

