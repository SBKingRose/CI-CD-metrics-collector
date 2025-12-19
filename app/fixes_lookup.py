"""
Known error patterns and their fixes.
Add new entries here as you discover common errors and their solutions.
"""

KNOWN_FIXES = [
    {
        "pattern": "Seems like you're running a lot of pipelines at the same time",
        "cause": "Workspace exceeded concurrent pipelines/step limits",
        "fix": [
            "Reduce number of parallel steps",
            "Avoid pushing >5 references (branches/tags) at once",
            "Stagger pipeline triggers across repos"
        ],
        "link": "https://support.atlassian.com/bitbucket-cloud/kb/bitbucket-pipelines-seems-like-youre-running-a-lot-of-pipelines-at-the-same-time-error-message/"
    },
    {
        "pattern": "The value provided is not a valid uuid",
        "cause": "BITBUCKET_PIPELINE_UUID or BITBUCKET_STEP_UUID used without braces or not URL-encoded",
        "fix": [
            "Use the UUID with braces: {11d87b82-...}",
            "URL-encode braces: %7B and %7D in API calls"
        ],
        "link": "https://support.atlassian.com/bitbucket-cloud/kb/bitbucket-cloud-pipelines-api-error-the-value-provided-is-not-a-valid-uuid/"
    },
    {
        "pattern": "npm ERR!",
        "cause": "npm package installation or script execution failed",
        "fix": [
            "Check package.json for dependency issues",
            "Clear npm cache: npm cache clean --force",
            "Delete node_modules and package-lock.json, then reinstall",
            "Check for version conflicts in dependencies"
        ],
        "link": "https://docs.npmjs.com/cli/v8/commands/npm-install"
    },
    {
        "pattern": "docker: Error response from daemon",
        "cause": "Docker daemon error or image pull failure",
        "fix": [
            "Check Docker daemon is running",
            "Verify image name and tag are correct",
            "Check Docker Hub rate limits",
            "Try pulling the image manually to verify access"
        ],
        "link": "https://docs.docker.com/get-started/"
    },
    {
        "pattern": "Permission denied",
        "cause": "File or directory permission issues",
        "fix": [
            "Check file permissions: chmod +x for scripts",
            "Verify user has access to required directories",
            "Check if files exist before accessing them"
        ],
        "link": ""
    },
    {
        "pattern": "Connection refused",
        "cause": "Service or port not available",
        "fix": [
            "Verify the service is running",
            "Check if the port is correct",
            "Ensure firewall rules allow the connection",
            "Wait for service to be ready before connecting"
        ],
        "link": ""
    },
    {
        "pattern": "Out of memory",
        "cause": "Build step exceeded memory limit",
        "fix": [
            "Increase memory limit in bitbucket-pipelines.yml",
            "Optimize build process to use less memory",
            "Split large steps into smaller ones",
            "Use larger build size if available"
        ],
        "link": "https://support.atlassian.com/bitbucket-cloud/docs/configure-bitbucket-pipelinesyml/"
    },
    {
        "pattern": "timeout",
        "cause": "Build step exceeded time limit",
        "fix": [
            "Increase max-time for the step",
            "Optimize slow operations",
            "Cache dependencies to speed up builds",
            "Split long-running steps"
        ],
        "link": "https://support.atlassian.com/bitbucket-cloud/docs/configure-bitbucket-pipelinesyml/"
    },
    {
        "pattern": "Module not found",
        "cause": "Missing dependency or incorrect import path",
        "fix": [
            "Install missing dependencies",
            "Check import paths are correct",
            "Verify package.json includes all required packages",
            "Clear cache and reinstall dependencies"
        ],
        "link": ""
    },
    {
        "pattern": "SyntaxError",
        "cause": "Syntax error in code",
        "fix": [
            "Check the file mentioned in the error",
            "Verify syntax matches language version",
            "Check for missing brackets, quotes, or semicolons",
            "Run linter locally before pushing"
        ],
        "link": ""
    }
]


def match_known_fixes(log_text: str) -> list:
    """
    Match error log text against known fix patterns.
    Returns list of matching fix entries.
    """
    if not log_text:
        return []
    
    log_lower = log_text.lower()
    matches = []
    
    for entry in KNOWN_FIXES:
        if entry["pattern"].lower() in log_lower:
            matches.append(entry)
    
    return matches

