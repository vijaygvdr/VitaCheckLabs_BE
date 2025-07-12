from fastapi import APIRouter
from app.api.v1 import auth

api_router = APIRouter()

# Include authentication router
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Placeholder endpoints - will be implemented in subsequent tasks
@api_router.get("/")
async def api_root():
    """API v1 root endpoint."""
    return {"message": "VitaCheckLabs API v1"}

# TODO: Add routers for:
# - lab_tests (VIT-25)
# - reports (VIT-26)
# - company (VIT-27)