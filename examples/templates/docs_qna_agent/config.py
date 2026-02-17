"""Runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass

from framework.config import RuntimeConfig

default_config = RuntimeConfig()


@dataclass
class AgentMetadata:
    name: str = "Docs QnA Agent"
    version: str = "1.0.0"
    description: str = (
        "Answers questions about Hive documentation using pre-populated markdown files. "
        "Cites sources and says 'I don't know' when docs don't contain the answer."
    )
    intro_message: str = (
        "Hi! I'm your Hive documentation assistant. Ask me anything about the Hive framework. "
        "I'll search the docs and cite my sources. Docs are auto-synced on startup."
    )


metadata = AgentMetadata()

# Optional: override for bootstrap and doc source
repo_owner: str = "adenhq"
repo_name: str = "hive"
