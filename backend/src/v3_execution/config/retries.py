from __future__ import annotations

import os

V3_MAX_RETRIES: dict[str, int] = {
    "signal_extractor": int(os.getenv("V3_RETRY_SIGNAL_MAX", "2")),
    "narrow": int(os.getenv("V3_RETRY_CLARIFY_MAX", "1")),
    "section_writer": int(os.getenv("V3_RETRY_SECTION_MAX", "1")),
    "question_writer": int(os.getenv("V3_RETRY_QUESTION_MAX", "1")),
    "answer_key_generator": int(os.getenv("V3_RETRY_ANSWER_KEY_MAX", "1")),
    "visual_executor_frame": int(os.getenv("V3_RETRY_VISUAL_MAX", "1")),
}

__all__ = ["V3_MAX_RETRIES"]
