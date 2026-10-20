// Words shown to you, instead of JobRadar's internal codes.
import type { Bucket, JobSummary } from "./api";

export const BUCKETS: { key: Bucket; label: string; hint: string }[] = [
  { key: "apply_now", label: "Apply now", hint: "Good fit, and the visa or remote side looks right" },
  { key: "apply_with_research", label: "Worth a closer look", hint: "Promising; read the ad before applying" },
  { key: "long_shot", label: "Long shots", hint: "Above your level, a partial match, or the visa side is unclear" },
  { key: "review", label: "Decide yourself", hint: "The ad's text could not be read; open it to judge" },
  { key: "skip", label: "Skipped", hint: "Blocked or a poor fit" },
];

export function bucketLabel(bucket: Bucket): string {
  return BUCKETS.find((b) => b.key === bucket)?.label ?? bucket;
}

/** One short phrase about whether you can take the job from Tunisia. */
export function eligibilityText(job: JobSummary): string | null {
  if (job.country === "remote") {
    switch (job.remote_open) {
      case "yes":
        return "Hires people in Tunisia";
      case "europe":
        return "Europe only";
      case "no":
        return "Not open to Tunisia";
      default:
        return "Check where they hire";
    }
  }

  switch (job.eligibility) {
    case "likely":
      return "Visa looks possible";
    case "possible":
      return "Visa not mentioned";
    case "unlikely":
      return "Visa unlikely";
    case "blocked":
      return "Not eligible";
    default:
      return null;
  }
}

export function ageText(days: number | null): string {
  if (days === null || days === undefined) return "";
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  return `${days} days ago`;
}

export function workModeText(mode: string | null): string | null {
  if (mode === "remote") return "Remote";
  if (mode === "hybrid") return "Hybrid";
  return null;
}

const SITES: Record<string, string> = {
  linkedin: "LinkedIn",
  indeed: "Indeed",
  bayt: "Bayt",
  jaabz: "Jaabz",
  relocateme: "Relocate.me",
  arbeitnow: "Arbeitnow",
  remotive: "Remotive",
  remoteok: "RemoteOK",
  weworkremotely: "We Work Remotely",
  workingnomads: "Working Nomads",
  himalayas: "Himalayas",
  tokyodev: "TokyoDev",
  japandev: "Japan Dev",
  justjoinit: "Just Join IT",
  nofluffjobs: "No Fluff Jobs",
  adzuna: "Adzuna",
};

export function siteName(site: string | null): string {
  if (!site) return "";
  if (site.startsWith("greenhouse")) return "Company careers page";
  if (site.startsWith("lever")) return "Company careers page";
  return SITES[site] ?? site;
}