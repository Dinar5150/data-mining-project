-- Replace {{ candidate_table }} before running.

SELECT COUNT(*) AS candidates
FROM `{{ candidate_table }}`;

SELECT
  APPROX_QUANTILES(additions + deletions, 20) AS diff_size_quantiles,
  APPROX_QUANTILES(changed_files, 20) AS changed_files_quantiles,
  APPROX_QUANTILES(review_comment_events, 20) AS review_comment_quantiles
FROM `{{ candidate_table }}`;

SELECT
  repo_name,
  pr_number,
  pr_url,
  pr_title,
  additions,
  deletions,
  changed_files,
  issue_comment_events,
  review_events,
  review_comment_events
FROM `{{ candidate_table }}`
ORDER BY RAND()
LIMIT 50;
