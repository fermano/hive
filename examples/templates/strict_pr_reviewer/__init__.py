"""
Strict PR Code Reviewer — read-only GitHub PR review (no code changes, no GitHub posts).

Fetches PR metadata and file patches via the GitHub API, then delivers a strict written review.
"""

from __future__ import annotations

from .agent import (
    StrictPrReviewerAgent,
    default_agent,
    edges,
    entry_node,
    entry_points,
    goal,
    nodes,
    pause_nodes,
    terminal_nodes,
)
from .config import AgentMetadata, RuntimeConfig, default_config, metadata

__version__ = "1.0.0"

__all__ = [
    "AgentMetadata",
    "RuntimeConfig",
    "StrictPrReviewerAgent",
    "default_agent",
    "default_config",
    "edges",
    "entry_node",
    "entry_points",
    "goal",
    "metadata",
    "nodes",
    "pause_nodes",
    "terminal_nodes",
]
