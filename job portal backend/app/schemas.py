from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    city: Optional[str] = None
    visitors: int
    page_views: int


class AnalyticsRealtimePage(BaseModel):
    path: str
    visitors: int
    page_views: int
    last_seen: datetime


class AnalyticsRealtimeLocation(BaseModel):
    country: str
    region: Optional[str] = None
    city: Optional[str] = None
    visitors: int
    last_seen: datetime


class AnalyticsRealtime(BaseModel):
    window_minutes: int
    active_visitors: int
    page_views: int
    pages: list[AnalyticsRealtimePage] = Field(default_factory=list)
    locations: list[AnalyticsRealtimeLocation] = Field(default_factory=list)
    generated_at: datetime


class AnalyticsDashboard(BaseModel):
    month: str
    unique_visitors: int
    page_views: int
    daily: list[AnalyticsDailyPoint] = Field(default_factory=list)
    locations: list[AnalyticsLocation] = Field(default_factory=list)


class InfrastructureStorageMetric(BaseModel):
    id: str
    name: str
    provider: str
    used_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    utilization_percent: Optional[float] = None
    object_count: Optional[int] = None
    status: str
    source: str
    detail: str


class InfrastructureComputeMetric(BaseModel):
    id: str
    name: str
    provider: str
    runtime_model: str
    cpu_used_percent: Optional[float] = None
    cpu_allocated_cores: Optional[float] = None
    memory_used_bytes: Optional[int] = None
    memory_allocated_bytes: Optional[int] = None
    memory_used_percent: Optional[float] = None
    min_replicas: Optional[int] = None
    max_replicas: Optional[int] = None
    uptime_seconds: Optional[int] = None
    status: str
    detail: str


class InfrastructureConnectionMetric(BaseModel):
    used: Optional[int] = None
    total: Optional[int] = None
    utilization_percent: Optional[float] = None
    status: str
    detail: str


class InfrastructureQuotaMetric(BaseModel):
    id: str
    name: str
    provider: str
    used: Optional[float] = None
    total: float
    unit: str
    utilization_percent: Optional[float] = None
    status: str
    detail: str


class InfrastructureCostDriver(BaseModel):
    id: str
    provider: str
    service: str
    plan: str
    metric: str
    used: Optional[float] = None
    included: Optional[float] = None
    remaining: Optional[float] = None
    unit: str
    utilization_percent: Optional[float] = None
    projected_month_end: Optional[float] = None
    current_cost_usd: Optional[float] = None
    projected_cost_usd: Optional[float] = None
    next_paid_increment_usd: Optional[float] = None
    status: str
    source: str
    detail: str


class InfrastructureProviderBilling(BaseModel):
    id: str
    provider: str
    plan: str
    subscription_fee_usd: float = 0.0
    included_credit_usd: float = 0.0
    current_usage_usd: Optional[float] = None
    current_amount_due_usd: float = 0.0
    projected_usage_usd: Optional[float] = None
    projected_amount_due_usd: Optional[float] = None
    billing_period_start: Optional[datetime] = None
    billing_period_end: Optional[datetime] = None
    next_charge_at: Optional[datetime] = None
    configured: bool = True
    status: str
    source: str
    detail: str


class InfrastructureCostItem(BaseModel):
    id: str
    name: str
    provider: str
    monthly_estimate_usd: Optional[float] = None
    configured: bool
    detail: str
    resource_id: Optional[str] = None


class InfrastructureCostHistoryPoint(BaseModel):
    month: str
    total_usd: Optional[float] = None
    paid_usd: float = 0.0
    outstanding_usd: Optional[float] = None
    provider_costs: dict[str, float] = Field(default_factory=dict)
    source: str
    estimated: bool = True
    available: bool = True


class InfrastructureCostSummary(BaseModel):
    currency: str = "USD"
    monthly_budget_usd: float
    tracked_monthly_estimate_usd: float
    current_month_cost_usd: float
    current_month_paid_usd: float
    current_outstanding_usd: float
    recorded_total_usd: float
    recorded_paid_usd: float
    recorded_outstanding_usd: float
    budget_utilization_percent: float
    unconfigured_services: int
    basis: str = "monthly_estimate"
    source: str = "configuration"
    forecast_monthly_cost_usd: Optional[float] = None
    items: list[InfrastructureCostItem] = Field(default_factory=list)
    history: list[InfrastructureCostHistoryPoint] = Field(default_factory=list)
    detail: str


class InfrastructureAlert(BaseModel):
    severity: str
    title: str
    detail: str


class InfrastructureDashboard(BaseModel):
    collected_at: datetime
    refresh_after_seconds: int
    storage: list[InfrastructureStorageMetric] = Field(default_factory=list)
    compute: list[InfrastructureComputeMetric] = Field(default_factory=list)
    database_connections: InfrastructureConnectionMetric
    quotas: list[InfrastructureQuotaMetric] = Field(default_factory=list)
    cost_drivers: list[InfrastructureCostDriver] = Field(default_factory=list)
    provider_billing: list[InfrastructureProviderBilling] = Field(default_factory=list)
    costs: InfrastructureCostSummary
    alerts: list[InfrastructureAlert] = Field(default_factory=list)


class BrandingOut(BaseModel):
    site_name: str
    site_title: str
    site_title_alignment: Literal["beside_logo", "center", "right"]
    site_header: str
    site_description: str
    footer_copyright: str
    homepage_focus_keyword: str
    homepage_meta_title: str
    homepage_meta_description: str
    homepage_meta_keywords: str
    logo_url: Optional[str] = None


