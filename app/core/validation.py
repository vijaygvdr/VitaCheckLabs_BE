"""
Enhanced validation utilities and security checks for VitaCheckLabs API.

This module provides comprehensive input validation, sanitization,
and security checks to protect against various attack vectors.
"""

import re
import html
import bleach
from typing import Any, Dict, List, Optional, Union
from email_validator import validate_email, EmailNotValidError
from pydantic import validator
from datetime import datetime, date

from app.core.exceptions import (
    ValidationError,
    InvalidEmailError,
    InvalidPhoneError,
    PasswordValidationError,
    InvalidInputError,
    SecurityError
)


# Security patterns
SUSPICIOUS_PATTERNS = [
    r'<script[^>]*>.*?</script>',  # Script tags
    r'javascript:',  # JavaScript protocol
    r'on\w+\s*=',  # Event handlers
    r'<iframe[^>]*>.*?</iframe>',  # Iframe tags
    r'<object[^>]*>.*?</object>',  # Object tags
    r'<embed[^>]*>.*?</embed>',  # Embed tags
    r'<link[^>]*>',  # Link tags
    r'<meta[^>]*>',  # Meta tags
    r'<style[^>]*>.*?</style>',  # Style tags
    r'<\?php.*?\?>',  # PHP tags
    r'<%.*?%>',  # ASP tags
    r'\${.*?}',  # Expression language
    r'#{.*?}',  # Expression language
]

SQL_INJECTION_PATTERNS = [
    r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|UNION|SCRIPT)\b)',
    r'(\b(OR|AND)\s+\d+\s*=\s*\d+)',
    r'(\b(OR|AND)\s+[\'"`]\w+[\'"`]\s*=\s*[\'"`]\w+[\'"`])',
    r'([\'"`];\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|TRUNCATE|EXEC|UNION))',
    r'(\b(BENCHMARK|SLEEP|WAITFOR)\s*\()',
    r'(INFORMATION_SCHEMA|SYSOBJECTS|SYSCOLUMNS)',
]

# Allowed tags for sanitization
ALLOWED_HTML_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'i', 'b',
    'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'code', 'pre'
]

ALLOWED_HTML_ATTRIBUTES = {
    '*': ['class'],
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}


class SecurityValidator:
    """Security validation utilities."""
    
    @staticmethod
    def check_for_xss(value: str) -> None:
        """Check for potential XSS attacks."""
        if not isinstance(value, str):
            return
        
        for pattern in SUSPICIOUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise SecurityError(
                    message="Potentially malicious content detected",
                    violation_type="xss_attempt",
                    details={"pattern": pattern, "value": value[:100]}
                )
    
    @staticmethod
    def check_for_sql_injection(value: str) -> None:
        """Check for potential SQL injection attacks."""
        if not isinstance(value, str):
            return
        
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                raise SecurityError(
                    message="Potentially malicious SQL detected",
                    violation_type="sql_injection_attempt",
                    details={"pattern": pattern, "value": value[:100]}
                )
    
    @staticmethod
    def sanitize_html(value: str) -> str:
        """Sanitize HTML content to prevent XSS."""
        if not isinstance(value, str):
            return value
        
        return bleach.clean(
            value,
            tags=ALLOWED_HTML_TAGS,
            attributes=ALLOWED_HTML_ATTRIBUTES,
            strip=True
        )
    
    @staticmethod
    def escape_html(value: str) -> str:
        """Escape HTML characters."""
        if not isinstance(value, str):
            return value
        
        return html.escape(value, quote=True)
    
    @staticmethod
    def validate_safe_string(value: str, field_name: str = "field") -> str:
        """Validate that a string is safe from common attacks."""
        if not isinstance(value, str):
            return value
        
        # Check for XSS and SQL injection
        SecurityValidator.check_for_xss(value)
        SecurityValidator.check_for_sql_injection(value)
        
        # Additional checks for suspicious patterns
        if len(value) > 10000:  # Prevent extremely long inputs
            raise InvalidInputError(
                message="Input too long",
                field=field_name,
                details={"max_length": 10000, "actual_length": len(value)}
            )
        
        # Check for null bytes
        if '\x00' in value:
            raise InvalidInputError(
                message="Null bytes not allowed",
                field=field_name
            )
        
        return value.strip()


