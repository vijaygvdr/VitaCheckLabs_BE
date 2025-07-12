import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.main import app
from app.core.deps import get_db
from app.core.security import get_password_hash, verify_password, generate_token_pair, verify_token
from app.models.user import User, UserRole

# Test database setup
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    """Create test client with fresh database"""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user_data():
    """Sample user data for testing"""
    return {
        "username": "testuser",
        "email": "test@example.com",
        "password": "testpassword123",
        "first_name": "Test",
        "last_name": "User"
    }


@pytest.fixture
def create_test_user(db_session):
    """Create a test user in the database"""
    user = User(
        username="existinguser",
        email="existing@example.com",
        password_hash=get_password_hash("password123"),
        first_name="Existing",
        last_name="User",
        role=UserRole.USER,
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestPasswordHashing:
    """Test password hashing functionality"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "test_password_123"
        hashed = get_password_hash(password)
        
        # Hashed password should be different from original
        assert hashed != password
        
        # Should verify correctly
        assert verify_password(password, hashed) is True
        
        # Wrong password should not verify
        assert verify_password("wrong_password", hashed) is False
    
    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes"""
        password1 = "password123"
        password2 = "password456"
        
        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)
        
        assert hash1 != hash2


class TestJWTTokens:
    """Test JWT token functionality"""
    
    def test_generate_token_pair(self):
        """Test JWT token pair generation"""
        user_id = 1
        username = "testuser"
        
        tokens = generate_token_pair(user_id, username)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "token_type" in tokens
        assert tokens["token_type"] == "bearer"
    
    def test_verify_access_token(self):
        """Test access token verification"""
        user_id = 1
        username = "testuser"
        
        tokens = generate_token_pair(user_id, username)
        access_token = tokens["access_token"]
        
        # Verify valid token
        payload = verify_token(access_token, "access")
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["username"] == username
        assert payload["type"] == "access"
    
    def test_verify_refresh_token(self):
        """Test refresh token verification"""
        user_id = 1
        username = "testuser"
        
        tokens = generate_token_pair(user_id, username)
        refresh_token = tokens["refresh_token"]
        
        # Verify valid token
        payload = verify_token(refresh_token, "refresh")
        assert payload is not None
        assert payload["sub"] == str(user_id)
        assert payload["username"] == username
        assert payload["type"] == "refresh"
    
    def test_invalid_token(self):
        """Test invalid token verification"""
        invalid_token = "invalid.jwt.token"
        
        payload = verify_token(invalid_token, "access")
        assert payload is None
    
    def test_wrong_token_type(self):
        """Test verifying token with wrong type"""
        user_id = 1
        username = "testuser"
        
        tokens = generate_token_pair(user_id, username)
        access_token = tokens["access_token"]
        
        # Try to verify access token as refresh token
        payload = verify_token(access_token, "refresh")
        assert payload is None


class TestUserRegistration:
    """Test user registration endpoints"""
    
    def test_register_new_user(self, client, test_user_data):
        """Test successful user registration"""
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 201
        data = response.json()
        
        # Check response structure
        assert "user" in data
        assert "tokens" in data
        
        # Check user data
        user = data["user"]
        assert user["username"] == test_user_data["username"]
        assert user["email"] == test_user_data["email"]
        assert user["first_name"] == test_user_data["first_name"]
        assert user["last_name"] == test_user_data["last_name"]
        assert user["role"] == "user"
        assert user["is_active"] is True
        assert user["is_verified"] is False
        
        # Check tokens
        tokens = data["tokens"]
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert tokens["expires_in"] == 1800  # 30 minutes
    
    def test_register_duplicate_username(self, client, test_user_data, create_test_user):
        """Test registration with existing username"""
        test_user_data["username"] = "existinguser"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Username already registered"
    
    def test_register_duplicate_email(self, client, test_user_data, create_test_user):
        """Test registration with existing email"""
        test_user_data["email"] = "existing@example.com"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Email already registered"
    
    def test_register_invalid_email(self, client, test_user_data):
        """Test registration with invalid email"""
        test_user_data["email"] = "invalid-email"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_register_short_password(self, client, test_user_data):
        """Test registration with password too short"""
        test_user_data["password"] = "short"
        
        response = client.post("/api/v1/auth/register", json=test_user_data)
        
        assert response.status_code == 422  # Validation error


