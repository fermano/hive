"""
Local docs tools — run in-process, no MCP. Read from synced docs path directly.
Bypasses workspace path mismatches between agent and MCP subprocess.
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _get_docs_dir() -> Path:
    """Return the docs directory (same path sync uses)."""
    env_base = os.environ.get("HIVE_WORKSPACES_DIR")
    base = (Path(env_base).resolve() if env_base else
            (Path.home() / ".hive" / "workdir" / "workspaces"))
    return base / "default" / "docs_qna_agent" / "docs"


def list_docs(path: str = ".") -> dict:
    """
    List docs in the knowledge base. Path relative to docs root (e.g. "." or "key_concepts").

    Returns:
        Dict with entries (name, type, size_bytes) or error.
    """
    try:
        docs_dir = _get_docs_dir().resolve()
        target = (docs_dir / path).resolve()
        try:
            target.relative_to(docs_dir)
        except ValueError:
            return {"error": f"Path outside docs: {path}"}
        if not target.exists():
            return {"error": f"Path not found: {path}"}
        if not target.is_dir():
            return {"error": f"Not a directory: {path}"}
        entries = []
        for item in sorted(target.iterdir()):
            is_dir = item.is_dir()
            entries.append({
                "name": item.name,
                "type": "directory" if is_dir else "file",
                "size_bytes": item.stat().st_size if not is_dir else None,
            })
        return {"success": True, "path": path, "entries": entries, "total_count": len(entries)}
    except Exception as e:
        return {"error": str(e)}


def search_docs(pattern: str, path: str = ".", recursive: bool = True) -> dict:
    """
    Search for pattern (regex) in docs. Returns file, line_number, line_content for each match.

    Args:
        pattern: Regex pattern to search
        path: Start path (default ".")
        recursive: Search subdirectories (default True)

    Returns:
        Dict with matches or error.
    """
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return {"error": f"Invalid regex: {e}"}

    try:
        docs_dir = _get_docs_dir().resolve()
        target = (docs_dir / path).resolve()
        try:
            target.relative_to(docs_dir)
        except ValueError:
            return {"error": f"Path outside docs: {path}"}
        if not target.exists():
            return {"error": f"Path not found: {path}"}

        matches = []
        iter_paths = target.rglob("*") if recursive and target.is_dir() else [target]
        for p in iter_paths:
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(docs_dir)
                text = p.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(text.splitlines(), 1):
                    if regex.search(line):
                        matches.append({
                            "file": str(rel),
                            "line_number": i,
                            "line_content": line.strip(),
                        })
            except (UnicodeDecodeError, PermissionError):
                continue

        return {"success": True, "matches": matches, "total": len(matches)}
    except Exception as e:
        return {"error": str(e)}


def read_doc(path: str) -> dict:
    """
    Read full content of a doc file. Path relative to docs root (e.g. "getting-started.md").

    Returns:
        Dict with content and metadata or error.
    """
    try:
        docs_dir = _get_docs_dir().resolve()
        target = (docs_dir / path).resolve()
        try:
            target.relative_to(docs_dir)
        except ValueError:
            return {"error": f"Path outside docs: {path}"}
        if not target.exists():
            return {"error": f"File not found: {path}"}
        if not target.is_file():
            return {"error": f"Not a file: {path}"}
        content = target.read_text(encoding="utf-8", errors="replace")
        return {"success": True, "path": path, "content": content}
    except Exception as e:
        return {"error": str(e)}
