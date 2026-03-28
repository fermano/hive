"""Agent graph construction for Strict PR Code Reviewer."""

from __future__ import annotations

from pathlib import Path

from framework.graph import Constraint, EdgeCondition, EdgeSpec, Goal, SuccessCriterion
from framework.graph.edge import GraphSpec
from framework.graph.executor import ExecutionResult, GraphExecutor
from framework.llm import LiteLLMProvider
from framework.runner.tool_registry import ToolRegistry
from framework.runtime.core import Runtime
from framework.runtime.event_bus import EventBus

from .config import default_config, metadata
from .nodes import (
    deliver_report_node,
    fetch_pr_node,
    intake_node,
    strict_review_node,
)

goal = Goal(
    id="strict-pr-code-review",
    name="Strict PR Code Reviewer",
    description=(
        "Read-only review of GitHub pull requests: fetch metadata and patches via the API, "
        "then produce a strict, balanced tech-lead review (correctness, security, design, "
        "performance/ops, style). The agent never modifies code and never posts to GitHub."
    ),
    success_criteria=[
        SuccessCriterion(
            id="sc-evidence-backed",
            description="Findings cite file paths and patch evidence where available",
            metric="evidence_per_finding",
            target="100%",
            weight=0.25,
        ),
        SuccessCriterion(
            id="sc-blocking-separated",
            description="Blocking vs non-blocking issues are clearly separated",
            metric="blocking_section_present",
            target="true",
            weight=0.2,
        ),
        SuccessCriterion(
            id="sc-remediation",
            description="Each blocking issue includes concrete remediation direction",
            metric="blocking_with_remediation",
            target="100%",
            weight=0.25,
        ),
        SuccessCriterion(
            id="sc-read-only",
            description="Review states no repository or GitHub-side mutations were performed",
            metric="read_only_acknowledged",
            target="true",
            weight=0.15,
        ),
        SuccessCriterion(
            id="sc-delivered",
            description="User receives a structured Markdown final report",
            metric="final_report_delivered",
            target="true",
            weight=0.15,
        ),
    ],
    constraints=[
        Constraint(
            id="c-no-code-mutation",
            description=(
                "Never modify, write, or rewrite repository code — no apply_diff, patches, "
                "file writes, or shell commands that change files"
            ),
            constraint_type="hard",
            category="safety",
        ),
        Constraint(
            id="c-no-github-writes",
            description=(
                "Never post PR comments, reviews, commits, merges, or create/update issues "
                "or pull requests on GitHub"
            ),
            constraint_type="hard",
            category="safety",
        ),
        Constraint(
            id="c-no-fabricated-diff",
            description="Never invent diff hunks or file contents; only use fetched API data",
            constraint_type="hard",
            category="quality",
        ),
        Constraint(
            id="c-suggestions-only",
            description=(
                "Remediation must be prose or pseudo-code guidance only — no full-file "
                "drop-in replacements presented as ready-to-apply patches"
            ),
            constraint_type="hard",
            category="quality",
        ),
    ],
)

nodes = [
    intake_node,
    fetch_pr_node,
    strict_review_node,
    deliver_report_node,
]

edges = [
    EdgeSpec(
        id="intake-to-fetch-pr",
        source="intake",
        target="fetch-pr",
        condition=EdgeCondition.ON_SUCCESS,
        priority=1,
    ),
    EdgeSpec(
        id="fetch-pr-to-strict-review",
        source="fetch-pr",
        target="strict-review",
        condition=EdgeCondition.ON_SUCCESS,
        priority=1,
    ),
    EdgeSpec(
        id="strict-review-to-deliver-report",
        source="strict-review",
        target="deliver-report",
        condition=EdgeCondition.ON_SUCCESS,
        priority=1,
    ),
]

entry_node = "intake"
entry_points = {"start": "intake"}
pause_nodes = []
terminal_nodes = ["deliver-report"]


