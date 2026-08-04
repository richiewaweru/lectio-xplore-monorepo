from __future__ import annotations

import os

V3_TIMEOUTS: dict[str, int] = {
    "signal_extractor": int(os.getenv("V3_TIMEOUT_SIGNAL_SECONDS", "30")),
    "narrow": int(os.getenv("V3_TIMEOUT_CLARIFY_SECONDS", "15")),
    "propose_intent": int(os.getenv("V3_TIMEOUT_PROPOSE_INTENT_SECONDS", "25")),
    "section_writer": int(os.getenv("V3_TIMEOUT_SECTION_SECONDS", "90")),
    "question_writer": int(os.getenv("V3_TIMEOUT_QUESTION_SECONDS", "60")),
    "answer_key_generator": int(os.getenv("V3_TIMEOUT_ANSWER_KEY_SECONDS", "30")),
    "visual_executor_frame": int(os.getenv("V3_TIMEOUT_VISUAL_FRAME_SECONDS", "45")),
    "assembly": int(os.getenv("V3_TIMEOUT_ASSEMBLY_SECONDS", "30")),
    "generation_total": int(os.getenv("V3_TIMEOUT_GENERATION_TOTAL_SECONDS", "600")),
}

__all__ = ["V3_TIMEOUTS"]
