from abc import ABC, abstractmethod

from pipeline.api import PipelineDocument


class DocumentRepository(ABC):
    @abstractmethod
    async def save_document(self, document: PipelineDocument) -> str: ...

    @abstractmethod
    async def load_document(self, path: str) -> PipelineDocument: ...
