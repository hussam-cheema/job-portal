export type JobSummary = {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  published_date: string | null;
  deadline_date: string | null;
  salary_range: string | null;
  source: string | null;
  newspaper: string | null;
  reference_url: string | null;
  application_url: string | null;
  experience_required: string | null;
  education_required: string | null;
  skills: string[];
  job_type: string | null;
  cities: string[];
  provinces: string[];
  tags: string[];
  keywords: string | null;
  created_at: string | null;
  // compatibility
  company: string | null;
  location: string | null;
  city: string | null;
  province: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  currency: string;
  category: string | null;
  application_deadline: string | null;
  source_type: string;
  source_name: string | null;
  nationwide?: boolean;
  applications_closed?: boolean;
};

export type TaxonomyTerm = {
  id: string;
  kind: string;
  name: string;
  slug: string;
  province?: string | null;
  is_active: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type SubscriptionResult = {
  status: "subscribed" | "already_subscribed" | "unsubscribed" | "not_subscribed";
  message: string;
};

export type DigestAdminSummary = {
  subscriber_count: number;
  active_subscriber_count: number;
  subject_template: string;
  body_template: string;
  last_digest_at: string | null;
  last_digest_status: string | null;
  last_digest_job_id: string | null;
  last_digest_job_title: string | null;
  last_digest_recipients_count: number;
  last_digest_sent_count: number;
  last_digest_failed_count: number;
  last_digest_error: string | null;
  // Optional during a rolling deployment: older API revisions did not expose
  // delivery readiness, so the admin UI supplies a safe, actionable fallback.
  delivery_provider?: string;
  delivery_ready?: boolean;
  delivery_configuration_message?: string;
  student_api_access?: SubscriberApiAccessAdmin[];
};

export type SubscriberApiAccessAdmin = {
  subscriber_email: string;
  subscriber_is_active: boolean;
  key_prefix: string | null;
  is_key_active: boolean;
  quota_total: number;
  requests_used: number;
  requests_remaining: number;
  verification_pending: boolean;
  verification_expires_at: string | null;
  verified_at: string | null;
  api_key_created_at: string | null;
  api_key_last_used_at: string | null;
};

export type StudentApiCodeRequest = {
  status: "code_sent" | "subscription_required";
  message: string;
  expires_in_seconds?: number | null;
  retry_after_seconds?: number | null;
};

export type StudentApiKey = {
  status: "verified";
  message: string;
  api_key: string;
  key_prefix: string;
  quota_total: number;
  requests_used: number;
  requests_remaining: number;
  documentation_url: string;
};

export type QnAItem = {
  question: string;
  answer: string;
  source?: string;
  youtube_url?: string;
  youtube_title?: string;
};

export type JobQnA = {
  id: string;
  job_id: string;
  question: string;
  answer: string;
  source?: string | null;
  youtube_url?: string | null;
  youtube_title?: string | null;
  created_at?: string | null;
};

export type JobAttachment = {
  id: string;
  job_id: string;
  file_type: string;
  file_size: number;
  s3_path: string;
  original_name?: string | null;
  is_inline_image: boolean;
  public_url?: string | null;
  created_at?: string | null;
};

export type JobResource = {
  id: string;
  job_id: string;
  resource_type: string;
  title: string;
  url: string;
  description: string | null;
  file_type: string | null;
  content_text?: string | null;
  meta?: {
    qna_items?: QnAItem[];
    qna_count?: number;
    [key: string]: unknown;
  } | null;
  created_at: string | null;
};

export type JobDetail = JobSummary & {
  application_email: string | null;
  source_url: string | null;
  attachments: JobAttachment[];
  qna: JobQnA[];
  resources: JobResource[];
};

export type JobListResponse = {
  items: JobSummary[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type FiltersResponse = {
  source_types: string[];
  sectors: string[];
  categories: string[];
  cities: string[];
  provinces: string[];
  companies: string[];
  newspapers: string[];
  employment_types: string[];
  tags: string[];
  job_types?: string[];
  qualifications?: string[];
};

export type StatsResponse = {
  total_jobs: number;
  open_for_apply?: number;
  by_source_type: Record<string, number>;
  by_category: Record<string, number>;
  by_city: Record<string, number>;
  by_job_type?: Record<string, number>;
  last_updated: string | null;
};

export type JobQuery = {
  q?: string;
  source_type?: string;
  sector?: string;
  category?: string;
  city?: string;
  province?: string;
  company?: string;
  newspaper?: string;
  education?: string;
  employment_type?: string;
  tag?: string;
  job_type?: string;
  date?: string;
  date_from?: string;
  date_to?: string;
  page?: number;
  page_size?: number;
};

export type JobFormData = {
  title: string;
  description: string;
  published_date: string;
  deadline_date?: string | null;
  salary_range?: string | null;
  source?: string | null;
  newspaper?: string | null;
  reference_url?: string | null;
  application_url?: string | null;
  experience_required?: string | null;
  education_required?: string | null;
  skills?: string[];
  job_type?: string | null;
  cities?: string[];
  provinces?: string[];
  tags?: string[];
  keywords?: string | null;
  seo?: {
    focus_keyword?: string | null;
    meta_title?: string | null;
    meta_description?: string | null;
    meta_keywords?: string | null;
  };
};

export type PageType =
  | "standard"
  | "city"
  | "province"
  | "category"
  | "organization"
  | "newspaper";

export type PageItem = {
  id: string;
  slug: string;
  title: string;
  content: string;
  page_type: PageType;
  taxonomy_value?: string | null;
  is_published: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type DirectoryPageLink = Pick<
  PageItem,
  "id" | "slug" | "title" | "page_type"
> & {
  page_type: Exclude<PageType, "standard">;
  taxonomy_value: string;
};

export type PublicSeoMeta = {
  meta_title?: string | null;
  meta_description?: string | null;
  meta_keywords?: string | null;
  og_title?: string | null;
  og_description?: string | null;
  og_image?: string | null;
};

export type ToolKind =
  | "content"
  | "tax_calculator"
  | "government_salary_calculator"
  | "cgpa_calculator"
  | "document_converter"
  | "image_watermark"
  | "resume_builder"
  | "cover_letter"
  | "student_api";

export type ToolPage = {
  id: string;
  category_id: string;
  slug: string;
  title: string;
  content: string;
  tool_kind: ToolKind;
  sort_order: number;
  is_published: boolean;
  created_at?: string | null;
  updated_at?: string | null;
};

export type ToolCategory = {
  id: string;
  slug: string;
  title: string;
  content: string;
  icon_key: string;
  color_index: number;
  sort_order: number;
  is_published: boolean;
  tools: ToolPage[];
  created_at?: string | null;
  updated_at?: string | null;
};

export type ToolAdminResponse = {
  categories: ToolCategory[];
  tools: ToolPage[];
};

export type ToolAnalyticsRow = {
  id: string;
  category_id: string;
  category_title: string;
  slug: string;
  title: string;
  tool_kind: ToolKind;
  is_published: boolean;
  opens: number;
  uses: number;
};

export type ToolAnalytics = {
  month: string;
  timezone: string;
  total_opens: number;
  total_uses: number;
  tools: ToolAnalyticsRow[];
  generated_at: string;
};

export type DocumentConversionStatus =
  | "queued"
  | "converting"
  | "verifying"
  | "completed"
  | "failed";

export type DocumentConversionJob = {
  job_id: string;
  status: DocumentConversionStatus;
  progress: number;
  stage: string;
  input_format: "pdf" | "docx";
  output_format: "pdf" | "docx";
  output_filename: string;
  estimated_seconds_remaining?: number | null;
  error?: string | null;
  created_at: string;
  expires_at: string;
};

export type DocumentConversionJobCreated = DocumentConversionJob & {
  access_token: string;
};

export type ToolSEOFields = {
  focus_keyword?: string | null;
  meta_title?: string | null;
  meta_description?: string | null;
  meta_keywords?: string | null;
};

export type BlogPost = {
  id: string;
  slug: string;
  title: string;
  excerpt?: string | null;
  content: string;
  author?: string | null;
  category?: string | null;
  tags: string[];
  is_published: boolean;
  published_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type BlogListResponse = {
  items: BlogPost[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type BlogFilters = { categories: string[]; tags: string[] };

export type DirectoryValue = {
  name: string;
  slug: string;
  count: number;
  page_id?: string;
  taxonomy_value?: string | null;
};

export type SiteDirectory = {
  generated_at: string | null;
  jobs: Array<{
    id: string;
    slug: string;
    title: string;
    published_date: string | null;
    deadline_date: string | null;
    applications_closed: boolean;
    organization: string | null;
    newspaper: string | null;
    salary_range: string | null;
    education_required: string | null;
    experience_required: string | null;
    job_type: string | null;
    category: string | null;
    cities: string[];
    provinces: string[];
    tags: string[];
  }>;
  blogs: Array<{
    id: string;
    slug: string;
    title: string;
    published_at: string | null;
    category: string | null;
    tags: string[];
  }>;
  pages: Array<{
    id: string;
    slug: string;
    title: string;
    path: string;
    page_type?: PageType;
    taxonomy_value?: string | null;
  }>;
  taxonomies: {
    job_categories: DirectoryValue[];
    job_tags: DirectoryValue[];
    cities: DirectoryValue[];
    provinces: DirectoryValue[];
    organizations: DirectoryValue[];
    newspapers: DirectoryValue[];
    qualifications: DirectoryValue[];
    blog_categories: DirectoryValue[];
    blog_tags: DirectoryValue[];
  };
};

export type BlogFormData = Omit<BlogPost, "id" | "created_at" | "updated_at"> & {
  seo?: {
    focus_keyword?: string | null;
    meta_title?: string | null;
    meta_description?: string | null;
    meta_keywords?: string | null;
  };
};

export type ContactMessage = {
  id: string;
  name: string;
  email: string;
  subject?: string | null;
  message: string;
  is_read: boolean;
  created_at?: string | null;
};

export type QnAFetchResult = {
  items: JobQnA[];
  count: number;
  elapsed_seconds: number;
  error?: string | null;
  videos_compared: number;
  videos_scanned: number;
  matched_videos: QnAMatchedVideo[];
};

export type QnAMatchedVideo = {
  title: string;
  url: string;
  similarity_percent: number;
  has_transcript: boolean;
  comment_threads: number;
};

export type QnAFetchOptions = {
  min_similarity_percent?: number;
  max_youtube_videos?: number;
  max_comments?: number;
};

export type SEODashboard = {
  on_page: Record<string, unknown>;
  off_page: Record<string, unknown>;
  performance: Record<string, unknown>;
  jobs_with_seo: number;
  pages_with_seo: number;
  total_jobs: number;
  total_pages: number;
  issues: string[];
  metrics: Array<Record<string, unknown>>;
  gsc?: Record<string, unknown>;
  pagespeed?: Record<string, unknown>;
  authority?: Record<string, unknown>;
  backlinks?: Array<Record<string, unknown>>;
  keyword_ranks?: Array<Record<string, unknown>>;
  url_ranks?: Array<Record<string, unknown>>;
  social?: {
    facebook_url?: string;
    youtube_url?: string;
    x_url?: string;
    linkedin_url?: string;
  };
  sitemap_url?: string;
  robots_url?: string;
  robots_preview?: string;
};

export type SocialSettings = {
  facebook_url: string;
  youtube_url: string;
  x_url: string;
  linkedin_url: string;
};

export type Branding = {
  site_name: string;
  site_title: string;
  site_title_alignment: "beside_logo" | "center" | "right";
  site_title_header: string;
  site_header: string;
  site_description: string;
  footer_copyright: string;
  homepage_focus_keyword: string;
  homepage_meta_title: string;
  homepage_meta_description: string;
  homepage_meta_keywords: string;
  logo_url: string | null;
};

export type AnalyticsDashboard = {
  month: string;
  timezone: string;
  unique_visitors: number;
  page_views: number;
  daily: Array<{ date: string; visitors: number; page_views: number }>;
  locations: Array<{
    country: string;
    region: string | null;
    city: string | null;
    visitors: number;
    page_views: number;
  }>;
  generated_at: string;
};

export type AnalyticsRealtime = {
  window_minutes: number;
  active_visitors: number;
  page_views: number;
  generated_at: string;
  pages: Array<{
    path: string;
    visitors: number;
    page_views: number;
    last_seen: string;
  }>;
  locations: Array<{
    country: string;
    region: string | null;
    city: string | null;
    visitors: number;
    last_seen: string;
  }>;
};

export type InfrastructureStorageMetric = {
  id: string;
  name: string;
  provider: string;
  used_bytes: number | null;
  total_bytes: number | null;
  utilization_percent: number | null;
  object_count: number | null;
  status: string;
  source: string;
  detail: string;
};

export type InfrastructureComputeMetric = {
  id: string;
  name: string;
  provider: string;
  runtime_model: string;
  cpu_used_percent: number | null;
  cpu_allocated_cores: number | null;
  memory_used_bytes: number | null;
  memory_allocated_bytes: number | null;
  memory_used_percent: number | null;
  min_replicas: number | null;
  max_replicas: number | null;
  uptime_seconds: number | null;
  status: string;
  detail: string;
};

export type InfrastructureDashboard = {
  collected_at: string;
  refresh_after_seconds: number;
  storage: InfrastructureStorageMetric[];
  compute: InfrastructureComputeMetric[];
  database_connections: {
    used: number | null;
    total: number | null;
    utilization_percent: number | null;
    status: string;
    detail: string;
  };
  quotas: Array<{
    id: string;
    name: string;
    provider: string;
    used: number | null;
    total: number;
    unit: string;
    utilization_percent: number | null;
    status: string;
    detail: string;
  }>;
  cost_drivers: Array<{
    id: string;
    provider: string;
    service: string;
    plan: string;
    metric: string;
    used: number | null;
    included: number | null;
    remaining: number | null;
    unit: string;
    utilization_percent: number | null;
    projected_month_end: number | null;
    current_cost_usd: number | null;
    projected_cost_usd: number | null;
    next_paid_increment_usd: number | null;
    status: string;
    source: string;
    detail: string;
  }>;
  provider_billing: Array<{
    id: string;
    provider: string;
    plan: string;
    subscription_fee_usd: number;
    included_credit_usd: number;
    current_usage_usd: number | null;
    current_amount_due_usd: number;
    projected_usage_usd: number | null;
    projected_amount_due_usd: number | null;
    billing_period_start: string | null;
    billing_period_end: string | null;
    next_charge_at: string | null;
    configured: boolean;
    status: string;
    source: string;
    detail: string;
  }>;
  costs: {
    currency: string;
    monthly_budget_usd: number;
    tracked_monthly_estimate_usd: number;
    current_month_cost_usd?: number;
    current_month_paid_usd?: number;
    current_outstanding_usd?: number;
    recorded_total_usd?: number;
    recorded_paid_usd?: number;
    recorded_outstanding_usd?: number;
    budget_utilization_percent: number;
    unconfigured_services: number;
    detail: string;
    items: Array<{
      id: string;
      name: string;
      provider: string;
      monthly_estimate_usd: number | null;
      configured: boolean;
      detail: string;
      resource_id?: string | null;
    }>;
    history: Array<{
      month: string;
      total_usd: number | null;
      paid_usd?: number;
      outstanding_usd?: number | null;
      provider_costs: Record<string, number>;
      source: string;
      estimated: boolean;
      available: boolean;
    }>;
    basis: string;
    source: string;
    forecast_monthly_cost_usd: number | null;
  };
  alerts: Array<{
    severity: string;
    title: string;
    detail: string;
  }>;
};
