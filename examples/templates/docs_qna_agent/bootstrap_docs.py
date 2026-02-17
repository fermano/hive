"""
Bootstrap script to fetch Hive documentation from GitHub.

Fetches all .md files from the repo's docs/ directory recursively
and writes to ~/.hive/workdir/workspaces/default/docs_qna_agent-graph/current/.

Idempotent: safe to run multiple times.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

WORKSPACES_DIR = Path.home() / ".hive" / "workdir" / "workspaces"
# Must match Runner's session context: agent_id=graph.id (docs_qna_agent-graph), session_id=current
DOCS_DIR = WORKSPACES_DIR / "default" / "docs_qna_agent-graph" / "current"
GITHUB_API = "https://api.github.com"


def _fetch_contents(owner: str, repo: str, path: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    """Fetch directory or file contents from GitHub API."""
    url = f"{GITHUB_API}/repos/{owner}/{repo}/contents/{path}" if path else f"{GITHUB_API}/repos/{owner}/{repo}/contents"
    resp = httpx.get(url, headers=headers, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()
    return data if isinstance(data, list) else [data]


def _fetch_file_content(url: str, headers: dict[str, str]) -> bytes:
    """Fetch raw file content from GitHub."""
    resp = httpx.get(url, headers={**headers, "Accept": "application/vnd.github.raw"}, timeout=30.0)
    resp.raise_for_status()
    return resp.content


def bootstrap(
    owner: str = "adenhq",
    repo: str = "hive",
    docs_path: str = "docs",
    github_token: str | None = None,
) -> int:
    """
    Fetch all .md files from GitHub repo recursively and write to local docs dir.

    Args:
        owner: GitHub repo owner
        repo: GitHub repo name
        docs_path: Path to docs folder in the repo (e.g. "docs")
        github_token: Optional GitHub token for higher rate limits

    Returns:
        Number of files written
    """
    headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
    if github_token:
        headers["Authorization"] = f"token {github_token}"

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    def recurse(remote_path: str, local_path: Path) -> int:
        count = 0
        for item in _fetch_contents(owner, repo, remote_path, headers):
            name = item.get("name", "")
            if item.get("type") == "dir":
                sub_local = local_path / name
                sub_local.mkdir(parents=True, exist_ok=True)
                sub_remote = f"{remote_path}/{name}" if remote_path else name
                count += recurse(sub_remote, sub_local)
            elif item.get("type") == "file" and name.endswith(".md"):
                sub_local = local_path / name
                download_url = item.get("download_url")
                if download_url:
                    content = _fetch_file_content(download_url, headers)
                    sub_local.write_bytes(content)
                    count += 1
        return count

    return recurse(docs_path, DOCS_DIR)