class StrictPrReviewerAgent:
    """Strict PR Code Reviewer — 4-node pipeline: intake → fetch → review → deliver."""

    def __init__(self, config=None):
        self.config = config or default_config
        self.goal = goal
        self.nodes = nodes
        self.edges = edges
        self.entry_node = entry_node
        self.entry_points = entry_points
        self.pause_nodes = pause_nodes
        self.terminal_nodes = terminal_nodes
        self._executor: GraphExecutor | None = None
        self._graph: GraphSpec | None = None
        self._event_bus: EventBus | None = None
        self._tool_registry: ToolRegistry | None = None

    def _build_graph(self) -> GraphSpec:
        """Build the GraphSpec."""
        return GraphSpec(
            id="strict-pr-reviewer-graph",
            goal_id=self.goal.id,
            version="1.0.0",
            entry_node=self.entry_node,
            entry_points=self.entry_points,
            terminal_nodes=self.terminal_nodes,
            pause_nodes=self.pause_nodes,
            nodes=self.nodes,
            edges=self.edges,
            default_model=self.config.model,
            max_tokens=self.config.max_tokens,
            loop_config={
                "max_iterations": 80,
                "max_tool_calls_per_turn": 40,
                "max_history_tokens": 32000,
            },
        )

    def _setup(self) -> GraphExecutor:
        """Set up the executor with all components."""
        storage_path = Path.home() / ".hive" / "strict_pr_reviewer"
        storage_path.mkdir(parents=True, exist_ok=True)

        self._event_bus = EventBus()
        self._tool_registry = ToolRegistry()

        mcp_config_path = Path(__file__).parent / "mcp_servers.json"
        if mcp_config_path.exists():
            self._tool_registry.load_mcp_config(mcp_config_path)

        llm = LiteLLMProvider(
            model=self.config.model,
            api_key=self.config.api_key,
            api_base=self.config.api_base,
        )

        tool_executor = self._tool_registry.get_executor()
        tools = list(self._tool_registry.get_tools().values())

        self._graph = self._build_graph()
        runtime = Runtime(storage_path)

        self._executor = GraphExecutor(
            runtime=runtime,
            llm=llm,
            tools=tools,
            tool_executor=tool_executor,
            event_bus=self._event_bus,
            storage_path=storage_path,
            loop_config=self._graph.loop_config,
        )

        return self._executor

    async def start(self) -> None:
        """Set up the agent (initialize executor and tools)."""
        if self._executor is None:
            self._setup()

    async def stop(self) -> None:
        """Clean up resources."""
        self._executor = None
        self._event_bus = None

    async def trigger_and_wait(
        self,
        entry_point: str,
        input_data: dict,
        timeout: float | None = None,
        session_state: dict | None = None,
    ) -> ExecutionResult | None:
        """Execute the graph and wait for completion."""
        if self._executor is None:
            raise RuntimeError("Agent not started. Call start() first.")
        if self._graph is None:
            raise RuntimeError("Graph not built. Call start() first.")

        return await self._executor.execute(
            graph=self._graph,
            goal=self.goal,
            input_data=input_data,
            session_state=session_state,
        )

    async def run(self, context: dict, session_state=None) -> ExecutionResult:
        """Run the agent (convenience method for single execution)."""
        await self.start()
        try:
            result = await self.trigger_and_wait(
                "start", context, session_state=session_state
            )
            return result or ExecutionResult(success=False, error="Execution timeout")
        finally:
            await self.stop()

    def info(self):
        """Get agent information."""
        return {
            "name": metadata.name,
            "version": metadata.version,
            "description": metadata.description,
            "goal": {
                "name": self.goal.name,
                "description": self.goal.description,
            },
            "nodes": [n.id for n in self.nodes],
            "edges": [e.id for e in self.edges],
            "entry_node": self.entry_node,
            "entry_points": self.entry_points,
            "pause_nodes": self.pause_nodes,
            "terminal_nodes": self.terminal_nodes,
            "client_facing_nodes": [n.id for n in self.nodes if n.client_facing],
        }

    def validate(self):
        """Validate agent structure."""
        errors = []
        warnings = []

        node_ids = {node.id for node in self.nodes}
        for edge in self.edges:
            if edge.source not in node_ids:
                errors.append(f"Edge {edge.id}: source '{edge.source}' not found")
            if edge.target not in node_ids:
                errors.append(f"Edge {edge.id}: target '{edge.target}' not found")

        if self.entry_node not in node_ids:
            errors.append(f"Entry node '{self.entry_node}' not found")

        for terminal in self.terminal_nodes:
            if terminal not in node_ids:
                errors.append(f"Terminal node '{terminal}' not found")

        for ep_id, node_id in self.entry_points.items():
            if node_id not in node_ids:
                errors.append(
                    f"Entry point '{ep_id}' references unknown node '{node_id}'"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }


default_agent = StrictPrReviewerAgent()
