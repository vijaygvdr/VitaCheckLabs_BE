"""
Authentication API endpoints using DynamoDB
Replaces SQLAlchemy-based authentication with DynamoDB
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import timedelta
from pydantic import BaseModel, EmailStr

from app.core.config import settings
from app.core.deps_dynamodb import (
    authenticate_user, create_access_token, get_current_active_user,
    get_password_hash, user_service
)
from app.schemas.auth import UserRegister as UserCreate, TokenResponse, UserResponse, ChangePassword

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

@router.post("/register", response_model=UserResponse)
def register(user_data: UserCreate):
    """
    Register a new user
    """
    # Check if user already exists (normalize for comparison)
    existing_user = user_service.get_user_by_email(user_data.email.lower())
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    existing_username = user_service.get_user_by_username(user_data.username.lower())
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Create user
    user_dict = {
        'email': user_data.email.lower(),
        'username': user_data.username.lower(),
        'password_hash': get_password_hash(user_data.password),
        'first_name': user_data.first_name or '',
        'last_name': user_data.last_name or '',
        'phone_number': user_data.phone_number or '',
        'role': 'user',
        'is_active': True,
        'is_verified': False
    }
    
    try:
        created_user = user_service.create_user(user_dict)
        
        # Transform data for UserResponse schema
        user_response_data = created_user.copy()
        user_response_data['id'] = user_response_data.get('user_id')  # Map user_id to id
        user_response_data['role'] = user_response_data.get('role', 'USER').lower()  # Convert to lowercase
        
        # Handle empty last_login
        if user_response_data.get('last_login') == '':
            user_response_data['last_login'] = None
        
        # Parse created_at to datetime object
        from datetime import datetime
        if isinstance(user_response_data.get('created_at'), str):
            try:
                user_response_data['created_at'] = datetime.fromisoformat(
                    user_response_data['created_at'].replace('Z', '+00:00')
                )
            except:
                user_response_data['created_at'] = datetime.utcnow()
        
        return UserResponse(**user_response_data)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest):
    """
    Login user and return access token
    """
    user = authenticate_user(login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.get('is_active', False):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    # Update last login
    user_service.update_last_login(user['user_id'])
    
    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user['user_id']}, expires_delta=access_token_expires
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "user_id": user['user_id'],
            "email": user['email'],
            "username": user['username'],
            "first_name": user.get('first_name', ''),
            "last_name": user.get('last_name', ''),
            "role": user['role'],
            "is_active": user['is_active'],
            "is_verified": user['is_verified']
        }
    }

@router.get("/me", response_model=UserResponse)
def get_current_user_info(current_user: dict = Depends(get_current_active_user)):
    """
    Get current user information
    """
    # Transform data for UserResponse schema
    user_response_data = current_user.copy()
    user_response_data['id'] = user_response_data.get('user_id')  # Map user_id to id
    user_response_data['role'] = user_response_data.get('role', 'user').lower()  # Convert to lowercase
    
    # Handle empty last_login
    if user_response_data.get('last_login') == '':
        user_response_data['last_login'] = None
    
    # Parse created_at to datetime object if it's a string
    from datetime import datetime
    if isinstance(user_response_data.get('created_at'), str):
        try:
            user_response_data['created_at'] = datetime.fromisoformat(
                user_response_data['created_at'].replace('Z', '+00:00')
            )
        except:
            user_response_data['created_at'] = datetime.utcnow()
    
    return UserResponse(**user_response_data)

@router.post("/logout")
def logout():
    """
    Logout user (client should discard token)
    """
    return {"message": "Successfully logged out"}

@router.put("/profile", response_model=UserResponse)
def update_profile(
    first_name: str = None,
    last_name: str = None,
    phone_number: str = None,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Update user profile
    """
    updates = {}
    if first_name is not None:
        updates['first_name'] = first_name
    if last_name is not None:
        updates['last_name'] = last_name
    if phone_number is not None:
        updates['phone_number'] = phone_number
    
    if updates:
        success = user_service.update_user(current_user['user_id'], updates)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update profile"
            )
    
    # Get updated user data
    updated_user = user_service.get_user_by_id(current_user['user_id'])
    
    # Transform data for UserResponse schema
    user_response_data = updated_user.copy()
    user_response_data['id'] = user_response_data.get('user_id')  # Map user_id to id
    user_response_data['role'] = user_response_data.get('role', 'user').lower()  # Convert to lowercase
    
    # Handle empty last_login
    if user_response_data.get('last_login') == '':
        user_response_data['last_login'] = None
    
    # Parse created_at to datetime object if it's a string
    from datetime import datetime
    if isinstance(user_response_data.get('created_at'), str):
        try:
            user_response_data['created_at'] = datetime.fromisoformat(
                user_response_data['created_at'].replace('Z', '+00:00')
            )
        except:
            user_response_data['created_at'] = datetime.utcnow()
    
    return UserResponse(**user_response_data)


# Additional Authentication Endpoints
@router.post("/refresh", response_model=dict)
def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
):
    """
    Refresh access token using current token
    """
    try:
        from jose import jwt, JWTError
        
        # Verify the current token
        try:
            payload = jwt.decode(
                credentials.credentials, 
                settings.SECRET_KEY, 
                algorithms=[settings.ALGORITHM]
            )
            user_id: str = payload.get("sub")
            if user_id is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Get user from database
        user = user_service.get_user_by_id(user_id)
        if not user or not user.get('is_active', False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            data={"sub": user_id}, expires_delta=access_token_expires
        )
        
        # Create refresh token (longer expiry)
        refresh_token_expires = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        new_refresh_token = create_access_token(
            data={"sub": user_id, "type": "refresh"}, expires_delta=refresh_token_expires
        )
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )


@router.put("/change-password")
def change_password(
    password_data: ChangePassword,
    current_user: dict = Depends(get_current_active_user)
):
    """
    Change user password
    """
    try:
        # Verify current password
        user = user_service.get_user_by_id(current_user['user_id'])
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Check current password
        from passlib.context import CryptContext
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        
        if not pwd_context.verify(password_data.current_password, user['password_hash']):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        new_password_hash = get_password_hash(password_data.new_password)
        success = user_service.update_user(current_user['user_id'], {
            'password_hash': new_password_hash
        })
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update password"
            )
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )


@router.get("/verify-token")
def verify_user_token(
    current_user: dict = Depends(get_current_active_user)
):
    """
    Verify if token is valid and return user info
    """
    return {
        "valid": True,
        "user": {
            "user_id": current_user['user_id'],
            "email": current_user['email'],
            "username": current_user['username'],
            "role": current_user['role'],
            "is_active": current_user['is_active'],
            "is_verified": current_user.get('is_verified', False)
        },
        "message": "Token is valid"
    }