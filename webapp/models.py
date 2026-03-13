"""
SQLAlchemy ORM models for KMD.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from webapp.database import Base

# ---------------------------------------------------------------------------
# Project
# ---------------------------------------------------------------------------

class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    customer: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="active")
    stages: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    # relationships
    versions: Mapped[List["DocumentVersion"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project id={self.id} name={self.name!r}>"

# ---------------------------------------------------------------------------
# DocumentVersion
# ---------------------------------------------------------------------------

class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(String(2048), nullable=False)
    file_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="versions")

    def __repr__(self) -> str:
        return f"<DocumentVersion id={self.id} filename={self.filename!r} v{self.version}>"

# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # relationships
    activity_logs: Mapped[List["ActivityLog"]] = relationship(back_populates="user")
    api_keys: Mapped[List["ApiKey"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"

# ---------------------------------------------------------------------------
# ActivityLog
# ---------------------------------------------------------------------------

class ActivityLog(Base):
    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(256), nullable=False)
    file_name: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="activity_logs")

    def __repr__(self) -> str:
        return f"<ActivityLog id={self.id} op={self.operation!r}>"

# ---------------------------------------------------------------------------
# ApiKey
# ---------------------------------------------------------------------------

class ApiKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key_hash: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_used: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # relationships
    user: Mapped[Optional["User"]] = relationship(back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} name={self.name!r}>"
