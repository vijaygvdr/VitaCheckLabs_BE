import pytest
import time
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app
from app.core.exceptions import (
    ValidationError, AuthenticationError, ResourceNotFoundError,
    BusinessLogicError, RateLimitExceededError, SecurityError
)
from app.core.validation import (
    SecurityValidator, DataValidator, FileValidator
)
from app.core.rate_limiting import InMemoryRateLimiter, RateLimitConfig


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_error_handling.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_validation_error(self):
        """Test ValidationError creation and properties."""
        error = ValidationError(
            message="Invalid email format",
            field="email",
            value="invalid-email"
        )
        
        assert error.message == "Invalid email format"
        assert error.status_code == 422
        assert error.error_code == "VALIDATION_ERROR"
        assert error.details["field"] == "email"
        assert error.details["value"] == "invalid-email"
    
    def test_authentication_error(self):
        """Test AuthenticationError creation."""
        error = AuthenticationError("Invalid credentials")
        
        assert error.message == "Invalid credentials"
        assert error.status_code == 401
        assert error.error_code == "AUTHENTICATION_FAILED"
    
    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError creation."""
        error = ResourceNotFoundError("User", "123")
        
        assert "User with ID '123' not found" in error.message
        assert error.status_code == 404
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.details["resource_type"] == "User"
        assert error.details["resource_id"] == "123"
    
    def test_business_logic_error(self):
        """Test BusinessLogicError creation."""
        error = BusinessLogicError(
            message="Cannot delete completed report",
            business_rule="report_deletion_rules"
        )
        
        assert error.message == "Cannot delete completed report"
        assert error.status_code == 400
        assert error.details["business_rule"] == "report_deletion_rules"
    
    def test_rate_limit_exceeded_error(self):
        """Test RateLimitExceededError creation."""
        error = RateLimitExceededError(
            message="Too many requests",
            limit=60,
            window=60,
            retry_after=30
        )
        
        assert error.message == "Too many requests"
        assert error.status_code == 429
        assert error.details["limit"] == 60
        assert error.details["window_seconds"] == 60
        assert error.details["retry_after_seconds"] == 30


class TestSecurityValidation:
    """Test security validation utilities."""
    
    def test_xss_detection(self):
        """Test XSS attack detection."""
        malicious_inputs = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<iframe src='evil.com'></iframe>",
            "onload=alert('xss')",
            "<style>body{background:url('javascript:alert(1)')}</style>"
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(SecurityError) as exc_info:
                SecurityValidator.check_for_xss(malicious_input)
            assert exc_info.value.error_code == "SECURITY_ERROR"
            assert "xss_attempt" in exc_info.value.details.get("violation_type", "")
    
    def test_sql_injection_detection(self):
        """Test SQL injection detection."""
        malicious_inputs = [
            "' OR 1=1 --",
            "'; DROP TABLE users; --",
            "UNION SELECT * FROM passwords",
            "'; INSERT INTO admin VALUES('hacker'); --",
            "EXEC xp_cmdshell('dir')"
        ]
        
        for malicious_input in malicious_inputs:
            with pytest.raises(SecurityError) as exc_info:
                SecurityValidator.check_for_sql_injection(malicious_input)
            assert exc_info.value.error_code == "SECURITY_ERROR"
            assert "sql_injection_attempt" in exc_info.value.details.get("violation_type", "")
    
    def test_safe_string_validation(self):
        """Test safe string validation."""
        # Valid inputs should pass
        safe_inputs = [
            "Hello World",
            "user@example.com",
            "Valid name with spaces",
            "123-456-7890"
        ]
        
        for safe_input in safe_inputs:
            result = SecurityValidator.validate_safe_string(safe_input, "test_field")
            assert result == safe_input.strip()
        
        # Invalid inputs should raise exceptions
        with pytest.raises(Exception):
            SecurityValidator.validate_safe_string("x" * 10001, "test_field")  # Too long
        
        with pytest.raises(Exception):
            SecurityValidator.validate_safe_string("test\x00null", "test_field")  # Null byte
    
    def test_html_sanitization(self):
        """Test HTML sanitization."""
        dirty_html = "<script>alert('xss')</script><p>Safe content</p><a href='javascript:evil()'>Link</a>"
        clean_html = SecurityValidator.sanitize_html(dirty_html)
        
        assert "<script>" not in clean_html
        assert "<p>Safe content</p>" in clean_html
        assert "javascript:" not in clean_html
    
    def test_html_escaping(self):
        """Test HTML escaping."""
        dangerous_text = "<script>alert('xss')</script>"
        escaped_text = SecurityValidator.escape_html(dangerous_text)
        
        assert "&lt;script&gt;" in escaped_text
        assert "<script>" not in escaped_text


class TestDataValidation:
    """Test data validation utilities."""
    
    def test_email_validation(self):
        """Test email validation."""
        # Valid emails
        valid_emails = [
            "user@example.com",
            "test.email+tag@domain.co.uk",
            "user123@test-domain.com"
        ]
        
        for email in valid_emails:
            result = DataValidator.validate_email_address(email)
            assert "@" in result
        
        # Invalid emails
        invalid_emails = [
            "invalid-email",
            "@domain.com",
            "user@",
            "user..double.dot@domain.com"
        ]
        
        for email in invalid_emails:
            with pytest.raises(Exception):
                DataValidator.validate_email_address(email)
    
    def test_phone_validation(self):
        """Test phone number validation."""
        # Valid phone numbers
        valid_phones = [
            "+919876543210",
            "9876543210",
            "+1-555-123-4567"
        ]
        
        for phone in valid_phones:
            result = DataValidator.validate_phone_number(phone)
            assert len(result.replace("+", "")) >= 10
        
        # Invalid phone numbers
        invalid_phones = [
            "123",
            "invalid-phone",
            "12345"
        ]
        
        for phone in invalid_phones:
            with pytest.raises(Exception):
                DataValidator.validate_phone_number(phone)
    
    def test_password_strength_validation(self):
        """Test password strength validation."""
        # Valid passwords
        valid_passwords = [
            "StrongP@ssw0rd",
            "MySecure123!",
            "ComplexPassword1@"
        ]
        
        for password in valid_passwords:
            result = DataValidator.validate_password_strength(password)
            assert result == password
        
        # Invalid passwords
        invalid_passwords = [
            "weak",  # Too short
            "password",  # No uppercase, numbers, or special chars
            "PASSWORD123",  # No lowercase or special chars
            "password!",  # No uppercase or numbers
            "Password1",  # No special characters
            "a" * 200  # Too long
        ]
        
        for password in invalid_passwords:
            with pytest.raises(Exception):
                DataValidator.validate_password_strength(password)
    
    def test_name_validation(self):
        """Test name validation."""
        # Valid names
        valid_names = [
            "John Doe",
            "Mary-Jane O'Connor",
            "José García",
            "Anna-Maria"
        ]
        
        for name in valid_names:
            result = DataValidator.validate_name(name, "test_name")
            assert len(result) >= 2
        
        # Invalid names
        invalid_names = [
            "",  # Empty
            "A",  # Too short
            "x" * 101,  # Too long
            "John123",  # Contains numbers
            "User@Name"  # Contains invalid characters
        ]
        
        for name in invalid_names:
            with pytest.raises(Exception):
                DataValidator.validate_name(name, "test_name")
    
    def test_id_validation(self):
        """Test ID field validation."""
        # Valid IDs
        valid_ids = [1, 123, "456", 9999]
        
        for id_val in valid_ids:
            result = DataValidator.validate_id_field(id_val, "test_id")
            assert result > 0
            assert isinstance(result, int)
        
        # Invalid IDs
        invalid_ids = [0, -1, "invalid", None, 0.5]
        
        for id_val in invalid_ids:
            with pytest.raises(Exception):
                DataValidator.validate_id_field(id_val, "test_id")


class TestFileValidation:
    """Test file validation utilities."""
    
    def test_file_type_validation(self):
        """Test file type validation."""
        # Valid image types
        for mime_type in FileValidator.ALLOWED_IMAGE_TYPES:
            try:
                FileValidator.validate_file_type(mime_type, FileValidator.ALLOWED_IMAGE_TYPES)
            except Exception:
                pytest.fail(f"Valid MIME type {mime_type} was rejected")
        
        # Invalid types
        invalid_types = ["text/html", "application/javascript", "image/svg+xml"]
        
        for mime_type in invalid_types:
            with pytest.raises(Exception):
                FileValidator.validate_file_type(mime_type, FileValidator.ALLOWED_IMAGE_TYPES)
    
    def test_file_size_validation(self):
        """Test file size validation."""
        # Valid sizes
        valid_sizes = [100, 1024, 1024 * 1024]  # 100 bytes, 1KB, 1MB
        
        for size in valid_sizes:
            try:
                FileValidator.validate_file_size(size)
            except Exception:
                pytest.fail(f"Valid file size {size} was rejected")
        
        # Invalid sizes
        invalid_sizes = [FileValidator.MAX_FILE_SIZE + 1, 50 * 1024 * 1024]  # Over 10MB
        
        for size in invalid_sizes:
            with pytest.raises(Exception):
                FileValidator.validate_file_size(size)
    
    def test_filename_validation(self):
        """Test filename validation."""
        # Valid filenames
        valid_filenames = [
            "document.pdf",
            "image_file.jpg",
            "test-file.png",
            "report 2023.pdf"
        ]
        
        for filename in valid_filenames:
            result = FileValidator.validate_filename(filename)
            assert len(result) > 0
            assert not any(char in result for char in '<>:"/\\|?*')
        
        # Invalid filenames
        invalid_filenames = [
            "",  # Empty
            "../../../etc/passwd",  # Path traversal
            "file<script>.exe",  # Dangerous characters
            "con.txt"  # Windows reserved name (should be handled)
        ]
        
        for filename in invalid_filenames:
            if filename == "":
                with pytest.raises(Exception):
                    FileValidator.validate_filename(filename)
            else:
                # Should sanitize, not raise exception
                result = FileValidator.validate_filename(filename)
                assert ".." not in result
                assert not any(char in result for char in '<>:"/\\|?*')


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limiter_basic(self):
        """Test basic rate limiting."""
        limiter = InMemoryRateLimiter()
        
        # Should allow requests under limit
        for i in range(5):
            allowed, info = limiter.is_allowed("test_key", 10, 60)
            assert allowed
            assert info["remaining"] == 10 - i - 1
        
        # Should block when over limit
        for i in range(6):
            allowed, info = limiter.is_allowed("test_key", 10, 60)
        
        # 11th request should be blocked
        allowed, info = limiter.is_allowed("test_key", 10, 60)
        assert not allowed
        assert info["remaining"] == 0
    
    def test_rate_limiter_window_reset(self):
        """Test rate limiter window reset."""
        limiter = InMemoryRateLimiter()
        current_time = time.time()
        
        # Fill up the limit
        for i in range(5):
            allowed, info = limiter.is_allowed("test_key", 5, 60, current_time)
            assert allowed
        
        # Should be blocked
        allowed, info = limiter.is_allowed("test_key", 5, 60, current_time)
        assert not allowed
        
        # After window expires, should be allowed again
        future_time = current_time + 61
        allowed, info = limiter.is_allowed("test_key", 5, 60, future_time)
        assert allowed
        assert info["remaining"] == 4
    
    def test_rate_limiter_multiple_keys(self):
        """Test rate limiter with multiple keys."""
        limiter = InMemoryRateLimiter()
        
        # Different keys should have separate limits
        allowed1, info1 = limiter.is_allowed("key1", 2, 60)
        allowed2, info2 = limiter.is_allowed("key2", 2, 60)
        
        assert allowed1 and allowed2
        assert info1["remaining"] == 1
        assert info2["remaining"] == 1
        
        # Exhaust key1
        limiter.is_allowed("key1", 2, 60)
        allowed1, info1 = limiter.is_allowed("key1", 2, 60)
        
        # key1 should be blocked, key2 should still work
        assert not allowed1
        
        allowed2, info2 = limiter.is_allowed("key2", 2, 60)
        assert allowed2


class TestErrorHandlerIntegration:
    """Test error handler integration with FastAPI."""
    
    def setup_method(self):
        """Set up test database."""
        Base.metadata.create_all(bind=engine)
    
    def teardown_method(self):
        """Clean up test database."""
        Base.metadata.drop_all(bind=engine)
    
    def test_validation_error_response_format(self):
        """Test validation error response format."""
        # Send invalid data to trigger validation error
        response = client.post("/api/v1/company/contact", json={
            "full_name": "A",  # Too short
            "email": "invalid-email",  # Invalid format
            "subject": "Hi",  # Too short
            "message": "Short"  # Too short
        })
        
        assert response.status_code == 422
        data = response.json()
        
        # Check standardized error format
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
        assert "timestamp" in data["error"]
        assert data["error"]["code"] == "VALIDATION_ERROR"
    
    def test_not_found_error_response(self):
        """Test not found error response format."""
        response = client.get("/api/v1/reports/99999")
        
        # Should return 401 (unauthorized) since no auth provided
        # But this tests the error format
        assert response.status_code in [401, 404]
        data = response.json()
        
        assert "error" in data
        assert "code" in data["error"]
        assert "message" in data["error"]
    
    def test_health_check_with_error_handling(self):
        """Test health check endpoint error handling."""
        response = client.get("/health")
        
        # Should return either 200 (healthy) or 503 (unhealthy)
        assert response.status_code in [200, 503]
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data


class TestEndpointSecurityValidation:
    """Test endpoint security validation."""
    
    def test_xss_protection_in_contact_form(self):
        """Test XSS protection in contact form."""
        malicious_data = {
            "full_name": "<script>alert('xss')</script>John Doe",
            "email": "test@example.com",
            "subject": "Test subject",
            "message": "<iframe src='evil.com'></iframe>Valid message content",
            "inquiry_type": "general"
        }
        
        response = client.post("/api/v1/company/contact", json=malicious_data)
        
        # Should either reject (400/422) or sanitize the input
        # The actual behavior depends on implementation
        if response.status_code == 201:
            # If accepted, content should be sanitized
            data = response.json()
            assert "script" not in str(data).lower()
            assert "iframe" not in str(data).lower()
        else:
            # If rejected, should be a client error
            assert 400 <= response.status_code < 500


if __name__ == "__main__":
    pytest.main([__file__])