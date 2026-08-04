from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import app
from core.database.models import UserModel
from core.dependencies import get_user_repository
from core.repositories.sql_user_repo import SqlUserRepository


@asynccontextmanager
async def _client():
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client


class TestGoogleAuthRoute:
    async def test_google_login_creates_new_user_on_first_attempt(
        self,
        db_session: AsyncSession,
    ):
        await db_session.execute(
            delete(UserModel).where(UserModel.email == "brand-new@example.com")
        )
        await db_session.commit()

        async def override_user_repo():
            return SqlUserRepository(db_session)

        app.dependency_overrides[get_user_repository] = override_user_repo

        with patch(
            "core.routes.auth.verify_google_token",
            return_value=SimpleNamespace(
                email="brand-new@example.com",
                name="Brand New User",
                picture_url="https://example.com/google-avatar.png",
            ),
        ):
            try:
                async with _client() as client:
                    first_response = await client.post(
                        "/api/v1/auth/google",
                        json={"credential": "test-google-credential"},
                    )
                    second_response = await client.post(
                        "/api/v1/auth/google",
                        json={"credential": "test-google-credential"},
                    )
            finally:
                app.dependency_overrides.clear()

        assert first_response.status_code == 200
        first_payload = first_response.json()
        assert first_payload["access_token"]
        assert first_payload["user"]["email"] == "brand-new@example.com"
        assert first_payload["user"]["has_profile"] is False

        assert second_response.status_code == 200
        second_payload = second_response.json()
        assert second_payload["user"]["email"] == "brand-new@example.com"
        assert second_payload["user"]["has_profile"] is False

        result = await db_session.execute(
            select(UserModel).where(UserModel.email == "brand-new@example.com")
        )
        created = result.scalar_one()
        assert created.name == "Brand New User"
