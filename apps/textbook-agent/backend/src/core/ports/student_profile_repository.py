from abc import ABC, abstractmethod

from core.entities.student_profile import StudentProfile


class StudentProfileRepository(ABC):
    """Abstract repository for student profile persistence."""

    @abstractmethod
    async def find_by_user_id(self, user_id: str) -> StudentProfile | None: ...

    @abstractmethod
    async def create(self, profile: StudentProfile) -> StudentProfile: ...

    @abstractmethod
    async def update(self, profile: StudentProfile) -> StudentProfile: ...
