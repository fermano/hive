"""Structural tests for Strict PR Code Reviewer."""

from __future__ import annotations


class TestAgentStructure:
    """Test agent graph structure."""

    def test_goal_defined(self, agent_module):
        """Goal is properly defined."""
        assert hasattr(agent_module, "goal")
        assert agent_module.goal.id == "strict-pr-code-review"
        assert len(agent_module.goal.success_criteria) == 5

    def test_hard_constraints_read_only(self, agent_module):
        """Hard constraints forbid code mutation and GitHub writes."""
        ids = {c.id for c in agent_module.goal.constraints}
        assert "c-no-code-mutation" in ids
        assert "c-no-github-writes" in ids

    def test_nodes_defined(self, agent_module):
        """All nodes are defined."""
        assert hasattr(agent_module, "nodes")
        node_ids = {n.id for n in agent_module.nodes}
        assert node_ids == {"intake", "fetch-pr", "strict-review", "deliver-report"}

    def test_edges_defined(self, agent_module):
        """Edges connect the linear pipeline."""
        assert hasattr(agent_module, "edges")
        pairs = {(e.source, e.target) for e in agent_module.edges}
        assert ("intake", "fetch-pr") in pairs
        assert ("fetch-pr", "strict-review") in pairs
        assert ("strict-review", "deliver-report") in pairs
        assert len(agent_module.edges) == 3

    def test_entry_points(self, agent_module):
        """Entry points configured."""
        assert hasattr(agent_module, "entry_points")
        assert agent_module.entry_points["start"] == "intake"

    def test_terminal_nodes(self, agent_module):
        """Terminal node is deliver-report."""
        assert hasattr(agent_module, "terminal_nodes")
        assert agent_module.terminal_nodes == ["deliver-report"]

    def test_client_facing_nodes(self, agent_module):
        """Intake and deliver-report face the user."""
        client_facing = {n.id for n in agent_module.nodes if n.client_facing}
        assert client_facing == {"intake", "deliver-report"}

    def test_fetch_node_github_tools_only(self, agent_module):
        """Fetch node uses read-only GitHub PR tools."""
        fetch = next(n for n in agent_module.nodes if n.id == "fetch-pr")
        assert set(fetch.tools) == {
            "github_get_pull_request",
            "github_list_pull_request_files",
        }

    def test_review_nodes_have_no_tools(self, agent_module):
        """Strict review and deliver nodes do not expose tools."""
        for nid in ("strict-review", "deliver-report"):
            node = next(n for n in agent_module.nodes if n.id == nid)
            assert node.tools == []


class TestRunnerLoad:
    """Test AgentRunner can load the agent."""

    def test_runner_load_succeeds(self, runner_loaded):
        """AgentRunner.load() succeeds."""
        assert runner_loaded is not None

    def test_runner_has_goal(self, runner_loaded):
        """Runner has goal after load."""
        assert runner_loaded.goal is not None
        assert runner_loaded.goal.id == "strict-pr-code-review"

    def test_runner_has_nodes(self, runner_loaded):
        """Runner has nodes after load."""
        assert runner_loaded.graph is not None
        assert len(runner_loaded.graph.nodes) == 4