class TestUserLogin:
    """Test user login endpoints"""
    
    def test_login_valid_username(self, client, create_test_user):
        """Test successful login with username"""
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check response structure
        assert "user" in data
        assert "tokens" in data
        
        # Check user data
        user = data["user"]
        assert user["username"] == "existinguser"
        assert user["email"] == "existing@example.com"
        
        # Check tokens
        tokens = data["tokens"]
        assert "access_token" in tokens
        assert "refresh_token" in tokens
    
    def test_login_valid_email(self, client, create_test_user):
        """Test successful login with email"""
        login_data = {
            "username": "existing@example.com",
            "password": "password123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["user"]["email"] == "existing@example.com"
    
    def test_login_wrong_password(self, client, create_test_user):
        """Test login with wrong password"""
        login_data = {
            "username": "existinguser",
            "password": "wrongpassword"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username/email or password"
    
    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user"""
        login_data = {
            "username": "nonexistent",
            "password": "password123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username/email or password"
    
    def test_login_inactive_user(self, client, db_session):
        """Test login with inactive user"""
        user = User(
            username="inactiveuser",
            email="inactive@example.com",
            password_hash=get_password_hash("password123"),
            role=UserRole.USER,
            is_active=False
        )
        db_session.add(user)
        db_session.commit()
        
        login_data = {
            "username": "inactiveuser",
            "password": "password123"
        }
        
        response = client.post("/api/v1/auth/login", json=login_data)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Account is deactivated"


class TestTokenRefresh:
    """Test token refresh functionality"""
    
    def test_refresh_valid_token(self, client, create_test_user):
        """Test token refresh with valid refresh token"""
        # First login to get tokens
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        refresh_token = login_response.json()["tokens"]["refresh_token"]
        
        # Refresh token
        refresh_data = {"refresh_token": refresh_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_refresh_invalid_token(self, client):
        """Test token refresh with invalid refresh token"""
        refresh_data = {"refresh_token": "invalid.jwt.token"}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"
    
    def test_refresh_access_token_as_refresh(self, client, create_test_user):
        """Test using access token as refresh token"""
        # Login to get tokens
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Try to use access token as refresh token
        refresh_data = {"refresh_token": access_token}
        response = client.post("/api/v1/auth/refresh", json=refresh_data)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid refresh token"


class TestProtectedEndpoints:
    """Test protected endpoints requiring authentication"""
    
    def test_get_current_user_valid_token(self, client, create_test_user):
        """Test getting current user with valid token"""
        # Login to get token
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Get current user
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "existinguser"
        assert data["email"] == "existing@example.com"
    
    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token"""
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        response = client.get("/api/v1/auth/me", headers=headers)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Could not validate credentials"
    
    def test_get_current_user_no_token(self, client):
        """Test getting current user without token"""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 403  # Missing authorization header


class TestPasswordChange:
    """Test password change functionality"""
    
    def test_change_password_valid(self, client, create_test_user):
        """Test successful password change"""
        # Login to get token
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Change password
        password_data = {
            "current_password": "password123",
            "new_password": "newpassword456"
        }
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.put("/api/v1/auth/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully"
        
        # Verify old password no longer works
        old_login = {
            "username": "existinguser",
            "password": "password123"
        }
        response = client.post("/api/v1/auth/login", json=old_login)
        assert response.status_code == 401
        
        # Verify new password works
        new_login = {
            "username": "existinguser",
            "password": "newpassword456"
        }
        response = client.post("/api/v1/auth/login", json=new_login)
        assert response.status_code == 200
    
    def test_change_password_wrong_current(self, client, create_test_user):
        """Test password change with wrong current password"""
        # Login to get token
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Try to change password with wrong current password
        password_data = {
            "current_password": "wrongpassword",
            "new_password": "newpassword456"
        }
        
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.put("/api/v1/auth/change-password", json=password_data, headers=headers)
        
        assert response.status_code == 400
        assert response.json()["detail"] == "Incorrect current password"


class TestTokenVerification:
    """Test token verification endpoint"""
    
    def test_verify_valid_token(self, client, create_test_user):
        """Test verifying a valid token"""
        # Login to get token
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Verify token
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert "user_id" in data
        assert "username" in data
        assert "expires_at" in data
    
    def test_verify_invalid_token(self, client):
        """Test verifying an invalid token"""
        headers = {"Authorization": "Bearer invalid.jwt.token"}
        response = client.get("/api/v1/auth/verify-token", headers=headers)
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"


class TestLogout:
    """Test logout functionality"""
    
    def test_logout_valid_user(self, client, create_test_user):
        """Test logout with valid authenticated user"""
        # Login to get token
        login_data = {
            "username": "existinguser",
            "password": "password123"
        }
        
        login_response = client.post("/api/v1/auth/login", json=login_data)
        access_token = login_response.json()["tokens"]["access_token"]
        
        # Logout
        headers = {"Authorization": f"Bearer {access_token}"}
        response = client.post("/api/v1/auth/logout", headers=headers)
        
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"


if __name__ == "__main__":
    pytest.main([__file__])