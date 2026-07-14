from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class LoginIn(BaseModel):
    username: str
    password: str


class PasswordChangeIn(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=12, max_length=72)


class CredentialsResetIn(BaseModel):
    token: str = Field(..., min_length=20, max_length=512)
    username: str = Field(
        ...,
        min_length=3,
        max_length=100,
        pattern=r"^[A-Za-z0-9_.-]+$",
    )
    new_password: str = Field(..., min_length=12, max_length=72)


class PasswordResetRequestOut(BaseModel):
    ok: bool = True
    message: str
    retry_after_seconds: int = 60


class AnalyticsVisitIn(BaseModel):
    visitor_id: str = Field(..., min_length=8, max_length=100)
    path: str = Field(default="/", min_length=1, max_length=500)


class AnalyticsDailyPoint(BaseModel):
    date: str
    visitors: int
    page_views: int


class AnalyticsLocation(BaseModel):
    country: str
    region: Optional[str] = None
    visitors: int
    page_views: int


class AnalyticsRealtimePage(BaseModel):
    path: str
    visitors: int
    page_views: int
    last_seen: datetime


class AnalyticsRealtime(BaseModel):
    window_minutes: int
    active_visitors: int
    page_views: int
    pages: list[AnalyticsRealtimePage] = Field(default_factory=list)
    generated_at: datetime


class AnalyticsDashboard(BaseModel):
    month: str
    unique_visitors: int
    page_views: int
    daily: list[AnalyticsDailyPoint] = Field(default_factory=list)
    locations: list[AnalyticsLocation] = Field(default_factory=list)


class BrandingOut(BaseModel):
    site_name: str
    logo_url: Optional[str] = None


class JobQnAOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    question: str
    answer: str
    source: Optional[str] = None
    youtube_url: Optional[str] = None
    youtube_title: Optional[str] = None
    created_at: Optional[datetime] = None


class JobAttachmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_type: str
    file_size: int
    s3_path: str
    original_name: Optional[str] = None
    is_inline_image: bool = False
    public_url: Optional[str] = None
    created_at: Optional[datetime] = None


class JobBase(BaseModel):
    title: str
    description: str
    published_date: datetime
    deadline_date: Optional[datetime] = None
    salary_range: Optional[str] = None
    source: Optional[str] = None
    reference_url: Optional[str] = None
    application_url: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    job_type: Optional[str] = None  # government | private
    cities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    keywords: Optional[str] = None


class SEOFields(BaseModel):
    focus_keyword: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class JobCreate(JobBase):
    seo: Optional[SEOFields] = None


class JobUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    published_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    salary_range: Optional[str] = None
    source: Optional[str] = None
    reference_url: Optional[str] = None
    application_url: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    skills: Optional[list[str]] = None
    job_type: Optional[str] = None
    cities: Optional[list[str]] = None
    tags: Optional[list[str]] = None
    keywords: Optional[str] = None
    seo: Optional[SEOFields] = None


class JobSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    description: Optional[str] = None
    published_date: Optional[datetime] = None
    deadline_date: Optional[datetime] = None
    salary_range: Optional[str] = None
    source: Optional[str] = None
    reference_url: Optional[str] = None
    application_url: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    job_type: Optional[str] = None
    cities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    keywords: Optional[str] = None
    created_at: Optional[datetime] = None
    # Compatibility aliases used by existing frontend
    company: Optional[str] = None
    location: Optional[str] = None
    city: Optional[str] = None
    province: Optional[str] = None
    employment_type: Optional[str] = None
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    currency: str = "PKR"
    category: Optional[str] = None
    application_deadline: Optional[datetime] = None
    source_type: str = "private"
    source_name: Optional[str] = None


class JobDetail(JobSummary):
    application_email: Optional[str] = None
    source_url: Optional[str] = None
    attachments: list[JobAttachmentOut] = Field(default_factory=list)
    qna: list[JobQnAOut] = Field(default_factory=list)
    resources: list[dict[str, Any]] = Field(default_factory=list)


class JobListResponse(BaseModel):
    items: list[JobSummary]
    total: int
    page: int
    page_size: int
    pages: int


class FiltersResponse(BaseModel):
    source_types: list[str]
    sectors: list[str]
    categories: list[str]
    cities: list[str]
    companies: list[str]
    employment_types: list[str]
    tags: list[str]
    job_types: list[str] = Field(default_factory=list)


class StatsResponse(BaseModel):
    total_jobs: int
    open_for_apply: int = 0  # deadline still in the future (or no deadline)
    by_source_type: dict[str, int]
    by_category: dict[str, int]
    by_city: dict[str, int]
    by_job_type: dict[str, int] = Field(default_factory=dict)
    last_updated: Optional[datetime] = None


class PageIn(BaseModel):
    slug: str
    title: str
    content: str = ""
    is_published: bool = True
    seo: Optional[SEOFields] = None


class PageUpdate(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    is_published: Optional[bool] = None
    seo: Optional[SEOFields] = None


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    content: str
    is_published: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ContactIn(BaseModel):
    name: str = Field(..., max_length=50)
    email: str = Field(..., max_length=100)
    subject: Optional[str] = Field(default=None, max_length=50)
    message: str = Field(..., max_length=300)


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    subject: Optional[str] = None
    message: str
    is_read: bool
    created_at: Optional[datetime] = None


class SEOMetaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    slug: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None
    focus_keyword: Optional[str] = None
    seo_score: Optional[float] = None
    readability_score: Optional[float] = None
    analysis: Optional[dict[str, Any]] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    canonical_url: Optional[str] = None
    robots: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None
    h1: Optional[str] = None


class SEODashboard(BaseModel):
    on_page: dict[str, Any]
    off_page: dict[str, Any]
    performance: dict[str, Any]
    jobs_with_seo: int
    pages_with_seo: int
    total_jobs: int
    total_pages: int
    issues: list[str] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    gsc: dict[str, Any] = Field(default_factory=dict)
    pagespeed: dict[str, Any] = Field(default_factory=dict)
    authority: dict[str, Any] = Field(default_factory=dict)
    backlinks: list[dict[str, Any]] = Field(default_factory=list)
    keyword_ranks: list[dict[str, Any]] = Field(default_factory=list)
    url_ranks: list[dict[str, Any]] = Field(default_factory=list)
    social: dict[str, str] = Field(default_factory=dict)
    sitemap_url: str = ""
    robots_url: str = ""
    robots_preview: str = ""


class YoastAnalyzeIn(BaseModel):
    title: str = ""
    content: str = ""
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    focus_keyword: Optional[str] = None
    slug: Optional[str] = None


class SocialSettingsIn(BaseModel):
    facebook_url: Optional[str] = None
    youtube_url: Optional[str] = None
    x_url: Optional[str] = None


class BacklinkIn(BaseModel):
    source_url: str
    target_url: Optional[str] = None
    anchor_text: Optional[str] = None
    notes: Optional[str] = None
    is_dofollow: bool = True


class QnAFetchResult(BaseModel):
    items: list[JobQnAOut] = Field(default_factory=list)
    count: int = 0
    elapsed_seconds: float = 0
    error: Optional[str] = None
    videos_scanned: int = 0


class UploadOut(BaseModel):
    id: Optional[str] = None
    file_type: str
    file_size: int
    s3_path: str
    public_url: str
    original_name: Optional[str] = None
    is_inline_image: bool = False
