"""
Rate limiting middleware for VitaCheckLabs API.

This module provides rate limiting functionality to protect against
abuse and ensure fair usage of API resources.
"""

import time
import hashlib
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.exceptions import RateLimitExceededError
from app.core.error_handlers import create_error_response


class InMemoryRateLimiter:
    """In-memory rate limiter using sliding window algorithm."""
    
    def __init__(self):
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.last_cleanup = time.time()
        self.cleanup_interval = 300  # 5 minutes
    
    def is_allowed(
        self,
        key: str,
        limit: int,
        window: int,
        current_time: Optional[float] = None
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Rate limit key (usually IP or user ID)
            limit: Maximum requests allowed
            window: Time window in seconds
            current_time: Current timestamp (for testing)
        
        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        current_time = current_time or time.time()
        window_start = current_time - window
        
        # Clean old requests
        request_times = self.requests[key]
        while request_times and request_times[0] < window_start:
            request_times.popleft()
        
        # Check if under limit
        current_count = len(request_times)
        is_allowed = current_count < limit
        
        if is_allowed:
            request_times.append(current_time)
        
        # Calculate rate limit info
        reset_time = int(current_time + window) if request_times else int(current_time)
        remaining = max(0, limit - current_count - (1 if is_allowed else 0))
        
        rate_limit_info = {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": window if not is_allowed else 0
        }
        
        # Periodic cleanup
        if current_time - self.last_cleanup > self.cleanup_interval:
            self._cleanup_old_entries(current_time)
            self.last_cleanup = current_time
        
        return is_allowed, rate_limit_info
    
    def _cleanup_old_entries(self, current_time: float):
        """Clean up old entries to prevent memory leaks."""
        keys_to_remove = []
        for key, request_times in self.requests.items():
            # Remove entries older than 1 hour
            cutoff_time = current_time - 3600
            while request_times and request_times[0] < cutoff_time:
                request_times.popleft()
            
            # Remove empty entries
            if not request_times:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.requests[key]


class RateLimitConfig:
    """Rate limit configuration."""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        requests_per_day: int = 10000,
        burst_size: int = 10,
        burst_window: int = 10
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day
        self.burst_size = burst_size
        self.burst_window = burst_window


# Predefined rate limit configurations
RATE_LIMIT_CONFIGS = {
    "default": RateLimitConfig(),
    "strict": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=500,
        requests_per_day=5000,
        burst_size=5,
        burst_window=10
    ),
    "relaxed": RateLimitConfig(
        requests_per_minute=120,
        requests_per_hour=2000,
        requests_per_day=20000,
        burst_size=20,
        burst_window=10
    ),
    "auth": RateLimitConfig(
        requests_per_minute=10,
        requests_per_hour=100,
        requests_per_day=500,
        burst_size=3,
        burst_window=60
    ),
    "public": RateLimitConfig(
        requests_per_minute=30,
        requests_per_hour=300,
        requests_per_day=1000,
        burst_size=5,
        burst_window=10
    )
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled
        self.limiter = InMemoryRateLimiter()
        
        # Route-specific configurations
        self.route_configs = {
            "/api/v1/auth/login": "auth",
            "/api/v1/auth/register": "auth",
            "/api/v1/auth/refresh": "auth",
            "/api/v1/company/contact": "public",
            "/api/v1/company/info": "public",
            "/api/v1/company/services": "public",
            "/api/v1/lab-tests": "public",
        }
    
    async def dispatch(self, request: Request, call_next):
        """Process rate limiting for requests."""
        if not self.enabled:
            response = await call_next(request)
            return response
        
        # Get client identifier
        client_id = self._get_client_id(request)
        
        # Get rate limit configuration
        config = self._get_rate_limit_config(request)
        
        # Check multiple rate limits
        current_time = time.time()
        
        # Check burst limit (most restrictive)
        burst_allowed, burst_info = self.limiter.is_allowed(
            f"{client_id}:burst",
            config.burst_size,
            config.burst_window,
            current_time
        )
        
        if not burst_allowed:
            return self._create_rate_limit_response(
                request, burst_info, "Burst rate limit exceeded"
            )
        
        # Check per-minute limit
        minute_allowed, minute_info = self.limiter.is_allowed(
            f"{client_id}:minute",
            config.requests_per_minute,
            60,
            current_time
        )
        
        if not minute_allowed:
            return self._create_rate_limit_response(
                request, minute_info, "Rate limit exceeded"
            )
        
        # Check per-hour limit
        hour_allowed, hour_info = self.limiter.is_allowed(
            f"{client_id}:hour",
            config.requests_per_hour,
            3600,
            current_time
        )
        
        if not hour_allowed:
            return self._create_rate_limit_response(
                request, hour_info, "Hourly rate limit exceeded"
            )
        
        # Check per-day limit
        day_allowed, day_info = self.limiter.is_allowed(
            f"{client_id}:day",
            config.requests_per_day,
            86400,
            current_time
        )
        
        if not day_allowed:
            return self._create_rate_limit_response(
                request, day_info, "Daily rate limit exceeded"
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        self._add_rate_limit_headers(response, minute_info)
        
        return response
    
    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get user ID from token if available
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.core.security import verify_token
                token = auth_header[7:]
                payload = verify_token(token, token_type="access")
                if payload and payload.get("sub"):
                    return f"user:{payload['sub']}"
            except Exception:
                pass
        
        # Fall back to IP address
        client_ip = self._get_client_ip(request)
        return f"ip:{client_ip}"
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address."""
        # Check for forwarded headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fall back to client host
        if request.client:
            return request.client.host
        
        return "unknown"
    
    def _get_rate_limit_config(self, request: Request) -> RateLimitConfig:
        """Get rate limit configuration for request."""
        path = request.url.path
        
        # Check for exact path match
        if path in self.route_configs:
            config_name = self.route_configs[path]
            return RATE_LIMIT_CONFIGS[config_name]
        
        # Check for prefix matches
        for route_path, config_name in self.route_configs.items():
            if path.startswith(route_path):
                return RATE_LIMIT_CONFIGS[config_name]
        
        # Default configuration
        return RATE_LIMIT_CONFIGS["default"]
    
    def _create_rate_limit_response(
        self,
        request: Request,
        rate_limit_info: Dict[str, int],
        message: str
    ) -> JSONResponse:
        """Create rate limit exceeded response."""
        return create_error_response(
            request=request,
            error_code="RATE_LIMIT_EXCEEDED",
            message=message,
            status_code=429,
            details={
                "limit": rate_limit_info["limit"],
                "retry_after": rate_limit_info["retry_after"]
            }
        )
    
    def _add_rate_limit_headers(self, response: Response, rate_limit_info: Dict[str, int]):
        """Add rate limit headers to response."""
        response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_limit_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset"])


# Decorator for endpoint-specific rate limiting
def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_size: int = 10
):
    """
    Decorator for endpoint-specific rate limiting.
    
    Args:
        requests_per_minute: Requests allowed per minute
        requests_per_hour: Requests allowed per hour
        burst_size: Burst requests allowed
    """
    def decorator(func):
        # Store rate limit config in function metadata
        func._rate_limit_config = RateLimitConfig(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_size=burst_size
        )
        return func
    return decorator


# Helper function to check rate limits manually
def check_rate_limit(
    client_id: str,
    config: RateLimitConfig,
    limiter: InMemoryRateLimiter = None
) -> Tuple[bool, Dict[str, int]]:
    """
    Manual rate limit check.
    
    Args:
        client_id: Client identifier
        config: Rate limit configuration
        limiter: Rate limiter instance
    
    Returns:
        Tuple of (is_allowed, rate_limit_info)
    """
    if limiter is None:
        limiter = InMemoryRateLimiter()
    
    current_time = time.time()
    
    # Check per-minute limit (most commonly used)
    return limiter.is_allowed(
        f"{client_id}:minute",
        config.requests_per_minute,
        60,
        current_time
    )