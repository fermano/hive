"""Agent graph construction for Docs QnA Agent."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

from framework.graph import EdgeSpec, EdgeCondition, Goal, SuccessCriterion, Constraint
from framework.graph.edge import GraphSpec
from framework.graph.executor import ExecutionResult
from framework.graph.checkpoint_config import CheckpointConfig
from framework.llm import LiteLLMProvider
from framework.runner.tool_registry import ToolRegistry
from framework.runtime.agent_runtime import AgentRuntime, create_agent_runtime
from framework.runtime.execution_stream import EntryPointSpec

from .config import default_config, metadata, repo_name, repo_owner
from .nodes import qna_node
from .sync_docs import sync_docs_from_repo

# Goal definition
goal = Goal(
    id="docs-qna",
    name="Docs QnA",
    description=(
        "Answer questions about Hive documentation. Uses pre-populated markdown files "
        "from the repo's docs/ directory. Cites sources and says 'I don't know' when "
        "docs don't contain the answer."
    ),
    success_criteria=[
        SuccessCriterion(
            id="answer-relevance",
            description="Answers are grounded in the docs",
            metric="llm_judge",
            target="true",
            weight=0.34,
        ),
        SuccessCriterion(
            id="citation",
            description="Answers cite which doc/section they came from",
            metric="llm_judge",
            target="true",
            weight=0.33,
        ),
        SuccessCriterion(
            id="no-hallucination",
            description="Does not invent information; says 'I don't know' when uncertain",
            metric="llm_judge",
            target="true",
            weight=0.33,
        ),
    ],
    constraints=[
        Constraint(
            id="docs-only",
            description="Only use information from the pre-populated docs; no web search or external sources",
            constraint_type="hard",
            category="quality",
        ),
        Constraint(
            id="cite-sources",
            description="Cite the doc file and section for each factual claim",
            constraint_type="hard",
            category="quality",
        ),
    ],
)

# Node list
nodes = [qna_node]

# Edge definitions (self-loop for continuous Q&A)
edges = [
    EdgeSpec(
        id="qna-to-qna",
        source="qna_node",
        target="qna_node",
        condition=EdgeCondition.ON_SUCCESS,
        priority=1,
    ),
]

# Graph configuration
entry_node = "qna_node"
entry_points = {"start": "qna_node"}
pause_nodes: list[str] = []
terminal_nodes: list[str] = []

# Session path for file tools — runner and custom CLI both use this
tool_session_context = {
    "workspace_id": "default",
    "agent_id": "docs_qna_agent",
    "session_id": "docs",
}


def on_runner_setup(*, agent_path: Path, mock_mode: bool) -> None:
    """
    Hook called by AgentRunner._setup(). Syncs docs to workspace so file tools find them.
    """
    if mock_mode:
        return
    n = sync_docs_from_repo()
    if n > 0:
        logger.info("Synced %d files from docs/ to knowledge base", n)
    else:
        try:
            from .bootstrap_docs import bootstrap

            count = bootstrap(owner=repo_owner, repo=repo_name)
            if count > 0:
                logger.info("Fetched %d files from GitHub (no local docs)", count)
        except Exception as e:
            logger.warning("Could not load docs: %s", e)


class DocsqnaAgent:
    """
    Docs QnA Agent — single-node Q&A over Hive documentation.

    Uses AgentRuntime with session context set so file tools (view_file,
    grep_search, list_dir) read from the pre-populated docs workspace.
    """

    def __init__(self, config=None):
        self.config = config or default_config
        self.goal = goal
        self.nodes = nodes
        self.edges = edges
        self.entry_node = entry_node
        self.entry_points = entry_points
        self.pause_nodes = pause_nodes
        self.terminal_nodes = terminal_nodes
        self._graph: GraphSpec | None = None
        self._agent_runtime: AgentRuntime | None = None
        self._tool_registry: ToolRegistry | None = None
        self._storage_path: Path | None = None

    def _build_graph(self) -> GraphSpec:
        """Build the GraphSpec."""
        return GraphSpec(
            id="docs-qna-agent-graph",
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
                "max_iterations": 100,
                "max_tool_calls_per_turn": 20,
                "max_history_tokens": 32000,
            },
        )

    def _setup(self, mock_mode: bool = False) -> None:
        """Set up the executor with all components."""
        self._storage_path = Path.home() / ".hive" / "agents" / "docs_qna_agent"
        self._storage_path.mkdir(parents=True, exist_ok=True)

        # Sync docs from repo's /docs into workspace (agent's knowledge base)
        if not mock_mode:
            n = sync_docs_from_repo()
            if n > 0:
                logger.info("Synced %d files from docs/ to knowledge base", n)
            else:
                # Fallback: fetch from GitHub when no local docs (e.g. installed package)
                try:
                    from .bootstrap_docs import bootstrap

                    count = bootstrap(owner=repo_owner, repo=repo_name)
                    if count > 0:
                        logger.info("Fetched %d files from GitHub (no local docs)", count)
                except Exception as e:
                    logger.warning("Could not load docs: %s", e)

        self._tool_registry = ToolRegistry()
        # Match Runner's session context so tools see bootstrap docs (when run via hive tui)
        self._tool_registry.set_session_context(
            workspace_id="default",
            agent_id="docs_qna_agent-graph",
            session_id="current",
        )

        # Load local docs tools from tools.py (in-process, no MCP)
        tools_path = Path(__file__).parent / "tools.py"
        self._tool_registry.discover_from_module(tools_path)

        llm = None
        if not mock_mode:
            llm = LiteLLMProvider(
                model=self.config.model,
                api_key=self.config.api_key,
                api_base=self.config.api_base,
            )

        tool_executor = self._tool_registry.get_executor()
        tools = list(self._tool_registry.get_tools().values())

        self._graph = self._build_graph()

        checkpoint_config = CheckpointConfig(
            enabled=True,
            checkpoint_on_node_start=False,
            checkpoint_on_node_complete=True,
            checkpoint_max_age_days=7,
            async_checkpoint=True,
        )

        entry_point_specs = [
            EntryPointSpec(
                id="default",
                name="Default",
                entry_node=self.entry_node,
                trigger_type="manual",
                isolation_level="shared",
            )
        ]

        self._agent_runtime = create_agent_runtime(
            graph=self._graph,
            goal=self.goal,
            storage_path=self._storage_path,
            entry_points=entry_point_specs,
            llm=llm,
            tools=tools,
            tool_executor=tool_executor,
            checkpoint_config=checkpoint_config,
        )

    async def start(self, mock_mode: bool = False) -> None:
        """Set up and start the agent runtime."""
        if self._agent_runtime is None:
            self._setup(mock_mode=mock_mode)
        if not self._agent_runtime.is_running:
            await self._agent_runtime.start()

    async def stop(self) -> None:
        """Stop the agent runtime and clean up."""
        if self._agent_runtime and self._agent_runtime.is_running:
            await self._agent_runtime.stop()
        self._agent_runtime = None

    async def trigger_and_wait(
        self,
        entry_point: str = "default",
        input_data: dict | None = None,
        timeout: float | None = None,
        session_state: dict | None = None,
    ) -> ExecutionResult | None:
        """Execute the graph and wait for completion."""
        if self._agent_runtime is None:
            raise RuntimeError("Agent not started. Call start() first.")

        return await self._agent_runtime.trigger_and_wait(
            entry_point_id=entry_point,
            input_data=input_data or {},
            session_state=session_state,
        )

    async def run(
        self, context: dict, mock_mode: bool = False, session_state: dict | None = None
    ) -> ExecutionResult:
        """Run the agent (convenience method for single execution)."""
        await self.start(mock_mode=mock_mode)
        try:
            result = await self.trigger_and_wait(
                "default", context, session_state=session_state
            )
            return result or ExecutionResult(success=False, error="Execution timeout")
        finally:
            await self.stop()

    def info(self) -> dict:
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

    def validate(self) -> dict:
        """Validate agent structure."""
        errors: list[str] = []
        warnings: list[str] = []

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


# Create default instance
default_agent = DocsqnaAgent()
