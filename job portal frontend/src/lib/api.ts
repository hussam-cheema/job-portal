import type {
  AnalyticsDashboard,
  Branding,
  ContactMessage,
  FiltersResponse,
  JobDetail,
  JobFormData,
  JobListResponse,
  JobQuery,
  PageItem,
  QnAFetchResult,
  SEODashboard,
  StatsResponse,
  TaxonomyTerm,
  SubscriptionResult,
  DigestAdminSummary,
  BlogFilters,
  BlogFormData,
  BlogListResponse,
  BlogPost,
} from "./types";
import { removeAdminSession } from "./adminSession";

const API_BASE = (
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://localhost:8000"
).replace(/\/$/, "");

const EMPTY_JOBS: JobListResponse = {
  items: [],
  total: 0,
  page: 1,
  page_size: 30,
  pages: 0,
};

const EMPTY_FILTERS: FiltersResponse = {
  source_types: [],
  sectors: ["govt", "private"],
  categories: [],
  cities: [],
  companies: [],
  employment_types: [],
  tags: [],
  job_types: ["government", "private"],
};

const EMPTY_STATS: StatsResponse = {
  total_jobs: 0,
  open_for_apply: 0,
  by_source_type: {},
  by_category: {},
  by_city: {},
  by_job_type: {},
  last_updated: null,
};

const DEFAULT_BRANDING: Branding = {
  site_name: "Pakistan Jobs Market",
  site_title: "Pakistan Jobs Market",
  site_title_alignment: "center",
  site_header: "Latest government & private job openings in Pakistan",
  site_description:
    "Discover current government and private jobs across Pakistan, search opportunities by city and category, get instant job alerts, and use practical career tools.",
  footer_copyright: "Copyrights © {year} - Pakistan Jobs Market. All rights reserved.",
  homepage_focus_keyword: "jobs in Pakistan",
  homepage_meta_title: "Jobs in Pakistan 2026 | Pakistan Jobs Market",
  homepage_meta_description:
    "Find latest government and private jobs in Pakistan by city and category. Explore curated listings, deadlines, job alerts, resume tools and career guides.",
  homepage_meta_keywords:
    "jobs in Pakistan, latest jobs in Pakistan, government jobs Pakistan, private jobs Pakistan, newspaper jobs, FPSC jobs, PPSC jobs, jobs by city, Pakistan Jobs Market",
  logo_url: "/pakistan-jobs-market-logo.png",
};

type ApiErrorBody = {
  detail?: string;
  message?: string;
};

export class ApiRequestError extends Error {
  status?: number;
  path: string;

  constructor(message: string, path: string, status?: number, options?: ErrorOptions) {
    super(message, options);
    this.name = "ApiRequestError";
    this.path = path;
    this.status = status;
  }
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  fallbackMessage = "Request failed"
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch (error) {
    throw new ApiRequestError(
      errorMessage(error, "Unable to reach the server"),
      path,
      undefined,
      { cause: error }
    );
  }

  let body: unknown = {};
  if (response.status !== 204) {
    try {
      body = await response.json();
    } catch (error) {
      if (response.ok) {
        throw new ApiRequestError(
          "The server returned an invalid response",
          path,
          response.status,
          { cause: error }
        );
      }
    }
  }

  if (!response.ok) {
    const errorBody = body as ApiErrorBody;
    const requestHeaders = new Headers(init.headers);
    const isAuthenticatedAdminRequest = Boolean(
      requestHeaders.get("Authorization") && path.startsWith("/api/admin/")
    );
    if (response.status === 401 && isAuthenticatedAdminRequest) {
      removeAdminSession();
      throw new ApiRequestError(
        "Your admin session expired. Please sign in again.",
        path,
        response.status
      );
    }
    throw new ApiRequestError(
      errorBody.detail || errorBody.message || fallbackMessage,
      path,
      response.status
    );
  }
  return body as T;
}

function buildQuery(params: JobQuery): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      sp.set(key, String(value));
    }
  });
  const qs = sp.toString();
  return qs ? `?${qs}` : "";
}

async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      next: { revalidate: 15 },
      signal: AbortSignal.timeout(10000),
    });
    if (!res.ok) {
      console.warn(`API ${res.status} ${path} — using empty fallback`);
      return fallback;
    }
    return (await res.json()) as T;
  } catch (err) {
    console.warn(`API unreachable ${path} — using empty fallback`, err);
    return fallback;
  }
}

