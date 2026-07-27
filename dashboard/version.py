import os


def get_version_info() -> dict[str, str]:
    git_sha = os.getenv("ADMINNGINX_GIT_SHA", "unknown")

    return {
        "version": os.getenv("ADMINNGINX_VERSION", "dev"),
        "git_sha": git_sha,
        "short_sha": git_sha[:12] if git_sha != "unknown" else git_sha,
        "build_date": os.getenv("ADMINNGINX_BUILD_DATE", "unknown"),
        "build_run": os.getenv("ADMINNGINX_BUILD_RUN", "local"),
        "deployment": os.getenv(
            "ADMINNGINX_DEPLOYMENT_NAME",
            "non-configure",
        ),
    }


def version_context(_request) -> dict[str, dict[str, str]]:
    return {"adminnginx_version": get_version_info()}
