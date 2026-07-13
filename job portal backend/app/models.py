from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AnalyticsVisit(Base):
    __tablename__ = "analytics_visits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    visitor_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(100), nullable=False, default="Unknown", index=True)
    region: Mapped[Optional[str]] = mapped_column(String(150), nullable=True, index=True)
    location_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visited_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(400), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    published_date: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    deadline_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    salary_range: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    reference_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    application_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experience_required: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    education_required: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    skills: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    job_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)  # government | private
    cities: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    tags: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class JobAttachment(Base):
    __tablename__ = "job_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    s3_path: Mapped[str] = mapped_column(Text, nullable=False)
    original_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_inline_image: Mapped[bool] = mapped_column(Boolean, default=False)
    public_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class JobQnA(Base):
    __tablename__ = "job_qna"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    youtube_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    youtube_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[Optional[str]] = mapped_column(String(400), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SEOMeta(Base):
    __tablename__ = "seo_meta"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # job | page
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    slug: Mapped[Optional[str]] = mapped_column(String(400), nullable=True, index=True)
    meta_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    meta_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    focus_keyword: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    seo_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    readability_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    analysis: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    og_title: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    og_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    og_image: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    robots: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    structured_data: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    h1: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SEOMetric(Base):
    __tablename__ = "seo_metrics"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value: Mapped[float] = mapped_column(Float, default=0)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    details: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SiteSetting(Base):
    """Key-value site settings (social URLs, GSC, etc.)."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class SEOBacklink(Base):
    __tablename__ = "seo_backlinks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    anchor_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_dofollow: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class SEOKeywordRank(Base):
    """Keyword → URL ranking snapshot (from GSC or manual)."""

    __tablename__ = "seo_keyword_ranks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    keyword: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    position: Mapped[float] = mapped_column(Float, default=0)  # avg Google position
    search_page: Mapped[int] = mapped_column(Integer, default=1)  # page 1 = pos 1-10
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    ctr: Mapped[float] = mapped_column(Float, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
