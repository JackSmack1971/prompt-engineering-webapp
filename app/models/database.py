from typing import List, Optional
from datetime import datetime
import uuid
from cryptography.fernet import Fernet
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, JSON, Float, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship, Mapped, mapped_column, DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    full_name: Mapped[Optional[str]] = mapped_column(String(100))
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500))
    bio: Mapped[Optional[str]] = mapped_column(Text)
    
    openrouter_api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    @property
    def openrouter_api_key(self) -> Optional[str]:
        if self.openrouter_api_key_encrypted:
            try:
                f = Fernet(settings.fernet_key.get_secret_value().encode())
                decrypted_key = f.decrypt(self.openrouter_api_key_encrypted.encode()).decode()
                return decrypted_key
            except Exception:
                logger.warning(f"Failed to decrypt API key for user {self.id}")
                return None
        return None

    @openrouter_api_key.setter
    def openrouter_api_key(self, key: Optional[str]):
        if key:
            f = Fernet(settings.fernet_key.get_secret_value().encode())
            self.openrouter_api_key_encrypted = f.encrypt(key.encode()).decode()
        else:
            self.openrouter_api_key_encrypted = None
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    subscription_tier: Mapped[str] = mapped_column(String(20), default="free")
    monthly_quota_used: Mapped[int] = mapped_column(Integer, default=0)
    monthly_quota_limit: Mapped[int] = mapped_column(Integer, default=100)
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    
    preferences: Mapped[dict] = mapped_column(JSON, default={})
    ui_settings: Mapped[dict] = mapped_column(JSON, default={})
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    prompts: Mapped[List["Prompt"]] = relationship("Prompt", back_populates="owner")
    test_results: Mapped[List["TestResult"]] = relationship("TestResult", back_populates="user")

    __table_args__ = (
        Index('ix_users_created_at', 'created_at'),
        Index('ix_users_last_login_at', 'last_login_at'),
    )

class Prompt(Base):
    __tablename__ = "prompts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    system_message: Mapped[Optional[str]] = mapped_column(Text)
    
    category: Mapped[Optional[str]] = mapped_column(String(50))
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])
    language: Mapped[str] = mapped_column(String(10), default="en")
    
    is_template: Mapped[bool] = mapped_column(Boolean, default=False)
    template_variables: Mapped[List[str]] = mapped_column(ARRAY(String), default=[])
    
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_prompt_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("prompts.id", ondelete="CASCADE"))
    is_latest_version: Mapped[bool] = mapped_column(Boolean, default=True)
    
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[Optional[float]] = mapped_column(Float)
    
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    owner: Mapped["User"] = relationship("User", back_populates="prompts")
    parent_prompt: Mapped[Optional["Prompt"]] = relationship("Prompt", remote_side="Prompt.id", back_populates="versions")
    versions: Mapped[List["Prompt"]] = relationship("Prompt", back_populates="parent_prompt")
    test_results: Mapped[List["TestResult"]] = relationship("TestResult", back_populates="prompt")

    __table_args__ = (
        Index('ix_prompts_title', 'title'),
        Index('ix_prompts_category', 'category'),
        Index('ix_prompts_is_public', 'is_public'),
        Index('ix_prompts_created_at', 'created_at'),
        # For PostgreSQL, a GIN index would be appropriate for the 'tags' ARRAY column:
        # Index('ix_prompts_tags', 'tags', postgresql_using='gin'),
    )

class TestResult(Base):
    __tablename__ = "test_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    temperature: Mapped[Optional[float]] = mapped_column(Float)
    max_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    top_p: Mapped[Optional[float]] = mapped_column(Float)
    frequency_penalty: Mapped[Optional[float]] = mapped_column(Float)
    presence_penalty: Mapped[Optional[float]] = mapped_column(Float)
    
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    cost_usd: Mapped[Optional[float]] = mapped_column(Float)
    
    test_input: Mapped[str] = mapped_column(Text, nullable=False)
    test_output: Mapped[str] = mapped_column(Text, nullable=False)
    
    evaluation_score: Mapped[Optional[float]] = mapped_column(Float)
    evaluation_feedback: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="test_results")
    prompt: Mapped["Prompt"] = relationship("Prompt", back_populates="test_results")

    __table_args__ = (
        Index('ix_test_results_created_at', 'created_at'),
        Index('ix_test_results_model_name', 'model_name'),
    )

