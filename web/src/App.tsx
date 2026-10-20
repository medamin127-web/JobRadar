import { useCallback, useEffect, useRef, useState } from "react";
import {
  type Bucket,
  type Filters,
  type JobList as JobListData,
  type Overview,
  type Sort,
  type View,
  getJobs,
  getOverview,
  isReady,
  refreshRanking,
} from "./api";
import { BucketTabs, JobList, Toolbar } from "./components/JobList";
import { JobDetail } from "./components/JobDetail";
import { Sidebar } from "./components/Sidebar";

const PAGE = 100;

const DEFAULTS: Filters = {
  view: "ranking",
  bucket: "apply_with_research",
  country: null,
  q: "",
  new: false,
  remote: false,
  sort: "rank",
};

// Filters live in the address bar, so a reload or a bookmark keeps them.
function readFilters(): Filters {
  const p = new URLSearchParams(window.location.search);

  return {
    view: (p.get("view") as View) || DEFAULTS.view,
    bucket: (p.get("bucket") as Bucket | "all") || DEFAULTS.bucket,
    country: p.get("country"),
    q: p.get("q") ?? "",
    new: p.get("new") === "1",
    remote: p.get("remote") === "1",
    sort: (p.get("sort") as Sort) || DEFAULTS.sort,
  };
}

function writeFilters(f: Filters) {
  const p = new URLSearchParams();

  if (f.view !== DEFAULTS.view) p.set("view", f.view);
  if (f.bucket !== DEFAULTS.bucket) p.set("bucket", f.bucket);
  if (f.country) p.set("country", f.country);
  if (f.q) p.set("q", f.q);
  if (f.new) p.set("new", "1");
  if (f.remote) p.set("remote", "1");
  if (f.sort !== DEFAULTS.sort) p.set("sort", f.sort);

  const job = new URLSearchParams(window.location.search).get("job");
  if (job) p.set("job", job);

  const query = p.toString();
  window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
}

function timeText(iso: string | null): string {
  if (!iso) return "";
  const date = new Date(iso);
  return date.toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

export default function App() {
  const [filters, setFilters] = useState<Filters>(readFilters);
  const [search, setSearch] = useState(filters.q);
  const [limit, setLimit] = useState(PAGE);
  const [data, setData] = useState<JobListData | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [ready, setReady] = useState(false);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);
  // The open job, in the address bar too (?job=...), so a reload keeps it.
  const [openJob, setOpenJob] = useState<string | null>(
    () => new URLSearchParams(window.location.search).get("job"),
  );

  // 1. Wait until the API has ranked the jobs (20-40 s after it starts).
  useEffect(() => {
    let stop = false;

    async function poll() {
      try {
        const answer = await isReady();
        if (stop) return;
        if (answer.ready) {
          setReady(true);
          setError(null);
          return;
        }
        setError(null);
      } catch {
        if (!stop) setError("The JobRadar API is not running. Start it with: uvicorn api.server:app --port 8000");
      }
      if (!stop) window.setTimeout(poll, 1500);
    }

    poll();
    return () => {
      stop = true;
    };
  }, []);

  const update = useCallback((change: Partial<Filters>) => {
    setFilters((current) => ({ ...current, ...change }));
    setLimit(PAGE);
  }, []);

  // Search waits until you stop typing.
  useEffect(() => {
    const timer = window.setTimeout(() => {
      if (search !== filters.q) update({ q: search });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search, filters.q, update]);

  // 2. Load the list whenever a filter changes.
  useEffect(() => {
    if (!ready) return;
    writeFilters(filters);

    const id = ++request.current;
    setLoading(true);

    getJobs(filters, limit)
      .then((answer) => {
        if (id !== request.current) return;
        setData(answer);
        setError(null);
      })
      .catch((e: Error) => {
        if (id === request.current) setError(`Could not load the jobs: ${e.message}`);
      })
      .finally(() => {
        if (id === request.current) setLoading(false);
      });
  }, [filters, limit, ready]);

  useEffect(() => {
    if (ready) getOverview().then(setOverview).catch(() => undefined);
  }, [ready]);

  async function refresh() {
    setRefreshing(true);
    try {
      setOverview(await refreshRanking());
      setFilters((current) => ({ ...current }));
    } catch (e) {
      setError(`Could not rank the jobs again: ${(e as Error).message}`);
    } finally {
      setRefreshing(false);
    }
  }

  function openDetails(id: string | null) {
    setOpenJob(id);
    const p = new URLSearchParams(window.location.search);
    if (id) p.set("job", id);
    else p.delete("job");
    const query = p.toString();
    window.history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
  }

  // After you mark a job: reload the list and the counts (it may leave this view).
  function statusChanged() {
    setFilters((current) => ({ ...current }));
    getOverview().then(setOverview).catch(() => undefined);
  }

  const countryTotal = data ? data.countries.reduce((sum, c) => sum + c.count, 0) : 0;

  return (
    <div className="app">
      <header className="top">
        <h1 className="brand">JobRadar</h1>
        <input
          className="search"
          type="search"
          placeholder="Search title, company or city"
          aria-label="Search jobs"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <div className="status">
          {overview && (
            <span>
              {overview.recommended} worth applying to, {overview.new} new from the run of{" "}
              {timeText(overview.last_run)}
            </span>
          )}
          <button className="button" onClick={refresh} disabled={!ready || refreshing}>
            {refreshing ? "Ranking…" : "Rank again"}
          </button>
        </div>
      </header>

      {error && <p className="notice">{error}</p>}

      {!ready && !error && (
        <p className="waiting">Ranking your saved jobs. This takes about half a minute after the API starts.</p>
      )}

      {ready && (
        <div className="layout">
          <Sidebar
            view={filters.view}
            onView={(view) => update({ view })}
            countries={data?.countries ?? []}
            total={countryTotal}
            country={filters.country}
            onCountry={(country) => update({ country })}
          />

          <main className="main">
            <BucketTabs bucket={filters.bucket} counts={data?.buckets ?? null} onBucket={(bucket) => update({ bucket })} />
            <Toolbar
              onlyNew={filters.new}
              onlyRemote={filters.remote}
              sort={filters.sort}
              onNew={(value) => update({ new: value })}
              onRemote={(value) => update({ remote: value })}
              onSort={(sort) => update({ sort })}
            />
            <JobList
              jobs={data?.items ?? []}
              total={data?.total ?? 0}
              loading={loading}
              selected={openJob}
              onOpen={(id) => openDetails(id)}
              onMore={() => setLimit((n) => n + PAGE)}
            />
          </main>
        </div>
      )}

      {ready && openJob && (
        <JobDetail id={openJob} onClose={() => openDetails(null)} onStatusChanged={statusChanged} />
      )}
    </div>
  );
}