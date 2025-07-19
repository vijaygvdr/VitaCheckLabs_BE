"""
Custom exception classes for VitaCheckLabs API.

This module defines custom exceptions for various error conditions
that can occur in the application, providing structured error handling
with appropriate HTTP status codes and error messages.
"""

from typing import Any, Dict, Optional, Union
from fastapi import HTTPException, status


class VitaCheckLabsException(Exception):
    """Base exception for all VitaCheckLabs custom exceptions."""
    
    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.error_code = error_code or self.__class__.__name__
        super().__init__(self.message)


# Authentication and Authorization Exceptions
class AuthenticationError(VitaCheckLabsException):
    """Exception raised for authentication failures."""
    
    def __init__(
        self,
        message: str = "Authentication failed",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
            error_code="AUTHENTICATION_FAILED"
        )


class AuthorizationError(VitaCheckLabsException):
    """Exception raised for authorization failures."""
    
    def __init__(
        self,
        message: str = "Insufficient permissions",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
            error_code="AUTHORIZATION_FAILED"
        )


class InvalidTokenError(AuthenticationError):
    """Exception raised for invalid or expired tokens."""
    
    def __init__(
        self,
        message: str = "Invalid or expired token",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message=message, details=details)
        self.error_code = "INVALID_TOKEN"


class UserNotFoundError(VitaCheckLabsException):
    """Exception raised when a user is not found."""
    
    def __init__(
        self,
        message: str = "User not found",
        user_id: Optional[Union[int, str]] = None
    ):
        details = {"user_id": user_id} if user_id else None
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            error_code="USER_NOT_FOUND"
        )


class UserInactiveError(AuthenticationError):
    """Exception raised when user account is inactive."""
    
    def __init__(
        self,
        message: str = "User account is inactive",
        user_id: Optional[Union[int, str]] = None
    ):
        details = {"user_id": user_id} if user_id else None
        super().__init__(message=message, details=details)
        self.error_code = "USER_INACTIVE"


# Validation Exceptions
class ValidationError(VitaCheckLabsException):
    """Exception raised for validation failures."""
    
    def __init__(
        self,
        message: str = "Validation failed",
        field: Optional[str] = None,
        value: Optional[Any] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        validation_details = details or {}
        if field:
            validation_details["field"] = field
        if value is not None:
            validation_details["value"] = str(value)  # Convert to string for safety
        
        super().__init__(
            message=message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=validation_details,
            error_code="VALIDATION_ERROR"
        )


class InvalidEmailError(ValidationError):
    """Exception raised for invalid email addresses."""
    
    def __init__(self, email: str):
        super().__init__(
            message=f"Invalid email address: {email}",
            field="email",
            value=email
        )
        self.error_code = "INVALID_EMAIL"


class InvalidPhoneError(ValidationError):
    """Exception raised for invalid phone numbers."""
    
    def __init__(self, phone: str):
        super().__init__(
            message=f"Invalid phone number: {phone}",
            field="phone",
            value=phone
        )
        self.error_code = "INVALID_PHONE"


class PasswordValidationError(ValidationError):
    """Exception raised for password validation failures."""
    
    def __init__(self, message: str = "Password does not meet requirements"):
        super().__init__(
            message=message,
            field="password"
        )
        self.error_code = "INVALID_PASSWORD"


# Resource Exceptions
class ResourceNotFoundError(VitaCheckLabsException):
    """Exception raised when a resource is not found."""
    
    def __init__(
        self,
        resource_type: str,
        resource_id: Optional[Union[int, str]] = None,
        message: Optional[str] = None
    ):
        if not message:
            if resource_id:
                message = f"{resource_type} with ID '{resource_id}' not found"
            else:
                message = f"{resource_type} not found"
        
        details = {
            "resource_type": resource_type,
            "resource_id": resource_id
        } if resource_id else {"resource_type": resource_type}
        
        super().__init__(
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
            error_code="RESOURCE_NOT_FOUND"
        )


class ResourceAlreadyExistsError(VitaCheckLabsException):
    """Exception raised when trying to create a resource that already exists."""
    
    def __init__(
        self,
        resource_type: str,
        identifier: Optional[str] = None,
        message: Optional[str] = None
    ):
        if not message:
            if identifier:
                message = f"{resource_type} with identifier '{identifier}' already exists"
            else:
                message = f"{resource_type} already exists"
        
        details = {
            "resource_type": resource_type,
            "identifier": identifier
        } if identifier else {"resource_type": resource_type}
        
        super().__init__(
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
            error_code="RESOURCE_ALREADY_EXISTS"
        )


class BusinessLogicError(VitaCheckLabsException):
    """Exception raised for business logic violations."""
    
    def __init__(
        self,
        message: str,
        business_rule: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        business_details = details or {}
        if business_rule:
            business_details["business_rule"] = business_rule
        
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=business_details,
            error_code="BUSINESS_LOGIC_ERROR"
        )


# File and Upload Exceptions
class FileUploadError(VitaCheckLabsException):
    """Exception raised for file upload failures."""
    
    def __init__(
        self,
        message: str = "File upload failed",
        filename: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        upload_details = details or {}
        if filename:
            upload_details["filename"] = filename
        
        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=upload_details,
            error_code="FILE_UPLOAD_ERROR"
        )


class InvalidFileTypeError(FileUploadError):
    """Exception raised for invalid file types."""
    
    def __init__(
        self,
        file_type: str,
        allowed_types: Optional[list] = None,
        filename: Optional[str] = None
    ):
        message = f"Invalid file type: {file_type}"
        details = {"file_type": file_type}
        
        if allowed_types:
            message += f". Allowed types: {', '.join(allowed_types)}"
            details["allowed_types"] = allowed_types
        
        super().__init__(
            message=message,
            filename=filename,
            details=details
        )
        self.error_code = "INVALID_FILE_TYPE"


class FileSizeExceededError(FileUploadError):
    """Exception raised when file size exceeds limits."""
    
    def __init__(
        self,
        file_size: int,
        max_size: int,
        filename: Optional[str] = None
    ):
        message = f"File size ({file_size} bytes) exceeds maximum allowed size ({max_size} bytes)"
        details = {
            "file_size": file_size,
            "max_size": max_size
        }
        
        super().__init__(
            message=message,
            filename=filename,
            details=details
        )
        self.error_code = "FILE_SIZE_EXCEEDED"


# Database Exceptions
class DatabaseError(VitaCheckLabsException):
    """Exception raised for database operation failures."""
    
    def __init__(
        self,
        message: str = "Database operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        db_details = details or {}
        if operation:
            db_details["operation"] = operation
        
        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=db_details,
            error_code="DATABASE_ERROR"
        )


class DatabaseConnectionError(DatabaseError):
    """Exception raised for database connection failures."""
    
    def __init__(self, message: str = "Database connection failed"):
        super().__init__(message=message, operation="connect")
        self.error_code = "DATABASE_CONNECTION_ERROR"


# Rate Limiting Exceptions
class RateLimitExceededError(VitaCheckLabsException):
    """Exception raised when rate limit is exceeded."""
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        limit: Optional[int] = None,
        window: Optional[int] = None,
        retry_after: Optional[int] = None
    ):
        details = {}
        if limit:
            details["limit"] = limit
        if window:
            details["window_seconds"] = window
        if retry_after:
            details["retry_after_seconds"] = retry_after
        
        super().__init__(
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
            error_code="RATE_LIMIT_EXCEEDED"
        )


