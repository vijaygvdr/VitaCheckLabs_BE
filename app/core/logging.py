"""
Comprehensive logging system for VitaCheckLabs API.

This module provides structured logging with different levels,
request tracking, and integration with monitoring systems.
"""

import logging
import json
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Union
from functools import wraps
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        
        if hasattr(record, "path"):
            log_data["path"] = record.path
        
        if hasattr(record, "method"):
            log_data["method"] = record.method
        
        if hasattr(record, "status_code"):
            log_data["status_code"] = record.status_code
        
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        
        if hasattr(record, "error_code"):
            log_data["error_code"] = record.error_code
        
        if hasattr(record, "details"):
            log_data["details"] = record.details
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, default=str)


class SecurityLogFilter(logging.Filter):
    """Filter for security-related logs."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter security-related log records."""
        security_keywords = [
            "authentication", "authorization", "security", "xss", "sql injection",
            "rate limit", "suspicious", "malicious", "invalid token", "unauthorized"
        ]
        
        message = record.getMessage().lower()
        return any(keyword in message for keyword in security_keywords)


def setup_logging():
    """Set up logging configuration."""
    # Create formatters
    structured_formatter = StructuredFormatter()
    simple_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG)
    
    # Remove default handlers
    root_logger.handlers.clear()
    
    # Console handler with structured format
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(structured_formatter)
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    
    # Application logger
    app_logger = logging.getLogger("vitachecklabs")
    app_logger.setLevel(logging.DEBUG)
    
    # Security logger with filter
    security_logger = logging.getLogger("vitachecklabs.security")
    security_handler = logging.StreamHandler()
    security_handler.setFormatter(structured_formatter)
    security_handler.addFilter(SecurityLogFilter())
    security_logger.addHandler(security_handler)
    security_logger.setLevel(logging.WARNING)
    
    # Disable some noisy loggers in production
    if settings.ENVIRONMENT == "production":
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses."""
    
    def __init__(self, app):
        super().__init__(app)
        self.logger = logging.getLogger("vitachecklabs.requests")
    
    async def dispatch(self, request: Request, call_next):
        """Log request and response details."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Start timing
        start_time = time.time()
        
        # Get user info if available
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.core.security import verify_token
                token = auth_header[7:]
                payload = verify_token(token, token_type="access")
                if payload:
                    user_id = payload.get("sub")
            except Exception:
                pass
        
        # Log request
        self.logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "query_params": dict(request.query_params),
                "user_id": user_id,
                "user_agent": request.headers.get("user-agent"),
                "client_ip": self._get_client_ip(request),
                "content_type": request.headers.get("content-type"),
                "content_length": request.headers.get("content-length")
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Log response
            log_level = logging.INFO
            if response.status_code >= 400:
                log_level = logging.WARNING
            if response.status_code >= 500:
                log_level = logging.ERROR
            
            self.logger.log(
                log_level,
                f"Request completed: {request.method} {request.url.path} -> {response.status_code}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "response_size": response.headers.get("content-length")
                }
            )
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as exc:
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Log error
            self.logger.error(
                f"Request failed: {request.method} {request.url.path}",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": str(request.url.path),
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__
                },
                exc_info=True
            )
            
            raise
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        if request.client:
            return request.client.host
        
        return "unknown"


# Logging decorators
def log_function_call(logger: Optional[logging.Logger] = None):
    """Decorator to log function calls."""
    def decorator(func):
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(f"vitachecklabs.{func.__module__}")
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(
                f"Function called: {func.__name__}",
                extra={
                    "function": func.__name__,
                    "module": func.__module__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
            )
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                logger.debug(
                    f"Function completed: {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "duration_ms": duration_ms,
                        "success": True
                    }
                )
                return result
                
            except Exception as exc:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                logger.error(
                    f"Function failed: {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "success": False
                    },
                    exc_info=True
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            logger.debug(
                f"Function called: {func.__name__}",
                extra={
                    "function": func.__name__,
                    "module": func.__module__,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys())
                }
            )
            
            try:
                result = func(*args, **kwargs)
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                logger.debug(
                    f"Function completed: {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "duration_ms": duration_ms,
                        "success": True
                    }
                )
                return result
                
            except Exception as exc:
                duration_ms = round((time.time() - start_time) * 1000, 2)
                
                logger.error(
                    f"Function failed: {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "duration_ms": duration_ms,
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                        "success": False
                    },
                    exc_info=True
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


# Specialized loggers
class SecurityLogger:
    """Logger for security events."""
    
    def __init__(self):
        self.logger = logging.getLogger("vitachecklabs.security")
    
    def log_authentication_attempt(
        self,
        email: str,
        success: bool,
        ip_address: str,
        user_agent: str = None,
        details: Dict[str, Any] = None
    ):
        """Log authentication attempts."""
        level = logging.INFO if success else logging.WARNING
        message = f"Authentication {'successful' if success else 'failed'} for {email}"
        
        self.logger.log(
            level,
            message,
            extra={
                "event_type": "authentication",
                "email": email,
                "success": success,
                "client_ip": ip_address,
                "user_agent": user_agent,
                "details": details or {}
            }
        )
    
    def log_authorization_failure(
        self,
        user_id: str,
        resource: str,
        action: str,
        ip_address: str,
        details: Dict[str, Any] = None
    ):
        """Log authorization failures."""
        self.logger.warning(
            f"Authorization failed for user {user_id} on {resource}",
            extra={
                "event_type": "authorization_failure",
                "user_id": user_id,
                "resource": resource,
                "action": action,
                "client_ip": ip_address,
                "details": details or {}
            }
        )
    
    def log_security_violation(
        self,
        violation_type: str,
        message: str,
        ip_address: str,
        user_id: str = None,
        details: Dict[str, Any] = None
    ):
        """Log security violations."""
        self.logger.error(
            f"Security violation detected: {violation_type} - {message}",
            extra={
                "event_type": "security_violation",
                "violation_type": violation_type,
                "client_ip": ip_address,
                "user_id": user_id,
                "details": details or {}
            }
        )
    
    def log_rate_limit_exceeded(
        self,
        client_id: str,
        endpoint: str,
        limit: int,
        window: int,
        details: Dict[str, Any] = None
    ):
        """Log rate limit violations."""
        self.logger.warning(
            f"Rate limit exceeded for {client_id} on {endpoint}",
            extra={
                "event_type": "rate_limit_exceeded",
                "client_id": client_id,
                "endpoint": endpoint,
                "limit": limit,
                "window_seconds": window,
                "details": details or {}
            }
        )


class DatabaseLogger:
    """Logger for database operations."""
    
    def __init__(self):
        self.logger = logging.getLogger("vitachecklabs.database")
    
    def log_query_slow(
        self,
        query: str,
        duration_ms: float,
        threshold_ms: float = 1000,
        details: Dict[str, Any] = None
    ):
        """Log slow database queries."""
        if duration_ms > threshold_ms:
            self.logger.warning(
                f"Slow query detected: {duration_ms}ms",
                extra={
                    "event_type": "slow_query",
                    "query": query[:500],  # Truncate long queries
                    "duration_ms": duration_ms,
                    "threshold_ms": threshold_ms,
                    "details": details or {}
                }
            )
    
    def log_connection_error(
        self,
        error: str,
        details: Dict[str, Any] = None
    ):
        """Log database connection errors."""
        self.logger.error(
            f"Database connection error: {error}",
            extra={
                "event_type": "db_connection_error",
                "error": error,
                "details": details or {}
            }
        )


# Import asyncio after other imports to avoid circular imports
import asyncio

# Global logger instances
security_logger = SecurityLogger()
db_logger = DatabaseLogger()