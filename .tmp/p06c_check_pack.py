import asyncio
from sqlalchemy import text
from core.database.session import get_async_engine


async def main() -> None:
    eng = get_async_engine()
    async with eng.connect() as c:
        r = await c.execute(
            text("select id, pack_id from path_lessons where id = :id"),
            {"id": "5901155d-8dfa-4e92-8285-0ab3170efd4d"},
        )
        print("LESSON", dict(r.mappings().one()))
        r = await c.execute(
            text(
                "select id, status from generations where id in "
                "('7206057e-5b25-4af8-9a77-40742213efac',"
                "'8a890460-7324-4927-8a90-33aa7da5baa3')"
            )
        )
        for row in r.mappings():
            print("GEN", dict(row))


if __name__ == "__main__":
    asyncio.run(main())