class BrandingUpdateIn(BaseModel):
    # This endpoint is a PATCH-style settings update exposed as PUT. All fields
    # remain optional so an older/newer frontend can safely update the fields it
    # knows about during a rolling deployment. The database stores settings as
    # text; generous safety limits prevent accidental megabyte payloads without
    # rejecting legitimate website copy.
    site_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    site_title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    site_title_alignment: Optional[Literal["beside_logo", "center", "right"]] = None
    site_header: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    site_description: Optional[str] = Field(default=None, min_length=1, max_length=4000)
    footer_copyright: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    homepage_focus_keyword: Optional[str] = Field(default=None, max_length=500)
    homepage_meta_title: Optional[str] = Field(default=None, max_length=255)
    homepage_meta_description: Optional[str] = Field(default=None, max_length=1000)
    homepage_meta_keywords: Optional[str] = Field(default=None, max_length=4000)


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
    newspaper: str = ""
    reference_url: Optional[str] = None
    application_url: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    job_type: Optional[str] = None  # government | private
    cities: list[str] = Field(default_factory=list)
    provinces: list[str] = Field(default_factory=list)
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
    newspaper: Optional[str] = None
    reference_url: Optional[str] = None
    application_url: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    skills: Optional[list[str]] = None
    job_type: Optional[str] = None
    cities: Optional[list[str]] = None
    provinces: Optional[list[str]] = None
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
    newspaper: str = ""
    reference_url: Optional[str] = None
    application_url: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    job_type: Optional[str] = None
    cities: list[str] = Field(default_factory=list)
    provinces: list[str] = Field(default_factory=list)
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
    nationwide: bool = False
    applications_closed: bool = False


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
    provinces: list[str] = Field(default_factory=list)
    companies: list[str]
    newspapers: list[str] = Field(default_factory=list)
    employment_types: list[str]
    tags: list[str]
    job_types: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)


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
    page_type: str = "standard"
    taxonomy_value: Optional[str] = None
    is_published: bool = True
    seo: Optional[SEOFields] = None


class PageUpdate(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    page_type: Optional[str] = None
    taxonomy_value: Optional[str] = None
    is_published: Optional[bool] = None
    seo: Optional[SEOFields] = None


class PageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    content: str
    page_type: str = "standard"
    taxonomy_value: Optional[str] = None
    is_published: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DirectoryPageLinkOut(BaseModel):
    id: str
    slug: str
    title: str
    page_type: str
    taxonomy_value: str


class BlogPostIn(BaseModel):
    slug: str
    title: str
    excerpt: Optional[str] = None
    content: str = ""
    author: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_published: bool = False
    published_at: Optional[datetime] = None
    seo: Optional[SEOFields] = None


class BlogPostUpdate(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    excerpt: Optional[str] = None
    content: Optional[str] = None
    author: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[list[str]] = None
    is_published: Optional[bool] = None
    published_at: Optional[datetime] = None
    seo: Optional[SEOFields] = None


class BlogPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slug: str
    title: str
    excerpt: Optional[str] = None
    content: str
    author: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BlogPostListResponse(BaseModel):
    items: list[BlogPostOut]
    total: int
    page: int
    page_size: int
    pages: int


class BlogFiltersResponse(BaseModel):
    categories: list[str]
    tags: list[str]


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
    linkedin_url: Optional[str] = None


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
    videos_compared: int = 0
    videos_scanned: int = 0
    matched_videos: list[dict[str, Any]] = Field(default_factory=list)


class QnAFetchOptions(BaseModel):
    min_similarity_percent: Optional[int] = Field(default=None, ge=1, le=100)
    max_youtube_videos: Optional[int] = Field(default=None, ge=1, le=50)
    max_comments: Optional[int] = Field(default=None, ge=1, le=500)


class UploadOut(BaseModel):
    id: Optional[str] = None
    file_type: str
    file_size: int
    s3_path: str
    public_url: str
    original_name: Optional[str] = None
    is_inline_image: bool = False


class TaxonomyTermIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=140)
    kind: str = Field(default="category", pattern=r"^(category|tag)$")
    is_active: bool = True


class TaxonomyTermUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    slug: Optional[str] = Field(default=None, max_length=140)
    is_active: Optional[bool] = None


class TaxonomyTermOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    kind: str
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SubscriptionIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class SubscriptionResult(BaseModel):
    ok: bool = True
    status: str
    message: str


class DigestTemplateUpdate(BaseModel):
    subject_template: str = Field(..., min_length=1, max_length=300)
    body_template: str = Field(..., min_length=1, max_length=6000)


class DigestAdminSummary(BaseModel):
    subscriber_count: int = 0
    active_subscriber_count: int = 0
    subject_template: str
    body_template: str
    last_digest_at: Optional[datetime] = None
    last_digest_status: Optional[str] = None
    last_digest_job_id: Optional[str] = None
    last_digest_job_title: Optional[str] = None
    last_digest_recipients_count: int = 0
    last_digest_sent_count: int = 0
    last_digest_failed_count: int = 0
    last_digest_error: Optional[str] = None
    delivery_provider: str = "unconfigured"
    delivery_ready: bool = False
    delivery_configuration_message: str = "Email delivery is not configured."
