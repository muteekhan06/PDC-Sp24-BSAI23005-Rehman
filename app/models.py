"""
Database models for StudySync.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, func
from app.database import Base


class Document(Base):
    """Represents a shared study document."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, default="")
    version = Column(Integer, default=1, nullable=False)  # For optimistic locking
    owner_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class User(Base):
    """Local user record, synced via Clerk webhooks."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    clerk_id = Column(String(255), unique=True, nullable=False)
    email = Column(String(255), nullable=False)
    is_premium = Column(Integer, default=0)  # 0 = free, 1 = premium
    created_at = Column(DateTime, server_default=func.now())


class LLMRequestLog(Base):
    """Logs every LLM API call for debugging / observability."""
    __tablename__ = "llm_request_logs"

    id = Column(Integer, primary_key=True, index=True)
    prompt = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status = Column(String(50), nullable=False)  # success, timeout, circuit_open, fallback
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
