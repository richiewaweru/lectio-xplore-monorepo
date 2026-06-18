from abc import ABC, abstractmethod

from pipeline.reporting import GenerationReport


class GenerationReportRepository(ABC):
    """Abstract repository for per-generation diagnostics report persistence."""

    @abstractmethod
    async def save_report(self, report: GenerationReport) -> str: ...

    @abstractmethod
    async def load_report(self, generation_id: str) -> GenerationReport: ...

    async def cleanup_tmp(self, generation_id: str) -> None:
        """Remove leftover temporary files from interrupted report writes."""
