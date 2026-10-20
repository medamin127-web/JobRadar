import { useEffect, useRef, useState } from "react";
import { type JobDetail as Detail, type Status, getJob, setStatus } from "../api";
import { ageText, bucketLabel, siteName } from "../labels";

const CEFR = ["", "A1", "A2", "B1", "B2", "C1", "C2"];

const STATUS_TEXT: Record<Status, string> = {
  open: "In your list",
  applied: "You applied",
  not_interested: "Hidden: not interested",
  closed: "Hidden: the ad is closed",
};

const VISA_TEXT: Record<string, string> = {
  yes: "The ad offers visa sponsorship",
  maybe: "A visa may be possible",
  no: "The ad says no visa sponsorship",
  mixed: "The ad says different things about visas",
  unknown: "The ad says nothing about visas",
};

const LANGUAGE_NEED: Record<string, string> = {
  required: "Required",
  optional: "A plus",
  not_required: "Not required",
};

interface Props {
  id: string;
  onClose: () => void;
  onStatusChanged: () => void;
}

export function JobDetail({ id, onClose, onStatusChanged }: Props) {
  const [job, setJob] = useState<Detail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");
  const [wholeAd, setWholeAd] = useState(false);
  const panel = useRef<HTMLElement>(null);

  useEffect(() => {
    setJob(null);
    setError(null);
    setNoteOpen(false);
    setWholeAd(false);
    getJob(id)
      .then((data) => {
        setJob(data);
        setNote(data.status_note ?? "");
      })
      .catch((e: Error) => setError(e.message));
  }, [id]);

  // Esc closes; focus moves into the panel so the keyboard follows.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    panel.current?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function mark(status: Status, withNote?: string) {
    if (!job) return;
    setSaving(true);
    try {
      await setStatus(job.id, status, withNote);
      setJob({ ...job, status, status_note: withNote ?? null });
      setNoteOpen(false);
      onStatusChanged();
    } catch (e) {
      setError(`Could not save: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <div className="scrim" onClick={onClose} aria-hidden="true" />
      <aside className="detail" ref={panel} tabIndex={-1} aria-label="Job details">
        <button className="close" onClick={onClose} aria-label="Close the details">
          Close
        </button>

        {error && <p className="notice">{error}</p>}
        {!job && !error && <p className="waiting-small">Loading the job…</p>}

        {job && (
          <>
            <header className={`detail-head job-${job.application_bucket}`}>
              <p className="detail-bucket">
                {bucketLabel(job.application_bucket)}
                <span className="detail-score">{Math.round(job.match_score ?? 0)} / 100</span>
              </p>
              <h2>{job.title}</h2>
              <p className="detail-where">
                <strong>{job.company || "Company not given"}</strong>
                <span>{job.location || job.country_name}</span>
                {job.country && <span>{job.country_name}</span>}
              </p>
              <p className="detail-where">
                <span>{ageText(job.age_days)}</span>
                <span>on {siteName(job.found_on || job.site)}</span>
              </p>
              {job.bucket_reason && <p className="detail-reason">{job.bucket_reason}</p>}
              {job.job_url && (
                <a className="button button-solid" href={job.job_url} target="_blank" rel="noreferrer">
                  Open the ad
                </a>
              )}
            </header>

            <section className="detail-status" aria-label="Your status">
              <p>
                <strong>{STATUS_TEXT[job.status] ?? job.status}</strong>
                {job.status_note && <span className="status-note">{job.status_note}</span>}
              </p>

              {job.status === "open" && !noteOpen && (
                <div className="status-buttons">
                  <button className="button" disabled={saving} onClick={() => setNoteOpen(true)}>
                    Mark as applied
                  </button>
                  <button className="button button-quiet" disabled={saving} onClick={() => mark("not_interested")}>
                    Not interested
                  </button>
                  <button className="button button-quiet" disabled={saving} onClick={() => mark("closed")}>
                    The ad is closed
                  </button>
                </div>
              )}

              {job.status === "open" && noteOpen && (
                <form
                  className="note-form"
                  onSubmit={(event) => {
                    event.preventDefault();
                    mark("applied", note.trim());
                  }}
                >
                  <label htmlFor="note">Note for yourself (optional): date, contact, salary asked…</label>
                  <input id="note" value={note} onChange={(e) => setNote(e.target.value)} autoFocus />
                  <div className="status-buttons">
                    <button className="button" type="submit" disabled={saving}>
                      Save as applied
                    </button>
                    <button className="button button-quiet" type="button" onClick={() => setNoteOpen(false)}>
                      Cancel
                    </button>
                  </div>
                </form>
              )}

              {job.status !== "open" && (
                <div className="status-buttons">
                  <button className="button button-quiet" disabled={saving} onClick={() => mark("open")}>
                    Move back to my list
                  </button>
                </div>
              )}
            </section>

            <Signals job={job} />
            <Languages job={job} />
            <Fit job={job} />

            <section className="detail-section">
              <h3>The ad</h3>
              {job.description ? (
                <>
                  <div className={wholeAd ? "ad-text" : "ad-text is-short"}>{job.description}</div>
                  {!wholeAd && job.description.length > 1500 && (
                    <button className="more" onClick={() => setWholeAd(true)}>
                      Show the whole ad
                    </button>
                  )}
                </>
              ) : (
                <p className="muted">JobRadar could not read the ad's text. Open the ad to read it.</p>
              )}
            </section>
          </>
        )}
      </aside>
    </>
  );
}

function Evidence({ text }: { text: string | null }) {
  if (!text || text.startsWith("No clear") || text.startsWith("No job description")) return null;
  return <q className="evidence">{text}</q>;
}

function Signals({ job }: { job: Detail }) {
  const remote = job.country === "remote";

  return (
    <section className="detail-section">
      <h3>{remote ? "Can you do it from Tunisia?" : "Can you get there?"}</h3>

      {(job.blockers_text.length > 0 || job.warnings_text.length > 0 || job.positives_text.length > 0) && (
        <ul className="signals">
          {job.blockers_text.map((text) => (
            <li key={text} className="signal signal-no">{text}</li>
          ))}
          {job.warnings_text.map((text) => (
            <li key={text} className="signal signal-warn">{text}</li>
          ))}
          {job.positives_text.map((text) => (
            <li key={text} className="signal signal-yes">{text}</li>
          ))}
        </ul>
      )}

      <dl className="facts">
        {remote ? (
          <>
            <dt>Hires in Tunisia</dt>
            <dd>
              {{ yes: "Yes", no: "No", europe: "Europe only", unknown: "Unclear" }[job.remote_open ?? "unknown"] ?? "Unclear"}
              <Evidence text={job.remote_open_evidence} />
            </dd>
          </>
        ) : (
          <>
            <dt>Visa</dt>
            <dd>
              {VISA_TEXT[job.visa_sponsorship_status ?? "unknown"] ?? job.visa_sponsorship_status}
              <Evidence text={job.visa_sponsorship_evidence} />
            </dd>
          </>
        )}

        {job.relocation_support && job.relocation_support !== "unknown" && (
          <>
            <dt>Relocation</dt>
            <dd>
              {job.relocation_support === "yes" ? "Help with relocation" : "No relocation help"}
              {/* Often the same sentence as the visa one: quote it once. */}
              {job.relocation_evidence !== job.visa_sponsorship_evidence && <Evidence text={job.relocation_evidence} />}
            </dd>
          </>
        )}

        {job.work_authorization_required && (
          <>
            <dt>Work permit</dt>
            <dd>
              You must already be allowed to work there
              <Evidence text={job.work_authorization_evidence} />
            </dd>
          </>
        )}

        {job.local_hire && (
          <>
            <dt>Who can apply</dt>
            <dd>
              {{ nationals_only: "Citizens of that country only", in_country_only: "People already living there", preferred: "Prefers people already living there" }[job.local_hire] ?? job.local_hire}
              <Evidence text={job.local_hire_evidence} />
            </dd>
          </>
        )}

        {job.sponsor_register && (
          <>
            <dt>Official sponsor list</dt>
            <dd>
              {job.sponsor_register === "listed"
                ? `Listed as “${job.sponsor_register_name}”`
                : "Not found (it may be listed under another legal name)"}
              <span className="muted"> ({job.sponsor_register_title})</span>
            </dd>
          </>
        )}
      </dl>
    </section>
  );
}

function Languages({ job }: { job: Detail }) {
  const others = Object.entries(job.other_languages ?? {});
  const german = job.german_requirement && job.german_requirement !== "none_mentioned";

  if (!german && others.length === 0) return null;

  return (
    <section className="detail-section">
      <h3>Languages</h3>
      <dl className="facts">
        {german && (
          <>
            <dt>German</dt>
            <dd>
              {{ required: "Required", implied: "Probably needed (the ad is in German)", optional: "A plus", not_required: "Not required" }[job.german_requirement ?? ""] ?? job.german_requirement}
              {job.german_level_required && ` (${job.german_level_required})`}
              <Evidence text={job.german_evidence} />
            </dd>
          </>
        )}
        {others.map(([name, need]) => (
          <div key={name} className="fact-pair">
            <dt>{name}</dt>
            <dd>
              {LANGUAGE_NEED[need.requirement] ?? need.requirement}
              {need.requirement === "required" && need.level_value ? ` (${CEFR[need.level_value] ?? ""})` : ""}
              <Evidence text={need.evidence} />
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function Fit({ job }: { job: Detail }) {
  const matched = job.matched_skills ?? [];
  const missing = job.missing_skills ?? [];

  return (
    <section className="detail-section">
      <h3>How you fit</h3>
      <dl className="facts">
        <dt>Experience asked</dt>
        <dd>{job.experience_min_years != null ? `${job.experience_min_years}+ years` : "Not stated"}</dd>
        <dt>Level</dt>
        <dd>{job.seniority ?? "Not stated"}</dd>
        {(matched.length > 0 || missing.length > 0) && (
          <>
            <dt>Skills you have</dt>
            <dd>{matched.length ? matched.join(", ") : "None of the skills it names"}</dd>
            {missing.length > 0 && (
              <>
                <dt>Skills to check</dt>
                <dd>{missing.join(", ")}</dd>
              </>
            )}
          </>
        )}
      </dl>
    </section>
  );
}