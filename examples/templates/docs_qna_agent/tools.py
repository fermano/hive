"""Local docs tools for Docs QnA Agent — run in-process, no MCP."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from framework.llm.provider import Tool, ToolResult, ToolUse

# Load docs_tools from same dir (works when tools.py is loaded standalone by discover_from_module)
_tools_dir = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("docs_tools", _tools_dir / "docs_tools.py")
_docs_tools = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_docs_tools)
list_docs = _docs_tools.list_docs
read_doc = _docs_tools.read_doc
search_docs = _docs_tools.search_docs

TOOLS = {
    "list_docs": Tool(
        name="list_docs",
        description=list_docs.__doc__ or "List files in docs. Use path='.' for root.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path relative to docs root (default '.')"},
            },
            "required": [],
        },
    ),
    "search_docs": Tool(
        name="search_docs",
        description=search_docs.__doc__ or "Search for pattern in docs.",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search"},
                "path": {"type": "string", "description": "Start path (default '.')"},
                "recursive": {"type": "boolean", "description": "Search subdirs (default True)"},
            },
            "required": ["pattern"],
        },
    ),
    "read_doc": Tool(
        name="read_doc",
        description=read_doc.__doc__ or "Read full content of a doc file.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to docs root"},
            },
            "required": ["path"],
        },
    ),
}


def tool_executor(tool_use: ToolUse) -> ToolResult:
    """Dispatch docs tool calls."""
    name = tool_use.name
    inp = tool_use.input or {}
    try:
        if name == "list_docs":
            result = list_docs(path=inp.get("path", "."))
        elif name == "search_docs":
            result = search_docs(
                pattern=inp.get("pattern", ""),
                path=inp.get("path", "."),
                recursive=inp.get("recursive", True),
            )
        elif name == "read_doc":
            result = read_doc(path=inp.get("path", ""))
        else:
            return ToolResult(
                tool_use_id=tool_use.id,
                content=json.dumps({"error": f"Unknown tool: {name}"}),
                is_error=True,
            )
        return ToolResult(
            tool_use_id=tool_use.id,
            content=json.dumps(result),
            is_error="error" in result,
        )
    except Exception as e:
        return ToolResult(
            tool_use_id=tool_use.id,
            content=json.dumps({"error": str(e)}),
            is_error=True,
        )
