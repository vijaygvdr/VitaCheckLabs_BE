from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="VitaCheckLabs API for lab tests, reports, and company information",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)

@app.get("/")
async def root():
    """Root endpoint for health check."""
    return {"message": "VitaCheckLabs API is running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    from app.database import check_database_health
    from app.services.s3_service import s3_service
    
    # Check database health
    db_health = await check_database_health()
    
    # Check S3 health
    s3_health = await s3_service.check_bucket_exists()
    
    return {
        "status": "healthy" if db_health["status"] == "healthy" and s3_health else "unhealthy",
        "database": db_health,
        "s3": {"status": "healthy" if s3_health else "unhealthy"}
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)