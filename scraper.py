from jobspy import scrape_jobs


jobs = scrape_jobs(
    site_name=["linkedin"],
    search_term="Full Stack Developer",
    location="Germany",
    results_wanted=10,
    hours_old=72,
)

print(f"\nFound {len(jobs)} jobs\n")

print(
    jobs[
        [
            "title",
            "company",
            "location",
            "job_url",
            "date_posted",
        ]
    ].to_string(index=False)
)

jobs.to_csv("jobs.csv", index=False)

print("\nJobs saved to jobs.csv")