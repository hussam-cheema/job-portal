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
} from "./types";

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

export async function fetchJobs(params: JobQuery = {}): Promise<JobListResponse> {
  const page = params.page ?? 1;
  const page_size = params.page_size ?? 30;
  const fallback: JobListResponse = { ...EMPTY_JOBS, page, page_size };
  return getJson<JobListResponse>(`/api/jobs${buildQuery({ ...params, page, page_size })}`, fallback);
}

export async function fetchJob(id: string): Promise<JobDetail | null> {
  return getJson<JobDetail | null>(`/api/jobs/${id}`, null);
}

export function fetchFilters(): Promise<FiltersResponse> {
  return getJson<FiltersResponse>("/api/filters", EMPTY_FILTERS);
}

export function fetchStats(): Promise<StatsResponse> {
  return getJson<StatsResponse>("/api/stats", EMPTY_STATS);
}

export function fetchBranding(): Promise<Branding> {
  return getJson<Branding>("/api/settings/branding", {
    site_name: "PakJobs",
    logo_url: null,
  });
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

function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

export async function adminLogin(username: string, password: string) {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || "Login failed");
  }
  return res.json() as Promise<{ access_token: string; username: string }>;
}

export async function requestAdminPasswordReset() {
  const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || "Unable to send the recovery email");
  }
  return body as { ok: boolean; message: string; retry_after_seconds: number };
}

export async function resetAdminCredentials(
  token: string,
  username: string,
  newPassword: string
) {
  const res = await fetch(`${API_BASE}/api/auth/reset-credentials`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token, username, new_password: newPassword }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body.detail || "Unable to reset credentials");
  }
  return body as { ok: boolean; message: string };
}

export async function adminChangePassword(
  token: string,
  currentPassword: string,
  newPassword: string
) {
  const res = await fetch(`${API_BASE}/api/admin/password`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!res.ok) {
    throw new Error((await res.json().catch(() => ({}))).detail || "Password change failed");
  }
  return res.json() as Promise<{ ok: boolean }>;
}

export async function adminUploadLogo(token: string, file: File): Promise<Branding> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/admin/settings/logo`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: form,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Upload failed");
  return res.json();
}

export async function adminDeleteLogo(token: string): Promise<Branding> {
  const res = await fetch(`${API_BASE}/api/admin/settings/logo`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Remove failed");
  return res.json();
}

export async function adminAnalytics(
  token: string,
  month?: string
): Promise<AnalyticsDashboard> {
  const query = month ? `?month=${encodeURIComponent(month)}` : "";
  const res = await fetch(`${API_BASE}/api/admin/analytics${query}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Load failed");
  return res.json();
}

export async function adminRealtimeAnalytics(token: string, windowMinutes = 5) {
  const res = await fetch(
    `${API_BASE}/api/admin/analytics/realtime?window_minutes=${windowMinutes}`,
    { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" }
  );
  if (!res.ok) {
    throw new Error((await res.json().catch(() => ({}))).detail || "Live analytics failed");
  }
  return res.json() as Promise<import("./types").AnalyticsRealtime>;
}

export async function adminCreateJob(token: string, data: JobFormData) {
  const res = await fetch(`${API_BASE}/api/admin/jobs`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Create failed");
  return res.json() as Promise<JobDetail>;
}

export async function adminUpdateJob(token: string, id: string, data: Partial<JobFormData>) {
  const res = await fetch(`${API_BASE}/api/admin/jobs/${id}`, {
    method: "PUT",
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Update failed");
  return res.json() as Promise<JobDetail>;
}

export async function adminDeleteJob(token: string, id: string) {
  const res = await fetch(`${API_BASE}/api/admin/jobs/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Delete failed");
  return res.json();
}

export async function adminFetchQnA(token: string, jobId: string): Promise<QnAFetchResult> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/admin/jobs/${jobId}/fetch-qna`, {
      method: "POST",
      headers: authHeaders(token),
      signal: AbortSignal.timeout(60000),
    });
  } catch (error) {
    if (error instanceof DOMException && ["AbortError", "TimeoutError"].includes(error.name)) {
      throw new Error("YouTube Q&A processing reached the 60-second limit.");
    }
    throw error;
  }
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "QnA fetch failed");
  return res.json();
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
  const res = await fetch(`${API_BASE}/api/admin/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: fd,
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Upload failed");
  return res.json() as Promise<{
    id?: string;
    public_url: string;
    file_type: string;
    file_size: number;
    original_name?: string;
    is_inline_image: boolean;
    s3_path: string;
  }>;
}

export async function adminListPages(token: string): Promise<PageItem[]> {
  const res = await fetch(`${API_BASE}/api/admin/pages`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
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
  const url = data.id ? `${API_BASE}/api/admin/pages/${data.id}` : `${API_BASE}/api/admin/pages`;
  const method = data.id ? "PUT" : "POST";
  const res = await fetch(url, {
    method,
    headers: authHeaders(token),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Page save failed");
  return res.json() as Promise<PageItem>;
}

export async function adminSeoAction(token: string, path: string, method = "GET", body?: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body
      ? authHeaders(token)
      : { Authorization: `Bearer ${token}` },
    body: body ? JSON.stringify(body) : undefined,
    cache: "no-store",
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Request failed");
  return res.json();
}

export async function adminDeletePage(token: string, id: string) {
  const res = await fetch(`${API_BASE}/api/admin/pages/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || "Delete failed");
  return res.json();
}

export async function adminListMessages(token: string): Promise<ContactMessage[]> {
  const res = await fetch(`${API_BASE}/api/admin/contact`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) return [];
  return res.json();
}

export async function adminDeleteMessage(token: string, id: string) {
  const res = await fetch(`${API_BASE}/api/admin/contact/${id}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Delete failed");
  return res.json();
}

export async function adminSeoDashboard(token: string): Promise<SEODashboard | null> {
  const res = await fetch(`${API_BASE}/api/admin/seo/dashboard`, {
    headers: authHeaders(token),
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export async function adminListJobs(token: string, page = 1): Promise<JobListResponse> {
  // public list is fine for admin listing
  return fetchJobs({ page, page_size: 50 });
}

export { API_BASE, EMPTY_JOBS, EMPTY_FILTERS, EMPTY_STATS };