async function getFreshJson<T>(path: string, fallback: T): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const res = await fetch(`${API_BASE}${path}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(15000),
      });
      if (res.ok) return (await res.json()) as T;
      if (res.status < 500 || attempt === 1) {
        console.warn(`API ${res.status} ${path} — using empty fallback`);
        return fallback;
      }
    } catch (err) {
      lastError = err;
      if (attempt === 1) break;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  console.warn(`API unreachable ${path} — using empty fallback`, lastError);
  return fallback;
}

export async function fetchJobs(params: JobQuery = {}): Promise<JobListResponse> {
  const page = params.page ?? 1;
  const page_size = params.page_size ?? 30;
  const fallback: JobListResponse = { ...EMPTY_JOBS, page, page_size };
  return getJson<JobListResponse>(`/api/jobs${buildQuery({ ...params, page, page_size })}`, fallback);
}

export async function fetchJob(id: string): Promise<JobDetail | null> {
  // Job details include mutable Q&A rows. Never reuse the previous response after
  // an admin refresh; also retry once for a briefly cold/revising production API.
  return getFreshJson<JobDetail | null>(`/api/jobs/${id}`, null);
}

export function fetchFilters(): Promise<FiltersResponse> {
  return getJson<FiltersResponse>("/api/filters", EMPTY_FILTERS);
}

export function fetchStats(): Promise<StatsResponse> {
  return getJson<StatsResponse>("/api/stats", EMPTY_STATS);
}

export async function fetchBranding(): Promise<Branding> {
  // Merge rather than replace so a new frontend stays compatible while an old
  // backend revision or a cached response still exposes only site_name/logo_url.
  const response = await getJson<Partial<Branding>>(
    "/api/settings/branding",
    DEFAULT_BRANDING
  );
  return { ...DEFAULT_BRANDING, ...response };
}

export async function fetchBlogPosts(params: {
  q?: string;
  category?: string;
  tag?: string;
  page?: number;
  page_size?: number;
} = {}): Promise<BlogListResponse> {
  const page = params.page || 1;
  const pageSize = params.page_size || 12;
  const query = new URLSearchParams();
  Object.entries({ ...params, page, page_size: pageSize }).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  return getFreshJson<BlogListResponse>(`/api/blog?${query}`, {
    items: [], total: 0, page, page_size: pageSize, pages: 0,
  });
}

export function fetchBlogFilters(): Promise<BlogFilters> {
  return getJson<BlogFilters>("/api/blog/filters", { categories: [], tags: [] });
}

export function fetchBlogPost(slug: string): Promise<BlogPost | null> {
  return getFreshJson<BlogPost | null>(`/api/blog/${encodeURIComponent(slug)}`, null);
}

export async function trackVisit(visitorId: string, path: string): Promise<void> {
  try {
    await fetch(`${API_BASE}/api/analytics/visit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitor_id: visitorId,
        path,
      }),
      keepalive: true,
    });
  } catch {
    // Analytics must never interrupt navigation.
  }
}

export async function fetchPage(slug: string): Promise<PageItem | null> {
  return getJson<PageItem | null>(`/api/pages/${slug}`, null);
}

export async function submitContact(data: {
  name: string;
  email: string;
  subject?: string;
  message: string;
}): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/api/contact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      return { ok: false, error: body.detail || `Failed (${res.status})` };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : "Network error" };
  }
}

export async function subscribeEmail(email: string): Promise<SubscriptionResult> {
  return requestJson<SubscriptionResult>("/api/subscriptions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email }),
  }, "Unable to subscribe this email");
}

export async function unsubscribeEmail(token: string): Promise<SubscriptionResult> {
  return requestJson<SubscriptionResult>(
    `/api/subscriptions/unsubscribe?token=${encodeURIComponent(token)}`,
    { method: "POST" },
    "Unable to unsubscribe"
  );
}

export function fetchTaxonomy(): Promise<TaxonomyTerm[]> {
  return getJson<TaxonomyTerm[]>("/api/taxonomy", []);
}

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function adminLogin(username: string, password: string) {
  return requestJson<{ access_token: string; username: string }>(
    "/api/auth/login",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    },
    "Login failed"
  );
}

