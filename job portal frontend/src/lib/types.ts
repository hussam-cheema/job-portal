export type JobSummary = {
  id: string;
  slug: string;
  title: string;
  description: string | null;
  published_date: string | null;
  deadline_date: string | null;
  salary_range: string | null;
  source: string | null;
  reference_url: string | null;
  application_url: string | null;
  experience_required: string | null;
  education_required: string | null;
  skills: string[];
  job_type: string | null;
  cities: string[];
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
  companies: string[];
  employment_types: string[];
  tags: string[];
  job_types?: string[];
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
  company?: string;
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
  reference_url?: string | null;
  application_url?: string | null;
  experience_required?: string | null;
  education_required?: string | null;
  skills?: string[];
  job_type?: string | null;
  cities?: string[];
  tags?: string[];
  keywords?: string | null;
  seo?: {
    focus_keyword?: string | null;
    meta_title?: string | null;
    meta_description?: string | null;
    meta_keywords?: string | null;
  };
};

export type PageItem = {
  id: string;
  slug: string;
  title: string;
  content: string;
  is_published: boolean;
  created_at?: string | null;
  updated_at?: string | null;
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
  videos_scanned: number;
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
  social?: { facebook_url?: string; youtube_url?: string; x_url?: string };
  sitemap_url?: string;
  robots_url?: string;
  robots_preview?: string;
};

export type Branding = {
  site_name: string;
  logo_url: string | null;
};

export type AnalyticsDashboard = {
  month: string;
  unique_visitors: number;
  page_views: number;
  daily: Array<{ date: string; visitors: number; page_views: number }>;
  locations: Array<{
    country: string;
    region: string | null;
    visitors: number;
    page_views: number;
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
  costs: {
    currency: string;
    monthly_budget_usd: number;
    tracked_monthly_estimate_usd: number;
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
    }>;
  };
  alerts: Array<{
    severity: string;
    title: string;
    detail: string;
  }>;
};
