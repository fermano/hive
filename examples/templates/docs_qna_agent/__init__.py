"""
Docs QnA Agent - Answers questions about Hive documentation.

Uses pre-populated markdown files from the repo's docs/ directory.
Cites sources and says "I don't know" when docs don't contain the answer.
"""

from .agent import DocsqnaAgent, default_agent, goal, nodes, edges
from .config import RuntimeConfig, AgentMetadata, default_config, metadata

__version__ = "1.0.0"

__all__ = [
    "DocsqnaAgent",
    "default_agent",
    "goal",
    "nodes",
    "edges",
    "RuntimeConfig",
    "AgentMetadata",
    "default_config",
    "metadata",
]
