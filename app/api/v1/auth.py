from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.deps import get_db, get_current_user, security
from app.core.security import (
    verify_password,
    get_password_hash,
    generate_token_pair,
    verify_token,
    create_access_token
)
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    TokenResponse,
    TokenRefresh,
    UserResponse,
    AuthResponse,
    ChangePassword
)

router = APIRouter()


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register_user(
    user_data: UserRegister,
    db: Session = Depends(get_db)
) -> Any:
    """
    Register a new user account.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        User data and authentication tokens
        
    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        username=user_data.username,
        email=user_data.email,
        password_hash=hashed_password,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        phone_number=user_data.phone_number,
        role=UserRole.USER,  # Default role
        is_active=True,
        is_verified=False  # Email verification required
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    # Generate tokens
    tokens = generate_token_pair(db_user.id, db_user.username)
    
    # Update last login
    db_user.last_login = datetime.utcnow()
    db.commit()
    
    return AuthResponse(
        user=UserResponse.model_validate(db_user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


@router.post("/login", response_model=AuthResponse)
def login_user(
    user_credentials: UserLogin,
    db: Session = Depends(get_db)
) -> Any:
    """
    Authenticate user and return tokens.
    
    Args:
        user_credentials: Login credentials
        db: Database session
        
    Returns:
        User data and authentication tokens
        
    Raises:
        HTTPException: If credentials are invalid
    """
    # Find user by username or email
    user = db.query(User).filter(
        (User.username == user_credentials.username) |
        (User.email == user_credentials.username)
    ).first()
    
    if not user or not verify_password(user_credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated"
        )
    
    # Generate tokens
    tokens = generate_token_pair(user.id, user.username)
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()
    
    return AuthResponse(
        user=UserResponse.model_validate(user),
        tokens=TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    token_data: TokenRefresh,
    db: Session = Depends(get_db)
) -> Any:
    """
    Refresh access token using refresh token.
    
    Args:
        token_data: Refresh token data
        db: Database session
        
    Returns:
        New access and refresh tokens
        
    Raises:
        HTTPException: If refresh token is invalid
    """
    # Verify refresh token
    payload = verify_token(token_data.refresh_token, token_type="refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user from token
    user_id = payload.get("sub")
    username = payload.get("username")
    
    if not user_id or not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload"
        )
    
    # Verify user still exists and is active
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    # Generate new tokens
    tokens = generate_token_pair(user.id, user.username)
    
    return TokenResponse(
        access_token=tokens["access_token"],
        refresh_token=tokens["refresh_token"],
        token_type=tokens["token_type"],
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post("/logout")
def logout_user(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Logout user (invalidate tokens on client side).
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Success message
        
    Note:
        Since we're using stateless JWT tokens, logout is handled client-side
        by removing tokens. In production, consider implementing token blacklisting.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
) -> Any:
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user data
    """
    return UserResponse.model_validate(current_user)


@router.put("/change-password")
def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    """
    Change user password.
    
    Args:
        password_data: Password change data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If current password is incorrect
    """
    # Verify current password
    if not verify_password(password_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    # Update password
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    
    return {"message": "Password changed successfully"}


@router.get("/verify-token")
def verify_user_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Any:
    """
    Verify if the provided token is valid.
    
    Args:
        credentials: HTTP Authorization credentials
        
    Returns:
        Token validity status and user info
        
    Raises:
        HTTPException: If token is invalid
    """
    # Verify token
    payload = verify_token(credentials.credentials, token_type="access")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    return {
        "valid": True,
        "user_id": payload.get("sub"),
        "username": payload.get("username"),
        "expires_at": payload.get("exp")
    }