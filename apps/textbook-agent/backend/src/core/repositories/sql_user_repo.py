import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.database.models import UserModel
from core.entities.user import User
from core.ports.user_repository import UserRepository


class SqlUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_user_model(self, user_id: str) -> UserModel:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(UserModel.id == user_id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def find_by_email(self, email: str) -> User | None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(UserModel.email == email)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def find_by_id(self, user_id: str) -> User | None:
        stmt = (
            select(UserModel)
            .options(selectinload(UserModel.profile))
            .where(UserModel.id == user_id)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_entity(row) if row else None

    async def create(self, user: User) -> User:
        now = datetime.utcnow()
        model = UserModel(
            id=user.id or str(uuid.uuid4()),
            email=user.email,
            name=user.name,
            picture_url=user.picture_url,
            created_at=now,
            updated_at=now,
        )
        self._session.add(model)
        await self._session.commit()
        created = await self._load_user_model(model.id)
        return self._to_entity(created)

    async def update(self, user: User) -> User:
        stmt = select(UserModel).where(UserModel.id == user.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one()
        model.name = user.name
        model.picture_url = user.picture_url
        model.updated_at = datetime.utcnow()
        await self._session.commit()
        updated = await self._load_user_model(model.id)
        return self._to_entity(updated)

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            name=model.name,
            picture_url=model.picture_url,
            created_at=model.created_at,
            updated_at=model.updated_at,
            has_profile=model.profile is not None,
        )
