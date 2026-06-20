import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, ForeignKey, String, Boolean
from sqlalchemy.orm import Mapped,mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.document import Document
    from app.models.conversation import Conversation

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    isVerified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    documents: Mapped[list["Document"]] = relationship(
        "Document", back_populates="user", cascade="all, delete-orphan"
    )

    conversation: Mapped[list["Conversation"]] = relationship(
        "Conversation", back_populates="user", cascade="all, delete-orphan"
    )


    otp_verifications: Mapped[list["OtpVerification"]] = relationship(
        "OtpVerification", back_populates="user", cascade="all, delete-orphan"
    )


class OtpVerification(Base):
    __tablename__ = "otp_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    otp = Column(String(6), nullable=False)
    is_used = Column(Boolean, nullable=False, default=False)
    reset_token_hash = Column(String(64), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped[User] = relationship("User", back_populates="otp_verifications")
