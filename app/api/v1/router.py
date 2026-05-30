from fastapi import APIRouter

from app.api.v1.endpoints import auth, families, users

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(families.router, prefix="/families", tags=["families"])
router.include_router(users.router, prefix="/users", tags=["users"])
