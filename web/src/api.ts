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