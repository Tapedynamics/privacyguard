"""
Database models for the PrivacyGuard backend.

These SQLAlchemy models define the database schema for photos, faces,
users and sessions.  They are intentionally simple: relationships are
configured to cascade deletions, and sensible defaults are provided.
"""
import enum
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Enum,
    ForeignKey,
    JSON,
)
from sqlalchemy.orm import relationship, declarative_base


Base = declarative_base()


class PhotoStatus(str, enum.Enum):
    IN_QUEUE = "in_queue"
    PROCESSING = "processing"
    PROCESSED = "processed"


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, default="admin")

    sessions = relationship("Session", back_populates="user", cascade="all,delete-orphan")


class Session(Base):
    __tablename__ = "sessions"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="sessions")


class Photo(Base):
    __tablename__ = "photos"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    s3_key = Column(String, nullable=False, unique=True)
    upload_time = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(PhotoStatus), default=PhotoStatus.IN_QUEUE, nullable=False)

    faces = relationship("Face", back_populates="photo", cascade="all,delete-orphan")


class Face(Base):
    __tablename__ = "faces"
    id = Column(Integer, primary_key=True, index=True)
    photo_id = Column(Integer, ForeignKey("photos.id"))
    rekognition_face_id = Column(String, nullable=True, index=True)
    bbox = Column(JSON, nullable=False)  # JSON with keys: x, y, width, height
    name = Column(String, nullable=True)
    consent_status = Column(Enum(ConsentStatus), default=ConsentStatus.PENDING, nullable=False)

    photo = relationship("Photo", back_populates="faces")