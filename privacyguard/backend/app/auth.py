"""
Authentication utilities using JWT and password hashing.

This module provides helper functions to hash passwords, verify them,
create JWT access tokens, and retrieve the current user from a token.
The implementation uses `passlib` for password hashing and `python-jose`
for signing and decoding JWT tokens.
"""
import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from . import models, database


# Create a passlib context for hashing passwords
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme that expects a bearer token in the Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if plain_password matches the hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a plaintext password for storage."""
    return pwd_context.hash(password)


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """
    Attempt to authenticate a user by username and password.

    Returns the user instance if authentication succeeds, otherwise None.
    """
    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token containing the given data.

    Args:
        data: The data to include in the token payload.
        expires_delta: An optional timedelta specifying the token's lifetime.

    Returns:
        A JWT encoded string.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=60))
    to_encode.update({"exp": expire})
    secret_key = os.getenv("JWT_SECRET_KEY", "secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def get_current_user(db: Session = Depends(database.get_db), token: str = Depends(oauth2_scheme)) -> models.User:
    """
    Retrieve the currently authenticated user based on the JWT token.

    Raises HTTPException if the token is invalid or expired.
    """
    secret_key = os.getenv("JWT_SECRET_KEY", "secret")
    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(models.User).filter(models.User.username == username).first()
    if user is None:
        raise credentials_exception
    return user