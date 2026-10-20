// Calls to the Python API (api/server.py).

export type Bucket = "apply_now" | "apply_with_research" | "long_shot" | "review" | "skip";
export type View = "ranking" | "applied" | "hidden";
export type Sort = "rank" | "score" | "newest";

export interface JobSummary {
  id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  country: string | null;
  country_name: string;
  bucket: Bucket;
  reason: string | null;
  score: number;
  eligibility: "likely" | "possible" | "unlikely" | "blocked" | "unknown" | null;
  seniority: string | null;
  work_mode: string | null;
  remote_open: "yes" | "europe" | "no" | "unknown" | null;
  is_new: boolean;
  age_days: number | null;
  site: string | null;
  job_url: string | null;
  status: string;
}

export interface CountryCount {
  key: string | null;
  name: string;
  count: number;
}

export interface JobList {
  total: number;
  items: JobSummary[];
  buckets: Record<Bucket, number>;
  countries: CountryCount[];
}

export interface Overview {
  total: number;
  new: number;
  recommended: number;
  applied: number;
  last_run: string | null;
  built_at: string;
}

export interface Filters {
  view: View;
  bucket: Bucket | "all";
  country: string | null;
  q: string;
  new: boolean;
  remote: boolean;
  sort: Sort;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);

  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      // not JSON: keep the status text
    }
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

export function isReady(): Promise<{ ready: boolean }> {
  return call("/api/ready");
}

export function getOverview(): Promise<Overview> {
  return call("/api/overview");
}

export function getJobs(filters: Filters, limit: number): Promise<JobList> {
  const params = new URLSearchParams({
    view: filters.view,
    bucket: filters.bucket,
    sort: filters.sort,
    limit: String(limit),
  });

  if (filters.country) params.set("country", filters.country);
  if (filters.q.trim()) params.set("q", filters.q.trim());
  if (filters.new) params.set("new", "true");
  if (filters.remote) params.set("remote", "true");

  return call(`/api/jobs?${params}`);
}

export function refreshRanking(): Promise<Overview> {
  return call("/api/refresh", { method: "POST" });
}

export type Status = "open" | "applied" | "not_interested" | "closed";

export interface LanguageNeed {
  requirement: "required" | "optional" | "not_required";
  level_value: number | null;
  evidence: string | null;
}

/** Everything JobRadar knows about one job (GET /api/jobs/{id}). */
export interface JobDetail {
  id: string;
  title: string | null;
  company: string | null;
  location: string | null;
  country: string | null;
  country_name: string;
  job_url: string | null;
  site: string | null;
  found_on: string | null;
  date_posted: string | null;
  age_days: number | null;
  description: string | null;

  application_bucket: Bucket;
  bucket_reason: string | null;
  match_score: number | null;
  role_match_score: number | null;
  skills_match_score: number | null;
  experience_match_score: number | null;
  matched_skills: string[] | null;
  missing_skills: string[] | null;
  experience_min_years: number | null;
  seniority: string | null;

  eligibility_status: string | null;
  blockers_text: string[];
  warnings_text: string[];
  positives_text: string[];
  visa_sponsorship_status: string | null;
  visa_sponsorship_evidence: string | null;
  relocation_support: string | null;
  relocation_evidence: string | null;
  work_authorization_required: boolean | null;
  work_authorization_evidence: string | null;
  german_requirement: string | null;
  german_level_required: string | null;
  german_evidence: string | null;
  other_languages: Record<string, LanguageNeed> | null;
  local_hire: string | null;
  local_hire_evidence: string | null;
  sponsor_register: string | null;
  sponsor_register_name: string | null;
  sponsor_register_title: string | null;
  work_mode: string | null;
  remote_open: string | null;
  remote_open_evidence: string | null;

  status: Status;
  status_note: string | null;
}

export function getJob(id: string): Promise<JobDetail> {
  return call(`/api/jobs/${encodeURIComponent(id)}`);
}

export function setStatus(id: string, status: Status, note?: string): Promise<JobSummary> {
  return call(`/api/jobs/${encodeURIComponent(id)}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, note: note || null }),
  });
}