export async function requestAdminPasswordReset() {
  return requestJson<{ ok: boolean; message: string; retry_after_seconds: number }>(
    "/api/auth/forgot-password",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    },
    "Unable to send the recovery email"
  );
}

export async function resetAdminCredentials(
  token: string,
  username: string,
  newPassword: string
) {
  return requestJson<{ ok: boolean; message: string }>(
    "/api/auth/reset-credentials",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token, username, new_password: newPassword }),
    },
    "Unable to reset credentials"
  );
}

export async function adminChangePassword(
  token: string,
  currentPassword: string,
  newPassword: string
) {
  return requestJson<{ ok: boolean }>(
    "/api/admin/password",
    {
      method: "PUT",
      headers: authHeaders(token),
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    },
    "Password change failed"
  );
}

export async function adminUploadLogo(token: string, file: File): Promise<Branding> {
  const form = new FormData();
  form.append("file", file);
  return requestJson<Branding>("/api/admin/settings/logo", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  }, "Upload failed");
}

export async function adminDeleteLogo(token: string): Promise<Branding> {
  return requestJson<Branding>("/api/admin/settings/logo", {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  }, "Remove failed");
}

export async function adminUpdateBranding(
  token: string,
  data: Pick<
    Branding,
    | "site_title"
    | "site_title_alignment"
    | "site_header"
    | "site_description"
    | "footer_copyright"
    | "homepage_focus_keyword"
    | "homepage_meta_title"
    | "homepage_meta_description"
    | "homepage_meta_keywords"
  >
): Promise<Branding> {
  return requestJson<Branding>("/api/admin/settings/branding", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Website settings update failed");
}

export async function adminAnalytics(
  token: string,
  month?: string
): Promise<AnalyticsDashboard> {
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  return requestJson<AnalyticsDashboard>(`/api/admin/analytics${query}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  }, "Analytics load failed");
}

export async function adminRealtimeAnalytics(token: string, windowMinutes = 5) {
  return requestJson<import("./types").AnalyticsRealtime>(
    `/api/admin/analytics/realtime?window_minutes=${windowMinutes}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" },
    "Live analytics failed"
  );
}

export async function adminCreateJob(token: string, data: JobFormData) {
  return requestJson<JobDetail>("/api/admin/jobs", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Create failed");
}

export async function adminUpdateJob(token: string, id: string, data: Partial<JobFormData>) {
  return requestJson<JobDetail>(`/api/admin/jobs/${id}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Update failed");
}

export async function adminDeleteJob(token: string, id: string) {
  return requestJson<{ ok?: boolean }>(`/api/admin/jobs/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  }, "Delete failed");
}

export async function adminFetchQnA(token: string, jobId: string): Promise<QnAFetchResult> {
  // The backend owns the configurable processing deadline. A shorter browser
  // timeout used to abort otherwise healthy 120-second requests at 60 seconds.
  return requestJson<QnAFetchResult>(`/api/admin/jobs/${jobId}/fetch-qna`, {
    method: "POST",
    headers: authHeaders(token),
  }, "QnA fetch failed");
}

export async function adminUpload(
  token: string,
  file: File,
  opts?: { jobId?: string; asAttachment?: boolean }
) {
  const fd = new FormData();
  fd.append("file", file);
  if (opts?.jobId) fd.append("job_id", opts.jobId);
  if (opts?.asAttachment) fd.append("as_attachment", "true");
  return requestJson<{
    id?: string;
    public_url: string;
    file_type: string;
    file_size: number;
    original_name?: string;
    is_inline_image: boolean;
    s3_path: string;
  }>("/api/admin/upload", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  }, "Upload failed");
}

export async function adminListPages(token: string): Promise<PageItem[]> {
  return requestJson<PageItem[]>("/api/admin/pages", {
    headers: authHeaders(token),
    cache: "no-store",
  }, "Failed to load pages");
}

