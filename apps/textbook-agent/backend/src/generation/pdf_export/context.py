from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(slots=True)
class PDFGenerationContext:
    id: str
    user_id: str
    subject: str
    context: str = ""
    mode: str = "v3"
    status: str = "completed"
    requested_template_id: str = "guided-concept-path"
    requested_preset_id: str = "blue-classroom"
    resolved_template_id: str | None = None
    resolved_preset_id: str | None = None
    quality_passed: bool | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
