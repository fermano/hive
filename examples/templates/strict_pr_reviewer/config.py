"""Runtime configuration for Strict PR Code Reviewer."""

from __future__ import annotations

from dataclasses import dataclass

from framework.config import RuntimeConfig

__all__ = ["AgentMetadata", "RuntimeConfig", "default_config", "metadata"]

default_config = RuntimeConfig()


@dataclass
class AgentMetadata:
    name: str = "Strict PR Code Reviewer"
    version: str = "1.0.0"
    description: str = (
        "Read-only automated code review for GitHub pull requests. Acts as a demanding "
        "tech lead: reports issues and remediation guidance only — never modifies code, "
        "never posts review comments on GitHub."
    )
    intro_message: str = (
        "I'm a strict, read-only PR reviewer. Give me a GitHub PR URL or owner, repo, and "
        "PR number. I'll fetch the diff via the API and return a written review only — "
        "no code changes and no posting to GitHub."
    )


metadata = AgentMetadata()
