# `sql/` — BigQuery Templates

Templates that build the candidate pull-request table from GH Archive in
BigQuery. They are an alternative to the local `download-gharchive` /
`candidates-from-gharchive` CLI path.

| File | Purpose |
| --- | --- |
| [`01_candidate_prs.sql`](01_candidate_prs.sql) | Builds the candidate PR table for a target time window. |
| [`02_candidate_stats.sql`](02_candidate_stats.sql) | Inspects distribution and samples the candidate table. |

After running `01_candidate_prs.sql`, export the result to CSV and place it in
[`data/candidates/`](../data/README.md) for the enrichment step.
