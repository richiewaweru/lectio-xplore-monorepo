from abc import ABC, abstractmethod

from core.entities.user import User


class UserRepository(ABC):
    """Abstract repository for user persistence."""

    @abstractmethod
    async def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def find_by_id(self, user_id: str) -> User | None: ...

    @abstractmethod
    async def create(self, user: User) -> User: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...
