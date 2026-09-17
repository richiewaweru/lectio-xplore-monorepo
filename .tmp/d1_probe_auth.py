import asyncio
from httpx import ASGITransport, AsyncClient

from app import app
from core.entities.user import User
from infra.auth.middleware import get_current_user

TEST_USER = User(
    id="path-route-owner",
    email="path-route@example.invalid",
    name="Path Route",
    created_at="2026-07-31T00:00:00+00:00",
    updated_at="2026-07-31T00:00:00+00:00",
)


async def main() -> None:
    async def override_user() -> User:
        return TEST_USER

    app.dependency_overrides[get_current_user] = override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/units")
        print(response.status_code, response.text[:500])
    app.dependency_overrides.clear()


asyncio.run(main())
