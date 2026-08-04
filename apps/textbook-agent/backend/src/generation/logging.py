from __future__ import annotations

import logging


class GenerationLogger(logging.LoggerAdapter):
    def __init__(self, generation_id: str, user_id: str) -> None:
        super().__init__(
            logging.getLogger("generation"),
            {"generation_id": generation_id, "user_id": user_id},
        )

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs
