from __future__ import annotations

from core.ports.generation_engine import GenerationEngine
from pipeline.run import run_pipeline_streaming


class PipelineGenerationEngine(GenerationEngine):
    async def run_streaming(self, command, on_event=None):
        return await run_pipeline_streaming(command, on_event=on_event)
