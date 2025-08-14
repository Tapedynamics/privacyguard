"""
Pydantic schemas for API requests and responses.

These models validate input data and serialise database objects for
responses. Separating the database models from the schemas prevents
exposing internal fields and enforces strict typing at the API layer.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from .models import ConsentStatus, PhotoStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    role: str

    class Config:
        orm_mode = True


class FaceResponse(BaseModel):
    id: int
    bbox: dict
    rekognition_face_id: Optional[str]
    name: Optional[str]
    consent_status: ConsentStatus

    class Config:
        orm_mode = True


class PhotoResponse(BaseModel):
    id: int
    filename: str
    status: PhotoStatus
    upload_time: datetime
    faces: List[FaceResponse] = []

    class Config:
        orm_mode = True


class NameUpdate(BaseModel):
    name: str = Field(..., description="Name to associate with the face")


class ConsentUpdate(BaseModel):
    consent_status: ConsentStatus


class LoginRequest(BaseModel):
    username: str
    password: str