export async function adminSavePage(
  token: string,
  data: {
    id?: string;
    slug: string;
    title: string;
    content: string;
    is_published?: boolean;
    seo?: {
      focus_keyword?: string | null;
      meta_title?: string | null;
      meta_description?: string | null;
      meta_keywords?: string | null;
    };
  }
) {
  const path = data.id ? `/api/admin/pages/${data.id}` : "/api/admin/pages";
  const method = data.id ? "PUT" : "POST";
  return requestJson<PageItem>(path, {
    method,
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Page save failed");
}

export async function adminSeoAction<
  T = { message?: string; [key: string]: unknown },
>(
  token: string,
  path: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  return requestJson<T>(path, {
    method,
    headers: body
      ? authHeaders(token)
      : { Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  }, "Request failed");
}

export async function adminDeletePage(token: string, id: string) {
  return requestJson<{ ok?: boolean }>(`/api/admin/pages/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  }, "Delete failed");
}

export async function adminListBlogPosts(
  token: string,
  params: { q?: string; category?: string; status?: string; page?: number } = {}
): Promise<BlogListResponse> {
  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== "") query.set(key, String(value));
  });
  const suffix = query.size ? `?${query}` : "";
  return requestJson<BlogListResponse>(`/api/admin/blog${suffix}`, {
    headers: authHeaders(token), cache: "no-store",
  }, "Failed to load blog posts");
}

export function adminGetBlogPost(token: string, id: string): Promise<BlogPost> {
  return requestJson<BlogPost>(`/api/admin/blog/${id}`, {
    headers: authHeaders(token), cache: "no-store",
  }, "Failed to load blog post");
}

export function adminSaveBlogPost(
  token: string, id: string | null, data: BlogFormData
): Promise<BlogPost> {
  return requestJson<BlogPost>(id ? `/api/admin/blog/${id}` : "/api/admin/blog", {
    method: id ? "PUT" : "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Blog post save failed");
}

export function adminDeleteBlogPost(token: string, id: string) {
  return requestJson<{ ok: boolean; id: string }>(`/api/admin/blog/${id}`, {
    method: "DELETE", headers: authHeaders(token),
  }, "Blog post delete failed");
}

export async function adminListMessages(token: string): Promise<ContactMessage[]> {
  try {
    return await requestJson<ContactMessage[]>("/api/admin/contact", {
      headers: authHeaders(token),
      cache: "no-store",
    }, "Failed to load messages");
  } catch (error) {
    console.warn("Unable to load admin messages; using an empty list", error);
    return [];
  }
}

export async function adminDeleteMessage(token: string, id: string) {
  return requestJson<{ ok?: boolean }>(`/api/admin/contact/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  }, "Delete failed");
}

export async function adminListTaxonomy(token: string): Promise<TaxonomyTerm[]> {
  return requestJson<TaxonomyTerm[]>("/api/admin/taxonomy", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  }, "Taxonomy load failed");
}

export async function adminCreateTaxonomyTerm(
  token: string,
  data: { name: string; slug?: string; is_active?: boolean }
): Promise<TaxonomyTerm> {
  return requestJson<TaxonomyTerm>("/api/admin/taxonomy", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ kind: "category", ...data }),
  }, "Create failed");
}

export async function adminUpdateTaxonomyTerm(
  token: string,
  id: string,
  data: { name?: string; slug?: string; is_active?: boolean }
): Promise<TaxonomyTerm> {
  return requestJson<TaxonomyTerm>(`/api/admin/taxonomy/${id}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Update failed");
}

export async function adminDeleteTaxonomyTerm(token: string, id: string) {
  return requestJson<{ ok?: boolean }>(`/api/admin/taxonomy/${id}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  }, "Delete failed");
}

export async function adminSubscriptionSummary(token: string): Promise<DigestAdminSummary> {
  return requestJson<DigestAdminSummary>("/api/admin/subscriptions", {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  }, "Subscription summary load failed");
}

export async function adminUpdateDigestTemplate(
  token: string,
  data: { subject_template: string; body_template: string }
): Promise<DigestAdminSummary> {
  return requestJson<DigestAdminSummary>("/api/admin/subscriptions/template", {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  }, "Save failed");
}

export async function adminSeoDashboard(token: string): Promise<SEODashboard | null> {
  try {
    return await requestJson<SEODashboard>("/api/admin/seo/dashboard", {
      headers: authHeaders(token),
      cache: "no-store",
    }, "SEO dashboard load failed");
  } catch (error) {
    console.warn("Unable to load the SEO dashboard", error);
    return null;
  }
}

export async function adminListJobs(token: string, page = 1): Promise<JobListResponse> {
  // public list is fine for admin listing
  return fetchJobs({ page, page_size: 50 });
}

export { API_BASE, EMPTY_JOBS, EMPTY_FILTERS, EMPTY_STATS };
