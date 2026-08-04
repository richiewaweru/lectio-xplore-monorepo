from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from core.database.models import UserModel
from core.entities.user import User
from core.repositories.sql_user_repo import SqlUserRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestSqlUserRepository:
    async def test_create_returns_user_without_profile(self, db_session: AsyncSession):
        repo = SqlUserRepository(db_session)
        user = User(
            id="user-create-1",
            email="new-user@example.com",
            name="New User",
            picture_url="https://example.com/avatar.png",
            created_at=_now(),
            updated_at=_now(),
            has_profile=False,
        )

        created = await repo.create(user)

        assert created.id == user.id
        assert created.email == user.email
        assert created.has_profile is False

    async def test_update_returns_user_without_profile(self, db_session: AsyncSession):
        db_session.add(
            UserModel(
                id="user-update-1",
                email="existing-user@example.com",
                name="Existing User",
                picture_url="https://example.com/original.png",
            )
        )
        await db_session.commit()

        repo = SqlUserRepository(db_session)
        updated = await repo.update(
            User(
                id="user-update-1",
                email="existing-user@example.com",
                name="Updated User",
                picture_url="https://example.com/updated.png",
                created_at=_now(),
                updated_at=_now(),
                has_profile=False,
            )
        )

        assert updated.id == "user-update-1"
        assert updated.name == "Updated User"
        assert updated.picture_url == "https://example.com/updated.png"
        assert updated.has_profile is False
