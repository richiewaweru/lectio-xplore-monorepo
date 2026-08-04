from .auth import router as auth_router
from core.health.routes import router as health_router
from .profile import router as profile_router

__all__ = ["auth_router", "health_router", "profile_router"]
