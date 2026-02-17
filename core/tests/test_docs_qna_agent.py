"""Tests for docs_qna_agent template."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

# Ensure examples/templates is on path for imports
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_EXAMPLES = _REPO_ROOT / "examples" / "templates"
if str(_EXAMPLES) not in sys.path:
    sys.path.insert(0, str(_EXAMPLES))


@pytest.fixture
def docs_qna_agent():
    """Import docs_qna_agent module (skip if not found)."""
    try:
        import docs_qna_agent as m

        return m
    except ImportError:
        pytest.skip("docs_qna_agent not found (run from repo with examples/templates)")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestDocsQnaAgentHappyPath:
    """Happy path tests for docs_qna_agent."""

    def test_validate_passes(self, docs_qna_agent):
        """Agent structure validation passes."""
        validation = docs_qna_agent.default_agent.validate()
        assert validation["valid"] is True
        assert validation["errors"] == []

    def test_info_returns_expected_structure(self, docs_qna_agent):
        """Agent info returns expected keys and structure."""
        info = docs_qna_agent.default_agent.info()
        assert info["name"] == "Docs QnA Agent"
        assert info["entry_node"] == "qna_node"
        assert "qna_node" in info["nodes"]
        assert "qna_node" in info["client_facing_nodes"]
        assert info["goal"]["name"] == "Docs QnA"

    def test_qna_node_has_required_tools(self, docs_qna_agent):
        """QnA node has list_docs, search_docs, read_doc tools."""
        from docs_qna_agent.nodes import qna_node

        assert "list_docs" in qna_node.tools
        assert "search_docs" in qna_node.tools
        assert "read_doc" in qna_node.tools

    def test_sync_docs_from_repo_when_docs_exist(self, docs_qna_agent, tmp_path, monkeypatch):
        """sync_docs_from_repo returns >= 0 when repo has docs/."""
        from docs_qna_agent.sync_docs import sync_docs_from_repo

        monkeypatch.setenv("HIVE_WORKSPACES_DIR", str(tmp_path))
        count = sync_docs_from_repo()
        assert count >= 0

    def test_bootstrap_writes_files_with_mock_github(self, docs_qna_agent, tmp_path):
        """Bootstrap writes .md files when GitHub API returns valid data."""
        from docs_qna_agent.bootstrap_docs import bootstrap

        mock_list = [
            {
                "name": "readme.md",
                "type": "file",
                "download_url": "https://raw.example.com/readme.md",
            },
        ]
        mock_file_content = b"# Readme\n\nContent."
        req = httpx.Request("GET", "https://api.github.com")

        def mock_get(url, **kwargs):
            if "raw" in str(url) or "download" in str(url).lower():
                return httpx.Response(200, content=mock_file_content, request=req)
            return httpx.Response(200, json=mock_list, request=req)

        with (
            patch.object(
                docs_qna_agent.bootstrap_docs,
                "DOCS_DIR",
                tmp_path / "default" / "docs_qna_agent-graph" / "current",
            ),
            patch("httpx.get", side_effect=mock_get),
        ):
            count = bootstrap(owner="test", repo="test")
        assert count == 1
        written = tmp_path / "default" / "docs_qna_agent-graph" / "current" / "readme.md"
        assert written.exists()
        assert written.read_bytes() == mock_file_content

    @pytest.mark.asyncio
    async def test_run_mock_mode_completes(self, docs_qna_agent, tmp_path, monkeypatch):
        """Agent run in mock_mode completes without crashing."""
        from framework.graph.executor import ExecutionResult

        monkeypatch.setenv("HIVE_WORKSPACES_DIR", str(tmp_path))
        docs_dir = tmp_path / "default" / "docs_qna_agent" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "test.md").write_text("# Test\n\nContent.")

        agent = docs_qna_agent.DocsqnaAgent()
        result = await agent.run({"question": "What is Hive?"}, mock_mode=True)
        assert isinstance(result, ExecutionResult)


# ---------------------------------------------------------------------------
# Problematic scenarios
# ---------------------------------------------------------------------------


class TestDocsQnaAgentProblematicScenarios:
    """Tests for expected failure or edge-case scenarios."""

    def test_bootstrap_raises_on_404(self, docs_qna_agent, tmp_path):
        """Bootstrap raises httpx.HTTPError when repo returns 404."""
        from docs_qna_agent.bootstrap_docs import bootstrap

        def mock_get_404(*args, **kwargs):
            raise httpx.HTTPStatusError(
                "404",
                request=httpx.Request("GET", "https://api.github.com/repos/x/y/contents/docs"),
                response=httpx.Response(404),
            )

        with patch("httpx.get", side_effect=mock_get_404):
            with pytest.raises(httpx.HTTPStatusError):
                bootstrap(owner="nonexistent_owner_xyz", repo="nonexistent_repo_xyz")

    def test_bootstrap_handles_empty_contents(self, docs_qna_agent, tmp_path):
        """Bootstrap returns 0 when API returns empty directory."""
        from docs_qna_agent.bootstrap_docs import bootstrap

        req = httpx.Request("GET", "https://api.github.com")
        with (
            patch.object(docs_qna_agent.bootstrap_docs, "DOCS_DIR", tmp_path),
            patch(
                "httpx.get",
                return_value=httpx.Response(200, json=[], request=req),
            ),
        ):
            count = bootstrap(owner="test", repo="test")
        assert count == 0

    def test_list_docs_returns_empty_entries_when_docs_dir_empty(
        self, docs_qna_agent, tmp_path, monkeypatch
    ):
        """list_docs returns success with 0 entries when docs dir is empty."""
        monkeypatch.setenv("HIVE_WORKSPACES_DIR", str(tmp_path))
        docs_dir = tmp_path / "default" / "docs_qna_agent" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        # Empty dir - list_docs on "." should succeed with 0 entries
        from docs_qna_agent.docs_tools import list_docs

        result = list_docs(path=".")
        assert "entries" in result
        assert result["total_count"] == 0

    def test_read_doc_returns_error_for_nonexistent_file(
        self, docs_qna_agent, tmp_path, monkeypatch
    ):
        """read_doc returns error dict when file does not exist."""
        monkeypatch.setenv("HIVE_WORKSPACES_DIR", str(tmp_path))
        docs_dir = tmp_path / "default" / "docs_qna_agent" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        from docs_qna_agent.docs_tools import read_doc

        result = read_doc(path="nonexistent_file_xyz.md")
        assert "error" in result

    def test_search_docs_returns_error_for_invalid_regex(
        self, docs_qna_agent, tmp_path, monkeypatch
    ):
        """search_docs returns error when pattern is invalid regex."""
        monkeypatch.setenv("HIVE_WORKSPACES_DIR", str(tmp_path))
        docs_dir = tmp_path / "default" / "docs_qna_agent" / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)

        from docs_qna_agent.docs_tools import search_docs

        result = search_docs(pattern="[invalid(regex")
        assert "error" in result
