from __future__ import annotations

from fastapi import Depends, HTTPException, status

from core.auth.middleware import get_current_user
from core.config import settings
from core.entities.user import User


def _beta_principals() -> set[str]:
    return {
        value.strip().lower()
        for value in settings.xplore_v2_beta_users.split(",")
        if value.strip()
    }


def xplore_v2_enabled_for(user: User) -> bool:
    if not settings.xplore_v2_enabled:
        return False
    principals = _beta_principals()
    return not principals or user.id.lower() in principals or user.email.lower() in principals


async def require_xplore_v2(
    current_user: User = Depends(get_current_user),
) -> User:
    if not xplore_v2_enabled_for(current_user):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Xplore V2 is not enabled for this account.",
        )
    return current_user
