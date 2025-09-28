from fastapi import APIRouter
from app.api.v1 import (
    booking_copilot,
    admin,
    lab_tests_dynamodb,
    report_explainer_dynamodb,
    bookings_dynamodb,
    company_dynamodb,
    auth_dynamodb,
    reports_s3
)

api_router = APIRouter()

# Include report explainer router (DynamoDB-based, working)
api_router.include_router(report_explainer_dynamodb.router, prefix="/report-explainer", tags=["report-explainer"])

# Include booking copilot router (DynamoDB-based, working)
api_router.include_router(booking_copilot.router, prefix="/booking-copilot", tags=["booking-copilot"])

# Include lab tests router (DynamoDB-based, working)
api_router.include_router(lab_tests_dynamodb.router, prefix="/lab-tests", tags=["lab-tests"])

# Include lab bookings router (DynamoDB-based, working)
api_router.include_router(bookings_dynamodb.router, prefix="/bookings", tags=["bookings"])

# Include company router (DynamoDB-based, working)
api_router.include_router(company_dynamodb.router, prefix="/company", tags=["company"])

# Include auth router (DynamoDB-based, working)
api_router.include_router(auth_dynamodb.router, prefix="/auth", tags=["auth"])

# Include reports router (DynamoDB and s3 based, working)
api_router.include_router(reports_s3.router, prefix="/reports", tags=["reports"])

# Include admin router (DynamoDB-based, working)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])


# Placeholder endpoints - will be implemented in subsequent tasks
@api_router.get("/")
async def api_root():
    """API v1 root endpoint."""
    return {"message": "VitaCheckLabs API v1"}