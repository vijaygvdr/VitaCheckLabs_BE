"""
Main API router using DynamoDB services
Replaces SQLAlchemy-based API with DynamoDB version
"""

from fastapi import APIRouter

from app.api.v1 import auth_dynamodb, lab_tests_dynamodb, bookings_dynamodb, reports_s3, company_dynamodb, report_explainer_dynamodb

api_router = APIRouter()

# Include all routers with DynamoDB integration
api_router.include_router(auth_dynamodb.router, prefix="/auth", tags=["authentication"])
api_router.include_router(lab_tests_dynamodb.router, prefix="/lab-tests", tags=["lab-tests"])
api_router.include_router(reports_s3.router, prefix="/reports", tags=["reports"])
api_router.include_router(report_explainer_dynamodb.router, prefix="/report-explainer", tags=["report-explainer"])
api_router.include_router(bookings_dynamodb.router, prefix="/bookings", tags=["bookings"])
api_router.include_router(company_dynamodb.router, prefix="/company", tags=["company"])