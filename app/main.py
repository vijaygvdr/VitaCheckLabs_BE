from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError

from app.core.config import settings
from app.api.v1.api import api_router
from app.core.exceptions import VitaCheckLabsException
from app.core.error_handlers import (
    custom_exception_handler,
    http_exception_handler,
    starlette_http_exception_handler,
    validation_exception_handler,
    pydantic_validation_exception_handler,
    sqlalchemy_exception_handler,
    generic_exception_handler
)
from app.core.rate_limiting import RateLimitMiddleware
from app.core.logging import setup_logging, RequestLoggingMiddleware

# Set up logging first
setup_logging()

# Create app instance - need to be importable for tests
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="VitaCheckLabs API for lab tests, reports, and company information with enhanced error handling and validation",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc"
)

# Add exception handlers
app.add_exception_handler(VitaCheckLabsException, custom_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(PydanticValidationError, pydantic_validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Add middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware, enabled=settings.ENVIRONMENT != "development")

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
    """Enhanced health check endpoint with detailed component status."""
    import logging
    from datetime import datetime
    from app.core.error_handlers import create_health_check_error
    
    logger = logging.getLogger("vitachecklabs.health")
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "components": {}
    }
    
    overall_healthy = True
    
    # Check database health
    try:
        from app.database import get_db
        next(get_db())  # Try to get a database connection
        health_status["components"]["database"] = {
            "status": "healthy",
            "details": {"connection": "ok"}
        }
        logger.debug("Database health check passed")
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        health_status["components"]["database"] = create_health_check_error(
            "database", 
            f"Database connection failed: {str(e)}"
        )
        overall_healthy = False
    
    # Check S3 health (if available)
    try:
        from app.services.s3_service import S3Service
        s3_service = S3Service()
        # Simplified S3 check - just verify configuration
        health_status["components"]["s3"] = {
            "status": "healthy",
            "details": {"service": "configured"}
        }
        logger.debug("S3 health check passed")
    except Exception as e:
        logger.warning(f"S3 health check failed: {str(e)}")
        health_status["components"]["s3"] = create_health_check_error(
            "s3",
            f"S3 service unavailable: {str(e)}"
        )
        # S3 failure doesn't make the whole system unhealthy
    
    # Check rate limiter
    try:
        from app.core.rate_limiting import InMemoryRateLimiter
        limiter = InMemoryRateLimiter()
        health_status["components"]["rate_limiter"] = {
            "status": "healthy",
            "details": {"active_limits": len(limiter.requests)}
        }
    except Exception as e:
        logger.error(f"Rate limiter health check failed: {str(e)}")
        health_status["components"]["rate_limiter"] = create_health_check_error(
            "rate_limiter",
            f"Rate limiter error: {str(e)}"
        )
        overall_healthy = False
    
    # Set overall status
    health_status["status"] = "healthy" if overall_healthy else "unhealthy"
    
    if not overall_healthy:
        logger.warning("Health check failed - system unhealthy")
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
    
    return health_status

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)