"""Pydantic v2 request/response schemas with validation."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from .models import SEVERITIES


# ---------- Auth ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = "citizen"
    ward: str | None = Field(default=None, max_length=80)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("citizen", "officer", "admin"):
            raise ValueError("role must be citizen, officer or admin")
        return v

    @field_validator("ward")
    @classmethod
    def ward_required_for_officer(cls, v: str | None, info):
        if info.data.get("role") == "officer" and not v:
            raise ValueError("ward is required for officer accounts")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    role: str
    ward: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Categories ----------
class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    icon: str
    base_priority: int


# ---------- Complaints ----------
class ComplaintCreate(BaseModel):
    title: str = Field(min_length=8, max_length=160)
    description: str = Field(min_length=20, max_length=4000)
    category_slug: str
    ward: str | None = Field(default=None, max_length=80)
    area: str | None = Field(default=None, max_length=120)
    severity: str = "medium"

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}")
        return v


class ComplaintUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=8, max_length=160)
    description: str | None = Field(default=None, min_length=20, max_length=4000)


class AssignIn(BaseModel):
    officer_id: int
    ward: str | None = Field(default=None, max_length=80)


class StatusChangeIn(BaseModel):
    to_status: str
    note: str | None = Field(default=None, max_length=2000)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class CommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    body: str
    author_name: str | None = None
    created_at: datetime


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    from_status: str | None = None
    to_status: str
    note: str | None = None
    actor_name: str | None = None
    created_at: datetime


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticket: str
    title: str
    description: str
    status: str
    category_name: str | None = None
    reporter_name: str | None = None
    assignee_name: str | None = None
    ward: str | None = None
    area: str | None = None
    severity: str
    priority: int
    resolved_note: str | None = None
    reject_reason: str | None = None
    reopen_count: int
    created_at: datetime
    updated_at: datetime
    history: list[HistoryOut] = []
    comments: list[CommentOut] = []
