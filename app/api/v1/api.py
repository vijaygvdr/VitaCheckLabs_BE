from fastapi import APIRouter

api_router = APIRouter()

# Placeholder endpoints - will be implemented in subsequent tasks
@api_router.get("/")
async def api_root():
    """API v1 root endpoint."""
    return {"message": "VitaCheckLabs API v1"}

# TODO: Add routers for:
# - auth (VIT-24)
# - lab_tests (VIT-25)
# - reports (VIT-26)
# - company (VIT-27)