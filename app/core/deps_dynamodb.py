"""
DynamoDB-based dependency injection
Replaces SQLAlchemy dependencies with DynamoDB services
"""

from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

from app.core.config import settings
from app.services.dynamodb_service import user_service

# Security
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Optional[dict]:
    """
    Get current user from JWT token using DynamoDB
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = jwt.decode(
            credentials.credentials, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # Get user from DynamoDB
    user_data = user_service.get_user_by_id(user_id)
    if user_data is None:
        raise credentials_exception
    
    return user_data

def get_current_active_user(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Get current active user
    """
    if not current_user.get('is_active', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
    return current_user

def get_admin_user(current_user: dict = Depends(get_current_active_user)) -> dict:
    """
    Get current user if they are an admin
    """
    if current_user.get('role') != 'ADMIN':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    return current_user

def get_optional_user(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[dict]:
    """
    Get current user if token is provided, otherwise return None
    """
    if not credentials:
        return None
    
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
            
        user_data = user_service.get_user_by_id(user_id)
        return user_data
        
    except JWTError:
        return None

# Helper functions for authentication
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """
    Create JWT access token
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify password against hash
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """
    Get password hash
    """
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    return pwd_context.hash(password)

def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Authenticate user with email and password
    """
    user = user_service.get_user_by_email(email)
    if not user:
        return None
    if not verify_password(password, user['password_hash']):
        return None
    return user