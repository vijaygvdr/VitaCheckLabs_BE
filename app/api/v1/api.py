from fastapi import APIRouter
from app.api.v1 import auth, lab_tests, reports, company

api_router = APIRouter()

# Include authentication router
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])

# Include lab tests router
api_router.include_router(lab_tests.router, prefix="/lab-tests", tags=["lab-tests"])

# Include reports router
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])

# Include company router
api_router.include_router(company.router, prefix="/company", tags=["company"])

# Placeholder endpoints - will be implemented in subsequent tasks
@api_router.get("/")
async def api_root():
    """API v1 root endpoint."""
    return {"message": "VitaCheckLabs API v1"}