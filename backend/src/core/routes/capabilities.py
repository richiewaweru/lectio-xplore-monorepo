from fastapi import APIRouter, Depends

from core.auth.middleware import get_current_user
from core.capabilities import xplore_v2_enabled_for
from core.entities.user import User


router = APIRouter(prefix="/api/v1/capabilities", tags=["capabilities"])


@router.get("")
async def get_capabilities(
    current_user: User = Depends(get_current_user),
) -> dict[str, bool]:
    return {"xplore_v2": xplore_v2_enabled_for(current_user)}
