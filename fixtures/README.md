# Fixtures Directory

This directory stores repo-specific data files that are not available via Bitbucket API.

## Structure

```
fixtures/
  {repo_slug}/
    trivy-report.json    # Vulnerability scan results from trivy/npm audit
    metrics.json         # CPU/Memory metrics (captured from Bitbucket UI)
    build_usage.json     # Build minutes report from atlassian/bitbucket-build-statistics pipe
```

## File Formats

### trivy-report.json
JSON output from trivy scan. Should contain vulnerability data.

### metrics.json
CPU/Memory metrics captured from Bitbucket pipeline step metrics page.
Format: JSON with CPU and memory usage data per step.

### build_usage.json
Output from `atlassian/bitbucket-build-statistics:1.5.4` pipe.
Contains build minutes per period (28th to 28th).

## Usage

When a repository is selected in the UI, the app will look for these files in:
`fixtures/{repo_slug}/{filename}`

If a file is missing, the app will show a message indicating the data is not available.

