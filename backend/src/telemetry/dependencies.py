from functools import lru_cache

from core.database.session import async_session_factory
from telemetry.repositories.sql_llm_call_repo import SqlLLMCallRepository
from telemetry.v3_trace.repository import V3TraceRepository


@lru_cache
def get_llm_call_repository() -> SqlLLMCallRepository:
    return SqlLLMCallRepository(async_session_factory)


@lru_cache
def get_v3_trace_repository() -> V3TraceRepository:
    return V3TraceRepository(async_session_factory)
