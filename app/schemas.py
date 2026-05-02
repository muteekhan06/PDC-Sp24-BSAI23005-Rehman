"""
Pydantic schemas for request/response validation.
"""

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# ---------- Document Schemas ----------
class DocumentCreate(BaseModel):
    title: str
    content: str = ""
    owner_id: str


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    version: int  # Required for optimistic locking


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    version: int
    owner_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------- LLM Schemas ----------
class LLMRequest(BaseModel):
    prompt: str


class LLMResponse(BaseModel):
    answer: str
    source: str  # "llm" or "fallback"
    circuit_state: str  # "closed", "open", "half-open"


# ---------- User Schemas ----------
class UserResponse(BaseModel):
    id: int
    clerk_id: str
    email: str
    is_premium: int

    class Config:
        from_attributes = True
