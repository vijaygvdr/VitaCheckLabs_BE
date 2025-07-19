"""
Error handlers and response formats for VitaCheckLabs API.

This module provides centralized error handling with standardized
error response formats and comprehensive logging.
"""

import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DatabaseError
from pydantic import ValidationError as PydanticValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import VitaCheckLabsException, DatabaseError as CustomDatabaseError


# Configure logger
logger = logging.getLogger(__name__)


class ErrorResponse:
    """Standardized error response format."""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        request_id: Optional[str] = None,
        path: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.timestamp = timestamp or datetime.utcnow()
        self.request_id = request_id
        self.path = path
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response."""
        response = {
            "error": {
                "code": self.error_code,
                "message": self.message,
                "timestamp": self.timestamp.isoformat(),
            }
        }
        
        if self.details:
            response["error"]["details"] = self.details
        
        if self.request_id:
            response["error"]["request_id"] = self.request_id
        
        if self.path:
            response["error"]["path"] = self.path
        
        return response


def get_request_id(request: Request) -> Optional[str]:
    """Extract request ID from headers or generate one."""
    return request.headers.get("X-Request-ID") or request.headers.get("X-Correlation-ID")


def create_error_response(
    request: Request,
    error_code: str,
    message: str,
    status_code: int,
    details: Optional[Dict[str, Any]] = None
) -> JSONResponse:
    """Create standardized error response."""
    error_response = ErrorResponse(
        error_code=error_code,
        message=message,
        details=details,
        request_id=get_request_id(request),
        path=str(request.url.path)
    )
    
    return JSONResponse(
        status_code=status_code,
        content=error_response.to_dict()
    )


async def custom_exception_handler(request: Request, exc: VitaCheckLabsException) -> JSONResponse:
    """Handle custom VitaCheckLabs exceptions."""
    logger.warning(
        f"Custom exception: {exc.error_code} - {exc.message}",
        extra={
            "error_code": exc.error_code,
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "request_id": get_request_id(request),
            "details": exc.details
        }
    )
    
    return create_error_response(
        request=request,
        error_code=exc.error_code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle FastAPI HTTPException with standardized format."""
    # Extract error details if they exist
    details = None
    error_code = "HTTP_ERROR"
    message = exc.detail
    
    if isinstance(exc.detail, dict):
        error_code = exc.detail.get("error", "HTTP_ERROR")
        message = exc.detail.get("message", "An error occurred")
        details = exc.detail.get("details")
    elif isinstance(exc.detail, str):
        message = exc.detail
    
    logger.warning(
        f"HTTP exception: {exc.status_code} - {message}",
        extra={
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "request_id": get_request_id(request),
            "details": details
        }
    )
    
    return create_error_response(
        request=request,
        error_code=error_code,
        message=message,
        status_code=exc.status_code,
        details=details
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handle Starlette HTTP exceptions."""
    error_code = f"HTTP_{exc.status_code}"
    message = exc.detail or "An error occurred"
    
    logger.warning(
        f"Starlette HTTP exception: {exc.status_code} - {message}",
        extra={
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "request_id": get_request_id(request)
        }
    )
    
    return create_error_response(
        request=request,
        error_code=error_code,
        message=message,
        status_code=exc.status_code
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    validation_errors = []
    
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        validation_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"],
            "input": error.get("input")
        })
    
    details = {
        "validation_errors": validation_errors,
        "error_count": len(validation_errors)
    }
    
    logger.warning(
        f"Validation error: {len(validation_errors)} validation errors",
        extra={
            "path": str(request.url.path),
            "request_id": get_request_id(request),
            "validation_errors": validation_errors
        }
    )
    
    return create_error_response(
        request=request,
        error_code="VALIDATION_ERROR",
        message="Request validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=details
    )


async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
    """Handle Pydantic validation errors from models."""
    validation_errors = []
    
    for error in exc.errors():
        field_path = " -> ".join(str(loc) for loc in error["loc"])
        validation_errors.append({
            "field": field_path,
            "message": error["msg"],
            "type": error["type"]
        })
    
    details = {
        "validation_errors": validation_errors,
        "error_count": len(validation_errors)
    }
    
    logger.warning(
        f"Pydantic validation error: {len(validation_errors)} validation errors",
        extra={
            "path": str(request.url.path),
            "request_id": get_request_id(request),
            "validation_errors": validation_errors
        }
    )
    
    return create_error_response(
        request=request,
        error_code="MODEL_VALIDATION_ERROR",
        message="Data validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details=details
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Handle SQLAlchemy database errors."""
    error_code = "DATABASE_ERROR"
    message = "Database operation failed"
    details = {"error_type": type(exc).__name__}
    
    # Handle specific SQLAlchemy exceptions
    if isinstance(exc, IntegrityError):
        error_code = "DATABASE_INTEGRITY_ERROR"
        message = "Database integrity constraint violated"
        
        # Extract constraint information if available
        if hasattr(exc, 'orig') and exc.orig:
            orig_error = str(exc.orig)
            if "UNIQUE constraint failed" in orig_error:
                message = "Duplicate entry found"
                error_code = "DUPLICATE_ENTRY"
            elif "FOREIGN KEY constraint failed" in orig_error:
                message = "Referenced record not found"
                error_code = "FOREIGN_KEY_ERROR"
            
            details["constraint_error"] = orig_error
    
    elif isinstance(exc, DatabaseError):
        error_code = "DATABASE_CONNECTION_ERROR"
        message = "Database connection failed"
    
    # Log the full exception for debugging
    logger.error(
        f"Database error: {message}",
        extra={
            "error_type": type(exc).__name__,
            "path": str(request.url.path),
            "request_id": get_request_id(request)
        },
        exc_info=True
    )
    
    return create_error_response(
        request=request,
        error_code=error_code,
        message=message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=details
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions."""
    error_id = f"error_{datetime.utcnow().strftime('%Y%m%d_%H%M%S_%f')}"
    
    logger.error(
        f"Unexpected error [{error_id}]: {str(exc)}",
        extra={
            "error_id": error_id,
            "error_type": type(exc).__name__,
            "path": str(request.url.path),
            "request_id": get_request_id(request),
            "traceback": traceback.format_exc()
        },
        exc_info=True
    )
    
    details = {
        "error_id": error_id,
        "error_type": type(exc).__name__
    }
    
    return create_error_response(
        request=request,
        error_code="INTERNAL_SERVER_ERROR",
        message="An unexpected error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        details=details
    )


# Health check error responses
def create_health_check_error(
    component: str,
    error_message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create error response for health check failures."""
    return {
        "status": "unhealthy",
        "component": component,
        "error": error_message,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details or {}
    }


# Utility functions for common error scenarios
def create_not_found_error(resource_type: str, resource_id: Optional[Union[str, int]] = None) -> HTTPException:
    """Create a standardized not found error."""
    if resource_id:
        message = f"{resource_type} with ID '{resource_id}' not found"
    else:
        message = f"{resource_type} not found"
    
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "error": "RESOURCE_NOT_FOUND",
            "message": message,
            "details": {
                "resource_type": resource_type,
                "resource_id": resource_id
            } if resource_id else {"resource_type": resource_type}
        }
    )


def create_duplicate_error(resource_type: str, identifier: str) -> HTTPException:
    """Create a standardized duplicate resource error."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "error": "RESOURCE_ALREADY_EXISTS",
            "message": f"{resource_type} with identifier '{identifier}' already exists",
            "details": {
                "resource_type": resource_type,
                "identifier": identifier
            }
        }
    )


def create_validation_error(field: str, message: str, value: Optional[Any] = None) -> HTTPException:
    """Create a standardized validation error."""
    details = {"field": field}
    if value is not None:
        details["value"] = str(value)
    
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail={
            "error": "VALIDATION_ERROR",
            "message": message,
            "details": details
        }
    )


def create_unauthorized_error(message: str = "Authentication required") -> HTTPException:
    """Create a standardized unauthorized error."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "error": "AUTHENTICATION_REQUIRED",
            "message": message
        },
        headers={"WWW-Authenticate": "Bearer"}
    )


def create_forbidden_error(message: str = "Insufficient permissions") -> HTTPException:
    """Create a standardized forbidden error."""
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "error": "INSUFFICIENT_PERMISSIONS",
            "message": message
        }
    )