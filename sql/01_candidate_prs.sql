-- Replace the placeholders below before running:
--   {{ output_table }}  e.g. my_project.my_dataset.candidate_prs
--   {{ source_table }}  e.g. githubarchive.year.2025

CREATE OR REPLACE TABLE `{{ output_table }}` AS
WITH pr_closed AS (
  SELECT
    repo.name AS repo_name,
    CAST(JSON_VALUE(payload, '$.pull_request.number') AS INT64) AS pr_number,
    JSON_VALUE(payload, '$.pull_request.html_url') AS pr_url,
    JSON_VALUE(payload, '$.pull_request.title') AS pr_title,
    JSON_VALUE(payload, '$.pull_request.body') AS pr_body,
    JSON_VALUE(payload, '$.pull_request.merge_commit_sha') AS merge_commit_sha,
    CAST(JSON_VALUE(payload, '$.pull_request.additions') AS INT64) AS additions,
    CAST(JSON_VALUE(payload, '$.pull_request.deletions') AS INT64) AS deletions,
    CAST(JSON_VALUE(payload, '$.pull_request.changed_files') AS INT64) AS changed_files,
    MIN(created_at) AS pr_closed_at
  FROM `{{ source_table }}`
  WHERE type = 'PullRequestEvent'
    AND JSON_VALUE(payload, '$.action') = 'closed'
    AND JSON_VALUE(payload, '$.pull_request.merged') = 'true'
  GROUP BY
    repo_name,
    pr_number,
    pr_url,
    pr_title,
    pr_body,
    merge_commit_sha,
    additions,
    deletions,
    changed_files
),
activity AS (
  SELECT
    repo.name AS repo_name,
    CAST(
      COALESCE(
        JSON_VALUE(payload, '$.pull_request.number'),
        JSON_VALUE(payload, '$.issue.number')
      ) AS INT64
    ) AS number,
    COUNTIF(type = 'IssueCommentEvent') AS issue_comment_events,
    COUNTIF(type = 'PullRequestReviewEvent') AS review_events,
    COUNTIF(type = 'PullRequestReviewCommentEvent') AS review_comment_events,
    MIN(created_at) AS first_seen_at,
    MAX(created_at) AS last_seen_at
  FROM `{{ source_table }}`
  WHERE type IN (
    'IssueCommentEvent',
    'PullRequestReviewEvent',
    'PullRequestReviewCommentEvent'
  )
  GROUP BY repo_name, number
)
SELECT
  p.repo_name,
  p.pr_number,
  p.pr_url,
  p.pr_title,
  p.pr_body,
  p.merge_commit_sha,
  p.additions,
  p.deletions,
  p.changed_files,
  a.issue_comment_events,
  a.review_events,
  a.review_comment_events,
  a.first_seen_at,
  a.last_seen_at
FROM pr_closed p
JOIN activity a
  ON p.repo_name = a.repo_name
 AND p.pr_number = a.number
WHERE p.changed_files BETWEEN 2 AND 30
  AND p.additions + p.deletions BETWEEN 50 AND 2000
  AND a.issue_comment_events >= 2
  AND a.review_events >= 1
  AND a.review_comment_events >= 2;