# Security Exceptions
class SecurityError(VitaCheckLabsException):
    """Exception raised for security violations."""
    
    def __init__(
        self,
        message: str = "Security violation detected",
        violation_type: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        security_details = details or {}
        if violation_type:
            security_details["violation_type"] = violation_type
        
        super().__init__(
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=security_details,
            error_code="SECURITY_ERROR"
        )


class InvalidInputError(SecurityError):
    """Exception raised for potentially malicious input."""
    
    def __init__(
        self,
        message: str = "Invalid input detected",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        security_details = details or {}
        if field:
            security_details["field"] = field
        
        super().__init__(
            message=message,
            violation_type="invalid_input",
            details=security_details
        )
        self.error_code = "INVALID_INPUT"


# External Service Exceptions
class ExternalServiceError(VitaCheckLabsException):
    """Exception raised for external service failures."""
    
    def __init__(
        self,
        service_name: str,
        message: str = "External service error",
        status_code: int = status.HTTP_503_SERVICE_UNAVAILABLE,
        details: Optional[Dict[str, Any]] = None
    ):
        service_details = details or {}
        service_details["service"] = service_name
        
        super().__init__(
            message=f"{service_name}: {message}",
            status_code=status_code,
            details=service_details,
            error_code="EXTERNAL_SERVICE_ERROR"
        )


class S3ServiceError(ExternalServiceError):
    """Exception raised for S3 service failures."""
    
    def __init__(
        self,
        message: str = "S3 operation failed",
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        s3_details = details or {}
        if operation:
            s3_details["operation"] = operation
        
        super().__init__(
            service_name="S3",
            message=message,
            details=s3_details
        )
        self.error_code = "S3_SERVICE_ERROR"


# Utility function to convert custom exceptions to HTTPException
def to_http_exception(exc: VitaCheckLabsException) -> HTTPException:
    """
    Convert a custom VitaCheckLabs exception to FastAPI HTTPException.
    
    Args:
        exc: Custom exception to convert
        
    Returns:
        HTTPException with structured error response
    """
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )