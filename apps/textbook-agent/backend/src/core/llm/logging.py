from __future__ import annotations

import logging


class NodeLogger(logging.LoggerAdapter):
    def __init__(
        self,
        *,
        generation_id: str,
        section_id: str | None = None,
        node_name: str,
    ) -> None:
        super().__init__(
            logging.getLogger(f"lectio.{node_name}"),
            {
                "generation_id": generation_id,
                "section_id": section_id,
                "node_name": node_name,
            },
        )

    def process(self, msg: str, kwargs: dict) -> tuple[str, dict]:
        kwargs.setdefault("extra", {}).update(self.extra)
        return msg, kwargs