class DataValidator:
    """Data validation utilities."""
    
    @staticmethod
    def validate_email_address(email: str) -> str:
        """Validate email address format."""
        if not email:
            raise InvalidEmailError("Email address is required")
        
        try:
            # Use email-validator library for robust validation
            validated_email = validate_email(email)
            return validated_email.email
        except EmailNotValidError as e:
            raise InvalidEmailError(str(e))
    
    @staticmethod
    def validate_phone_number(phone: str) -> str:
        """Validate phone number format."""
        if not phone:
            return phone
        
        # Remove common formatting characters
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        
        # Check for valid patterns
        patterns = [
            r'^\+\d{1,3}\d{10}$',  # International format
            r'^\d{10}$',  # 10 digits
            r'^\+91\d{10}$',  # India specific
        ]
        
        for pattern in patterns:
            if re.match(pattern, cleaned_phone):
                return cleaned_phone
        
        raise InvalidPhoneError(phone)
    
    @staticmethod
    def validate_password_strength(password: str) -> str:
        """Validate password meets security requirements."""
        if not password:
            raise PasswordValidationError("Password is required")
        
        errors = []
        
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long")
        
        if len(password) > 128:
            errors.append("Password must be less than 128 characters")
        
        if not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        if not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        if not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("Password must contain at least one special character")
        
        if errors:
            raise PasswordValidationError("; ".join(errors))
        
        return password
    
    @staticmethod
    def validate_name(name: str, field_name: str = "name") -> str:
        """Validate name fields."""
        if not name:
            raise ValidationError(
                message=f"{field_name} is required",
                field=field_name
            )
        
        # Security check
        name = SecurityValidator.validate_safe_string(name, field_name)
        
        # Name-specific validation
        if len(name) < 2:
            raise ValidationError(
                message=f"{field_name} must be at least 2 characters",
                field=field_name,
                value=name
            )
        
        if len(name) > 100:
            raise ValidationError(
                message=f"{field_name} must be less than 100 characters",
                field=field_name,
                value=name
            )
        
        # Check for valid name characters
        if not re.match(r'^[a-zA-Z\s\-\.\']+$', name):
            raise ValidationError(
                message=f"{field_name} contains invalid characters",
                field=field_name,
                value=name
            )
        
        return name.strip()
    
    @staticmethod
    def validate_text_content(content: str, field_name: str = "content", max_length: int = 5000) -> str:
        """Validate text content fields."""
        if not content:
            return content
        
        # Security check
        content = SecurityValidator.validate_safe_string(content, field_name)
        
        if len(content) > max_length:
            raise ValidationError(
                message=f"{field_name} must be less than {max_length} characters",
                field=field_name,
                value=f"{content[:50]}..."
            )
        
        return content.strip()
    
    @staticmethod
    def validate_id_field(value: Any, field_name: str = "id") -> int:
        """Validate ID fields."""
        if value is None:
            raise ValidationError(
                message=f"{field_name} is required",
                field=field_name
            )
        
        try:
            id_value = int(value)
            if id_value <= 0:
                raise ValidationError(
                    message=f"{field_name} must be a positive integer",
                    field=field_name,
                    value=value
                )
            return id_value
        except (ValueError, TypeError):
            raise ValidationError(
                message=f"{field_name} must be a valid integer",
                field=field_name,
                value=value
            )
    
    @staticmethod
    def validate_date_field(value: Any, field_name: str = "date") -> Optional[date]:
        """Validate date fields."""
        if value is None:
            return None
        
        if isinstance(value, date):
            return value
        
        if isinstance(value, datetime):
            return value.date()
        
        if isinstance(value, str):
            try:
                parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                return parsed_date
            except ValueError:
                raise ValidationError(
                    message=f"{field_name} must be a valid date",
                    field=field_name,
                    value=value
                )
        
        raise ValidationError(
            message=f"{field_name} must be a valid date",
            field=field_name,
            value=value
        )
    
    @staticmethod
    def validate_datetime_field(value: Any, field_name: str = "datetime") -> Optional[datetime]:
        """Validate datetime fields."""
        if value is None:
            return None
        
        if isinstance(value, datetime):
            return value
        
        if isinstance(value, str):
            try:
                parsed_datetime = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return parsed_datetime
            except ValueError:
                raise ValidationError(
                    message=f"{field_name} must be a valid datetime",
                    field=field_name,
                    value=value
                )
        
        raise ValidationError(
            message=f"{field_name} must be a valid datetime",
            field=field_name,
            value=value
        )


# Custom Pydantic validators for common use cases
def validate_email_field(cls, v):
    """Pydantic validator for email fields."""
    if v:
        return DataValidator.validate_email_address(v)
    return v


def validate_phone_field(cls, v):
    """Pydantic validator for phone fields."""
    if v:
        return DataValidator.validate_phone_number(v)
    return v


def validate_name_field(cls, v, field_name: str = None):
    """Pydantic validator for name fields."""
    if v:
        field_name = field_name or "name"
        return DataValidator.validate_name(v, field_name)
    return v


def validate_password_field(cls, v):
    """Pydantic validator for password fields."""
    if v:
        return DataValidator.validate_password_strength(v)
    return v


def validate_safe_string_field(cls, v, field_name: str = None):
    """Pydantic validator for safe string fields."""
    if v:
        field_name = field_name or "field"
        return SecurityValidator.validate_safe_string(v, field_name)
    return v


def validate_text_content_field(cls, v, field_name: str = None, max_length: int = 5000):
    """Pydantic validator for text content fields."""
    if v:
        field_name = field_name or "content"
        return DataValidator.validate_text_content(v, field_name, max_length)
    return v


# File validation utilities
class FileValidator:
    """File validation utilities."""
    
    ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}
    ALLOWED_DOCUMENT_TYPES = {'application/pdf', 'text/plain'}
    ALLOWED_REPORT_TYPES = ALLOWED_IMAGE_TYPES | ALLOWED_DOCUMENT_TYPES
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    @staticmethod
    def validate_file_type(content_type: str, allowed_types: set) -> None:
        """Validate file content type."""
        if content_type not in allowed_types:
            from app.core.exceptions import InvalidFileTypeError
            raise InvalidFileTypeError(
                file_type=content_type,
                allowed_types=list(allowed_types)
            )
    
    @staticmethod
    def validate_file_size(file_size: int, max_size: int = None) -> None:
        """Validate file size."""
        max_size = max_size or FileValidator.MAX_FILE_SIZE
        if file_size > max_size:
            from app.core.exceptions import FileSizeExceededError
            raise FileSizeExceededError(
                file_size=file_size,
                max_size=max_size
            )
    
    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate and sanitize filename."""
        if not filename:
            raise ValidationError("Filename is required", field="filename")
        
        # Remove path components and dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', filename)
        sanitized = sanitized.replace('..', '')
        
        if not sanitized:
            raise ValidationError("Invalid filename", field="filename", value=filename)
        
        return sanitized[:255]  # Limit length