class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    system_message: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    prompt: Mapped["Prompt"] = relationship("Prompt")

    __table_args__ = (
        Index('ix_prompt_versions_prompt_id_version_number', 'prompt_id', 'version_number', unique=True),
        Index('ix_prompt_versions_created_at', 'created_at'),
    )

class PromptCollaboration(Base):
    __tablename__ = "prompt_collaborations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    prompt_id: Mapped[int] = mapped_column(Integer, ForeignKey("prompts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    role: Mapped[str] = mapped_column(String(20), nullable=False) # e.g., 'editor', 'viewer'
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('prompt_id', 'user_id', name='unique_collaboration'),
    )
    # The UniqueConstraint already creates an index, so no additional index needed for (prompt_id, user_id)

    prompt: Mapped["Prompt"] = relationship("Prompt")
    user: Mapped["User"] = relationship("User")

class APICallLog(Base):
    __tablename__ = "api_call_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    
    request_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    response_payload: Mapped[Optional[dict]] = mapped_column(JSON)
    
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index('ix_api_call_logs_created_at', 'created_at'),
        Index('ix_api_call_logs_user_id', 'user_id'),
        Index('ix_api_call_logs_endpoint_method', 'endpoint', 'method'),
        Index('ix_api_call_logs_status_code', 'status_code'),
    )

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    
    old_value: Mapped[Optional[dict]] = mapped_column(JSON)
    new_value: Mapped[Optional[dict]] = mapped_column(JSON)
    
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index('ix_audit_logs_created_at', 'created_at'),
        Index('ix_audit_logs_user_id', 'user_id'),
        Index('ix_audit_logs_action_entity_type', 'action', 'entity_type'),
    )

class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    
    feedback_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., 'bug', 'feature_request', 'general'
    subject: Mapped[Optional[str]] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default="new") # e.g., 'new', 'in_progress', 'resolved'
    priority: Mapped[str] = mapped_column(String(20), default="medium") # e.g., 'low', 'medium', 'high'
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[Optional["User"]] = relationship("User")

    __table_args__ = (
        Index('ix_feedback_created_at', 'created_at'),
        Index('ix_feedback_status', 'status'),
        Index('ix_feedback_priority', 'priority'),
        Index('ix_feedback_type', 'feedback_type'),
    )

class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    message: Mapped[str] = mapped_column(Text, nullable=False)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False) # e.g., 'system', 'alert', 'prompt_update'
    
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_notifications_created_at', 'created_at'),
        Index('ix_notifications_is_read', 'is_read'),
        Index('ix_notifications_type', 'notification_type'),
    )

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50))
    transaction_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False) # e.g., 'pending', 'completed', 'failed'
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_payments_created_at', 'created_at'),
        Index('ix_payments_status', 'status'),
    )

class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    tier: Mapped[str] = mapped_column(String(20), nullable=False) # e.g., 'free', 'pro', 'enterprise'
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_subscriptions_is_active', 'is_active'),
        Index('ix_subscriptions_end_date', 'end_date'),
    )

class UsageLog(Base):
    __tablename__ = "usage_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    feature_used: Mapped[str] = mapped_column(String(100), nullable=False)
    usage_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_usage_logs_created_at', 'created_at'),
        Index('ix_usage_logs_feature_used', 'feature_used'),
    )

class UserActivity(Base):
    __tablename__ = "user_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    activity_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., 'login', 'prompt_create', 'test_run'
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_user_activities_created_at', 'created_at'),
        Index('ix_user_activities_type', 'activity_type'),
    )

class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    setting_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    setting_value: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        # UniqueConstraint('user_id', 'setting_key') implicitly creates an index
        Index('ix_user_settings_updated_at', 'updated_at'),
    )

class Webhook(Base):
    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default_factory=uuid.uuid4, unique=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    event_type: Mapped[str] = mapped_column(String(100), nullable=False) # e.g., 'prompt_created', 'test_completed'
    callback_url: Mapped[str] = mapped_column(String(500), nullable=False)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    secret: Mapped[Optional[str]] = mapped_column(String(255)) # For HMAC verification
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        Index('ix_webhooks_event_type', 'event_type'),
        Index('ix_webhooks_is_active', 'is_active'),
        Index('ix_webhooks_created_at', 'created_at'),
    )