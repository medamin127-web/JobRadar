import type { Bucket, JobSummary, Sort } from "../api";
import { BUCKETS, ageText, eligibilityText, siteName, workModeText } from "../labels";

interface TabsProps {
  bucket: Bucket | "all";
  counts: Record<Bucket, number> | null;
  onBucket: (bucket: Bucket | "all") => void;
}

export function BucketTabs({ bucket, counts, onBucket }: TabsProps) {
  const all = counts ? Object.values(counts).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="tabs" role="tablist" aria-label="How good a match">
      {BUCKETS.map((item) => (
        <button
          key={item.key}
          role="tab"
          title={item.hint}
          aria-selected={bucket === item.key}
          className={`tab tab-${item.key}${bucket === item.key ? " is-on" : ""}`}
          onClick={() => onBucket(item.key)}
        >
          {item.label}
          <span className="tab-count">{counts ? counts[item.key] : ""}</span>
        </button>
      ))}
      <button
        role="tab"
        aria-selected={bucket === "all"}
        className={`tab tab-all${bucket === "all" ? " is-on" : ""}`}
        onClick={() => onBucket("all")}
      >
        All
        <span className="tab-count">{counts ? all : ""}</span>
      </button>
    </div>
  );
}

interface ToolbarProps {
  onlyNew: boolean;
  onlyRemote: boolean;
  sort: Sort;
  onNew: (value: boolean) => void;
  onRemote: (value: boolean) => void;
  onSort: (value: Sort) => void;
}

export function Toolbar({ onlyNew, onlyRemote, sort, onNew, onRemote, onSort }: ToolbarProps) {
  return (
    <div className="toolbar">
      <label className="check">
        <input type="checkbox" checked={onlyNew} onChange={(e) => onNew(e.target.checked)} />
        From the latest run
      </label>
      <label className="check">
        <input type="checkbox" checked={onlyRemote} onChange={(e) => onRemote(e.target.checked)} />
        Remote
      </label>
      <label className="sort">
        Order
        <select value={sort} onChange={(e) => onSort(e.target.value as Sort)}>
          <option value="rank">Best first</option>
          <option value="score">Highest skills match</option>
          <option value="newest">Newest first</option>
        </select>
      </label>
    </div>
  );
}

function JobRow({ job }: { job: JobSummary }) {
  const eligibility = eligibilityText(job);
  const mode = workModeText(job.work_mode);

  return (
    <li className={`job job-${job.bucket}`}>
      <div className="score" title="How well the job matches your skills and experience, out of 100">
        {job.score}
      </div>
      <div className="job-body">
        <div className="job-head">
          <a className="job-title" href={job.job_url ?? undefined} target="_blank" rel="noreferrer">
            {job.title || "Untitled job"}
          </a>
          {job.is_new && <span className="new">New</span>}
        </div>
        <div className="job-meta">
          <span className="company">{job.company || "Company not given"}</span>
          <span>{job.location || job.country_name}</span>
          {mode && <span>{mode}</span>}
          {job.seniority && <span>{job.seniority}</span>}
        </div>
        {job.reason && <p className="reason">{job.reason}</p>}
      </div>
      <div className="job-side">
        {eligibility && <span className={`elig elig-${job.eligibility}`}>{eligibility}</span>}
        <span className="when">{ageText(job.age_days)}</span>
        <span className="site">{siteName(job.site)}</span>
      </div>
    </li>
  );
}

interface ListProps {
  jobs: JobSummary[];
  total: number;
  loading: boolean;
  onMore: () => void;
}

export function JobList({ jobs, total, loading, onMore }: ListProps) {
  if (!loading && jobs.length === 0) {
    return (
      <p className="empty">
        No jobs match these filters. Try another country or tab, or clear the search.
      </p>
    );
  }

  return (
    <>
      <ol className={loading ? "jobs is-loading" : "jobs"} aria-busy={loading}>
        {jobs.map((job) => (
          <JobRow key={job.id} job={job} />
        ))}
      </ol>
      {jobs.length < total && (
        <button className="more" onClick={onMore} disabled={loading}>
          Show {Math.min(100, total - jobs.length)} more of {total - jobs.length}
        </button>
      )}
    </>
  );
}