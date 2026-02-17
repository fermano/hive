"""
Sync docs from the repo's /docs directory to the agent's knowledge base.

Copies all files from docs/ recursively into the workspace so the agent
can use view_file, grep_search, list_dir. Runs on agent initialization.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

# Workspace base — must match tools' security.WORKSPACES_DIR resolution
WORKSPACES_DIR = Path.home() / ".hive" / "workdir" / "workspaces"
# Session dir: workspace_id/agent_id/session_id (matches tool_session_context)
DOCS_WORKSPACE_DIR = WORKSPACES_DIR / "default" / "docs_qna_agent" / "docs"


def _find_repo_docs() -> Path | None:
    """Find the repo's docs/ directory (relative to this package)."""
    # Agent package: examples/templates/docs_qna_agent/
    # Repo root: 3 levels up from package dir
    package_dir = Path(__file__).resolve().parent
    repo_root = package_dir.parent.parent.parent
    docs_src = repo_root / "docs"
    if docs_src.is_dir():
        return docs_src
    return None


def _copy_docs_to(docs_src: Path, target_dir: Path) -> int:
    """Copy docs recursively into target_dir. Returns number of files copied."""
    target_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for src_path in docs_src.rglob("*"):
        if src_path.is_file():
            rel = src_path.relative_to(docs_src)
            dst = target_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dst)
            count += 1
    return count


def sync_docs_from_repo() -> int:
    """
    Copy repo's docs/ into workspace session dir. Idempotent.

    Uses same path as tools (workspace_id/agent_id/session_id). Supports
    HIVE_WORKSPACES_DIR env var to override base path if needed.

    Returns:
        Number of files copied. 0 if docs/ not found.
    """
    env_base = os.environ.get("HIVE_WORKSPACES_DIR")
    base = Path(env_base).resolve() if env_base else (Path.home() / ".hive" / "workdir" / "workspaces")
    target = base / "default" / "docs_qna_agent" / "docs"

    docs_src = _find_repo_docs()
    if not docs_src:
        return 0

    return _copy_docs_to(docs_src, target)
