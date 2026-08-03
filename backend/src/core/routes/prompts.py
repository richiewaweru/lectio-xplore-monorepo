from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth.middleware import get_current_user
from core.dependencies import get_async_session
from core.entities.user import User
from core.prompts import (
    PromptLockedError,
    PromptNotFoundError,
    delete_override,
    get_default_prompt,
    get_manifest_entry,
    is_modified,
    list_manifest,
    resolve_prompt,
    save_override,
)

router = APIRouter(prefix="/api/v1/prompts", tags=["prompts"])


class PromptListItem(BaseModel):
    id: str
    stage_label: str
    editable: bool
    modified: bool
    version: int


class PromptDetail(BaseModel):
    id: str
    stage_label: str
    editable: bool
    text: str
    modified: bool
    version: int


class PromptUpdateRequest(BaseModel):
    text: str = Field(min_length=1)


def _entry_or_404(prompt_id: str):
    try:
        return get_manifest_entry(prompt_id)
    except PromptNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown prompt id: {prompt_id}",
        ) from exc


def _default_text_or_500(prompt_id: str) -> str:
    try:
        return get_default_prompt(prompt_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc


@router.get("", response_model=list[PromptListItem])
async def list_prompts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> list[PromptListItem]:
    items: list[PromptListItem] = []
    for entry in list_manifest():
        modified = await is_modified(entry.id, current_user.id, session)
        items.append(
            PromptListItem(
                id=entry.id,
                stage_label=entry.stage_label,
                editable=entry.editable,
                modified=modified,
                version=entry.version,
            )
        )
    return items


@router.get("/{prompt_id}", response_model=PromptDetail)
async def get_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PromptDetail:
    entry = _entry_or_404(prompt_id)
    text, _sha256 = await resolve_prompt(prompt_id, current_user.id, session)
    modified = await is_modified(prompt_id, current_user.id, session)
    return PromptDetail(
        id=entry.id,
        stage_label=entry.stage_label,
        editable=entry.editable,
        text=text,
        modified=modified,
        version=entry.version,
    )


@router.put("/{prompt_id}", response_model=PromptDetail)
async def update_prompt(
    prompt_id: str,
    body: PromptUpdateRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PromptDetail:
    entry = _entry_or_404(prompt_id)
    if not entry.editable:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Prompt '{prompt_id}' is locked and cannot be edited.",
        )
    try:
        await save_override(prompt_id, current_user.id, body.text, session)
    except PromptLockedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Prompt '{prompt_id}' is locked and cannot be edited.",
        ) from exc
    return PromptDetail(
        id=entry.id,
        stage_label=entry.stage_label,
        editable=entry.editable,
        text=body.text,
        modified=True,
        version=entry.version,
    )


@router.delete("/{prompt_id}", response_model=PromptDetail)
async def reset_prompt(
    prompt_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_async_session),
) -> PromptDetail:
    entry = _entry_or_404(prompt_id)
    await delete_override(prompt_id, current_user.id, session)
    text = _default_text_or_500(prompt_id)
    return PromptDetail(
        id=entry.id,
        stage_label=entry.stage_label,
        editable=entry.editable,
        text=text,
        modified=False,
        version=entry.version,
    )


__all__ = ["router"]
