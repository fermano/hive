"""
CLI entry point for Docs QnA Agent.

Bootstrap docs before first use. Uses session context so file tools
read from the pre-populated docs workspace.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

import click
import httpx

from .agent import default_agent, DocsqnaAgent
from .config import metadata, repo_owner, repo_name
from .bootstrap_docs import bootstrap, DOCS_DIR
from .sync_docs import sync_docs_from_repo


def setup_logging(verbose: bool = False, debug: bool = False) -> None:
    """Configure logging for execution visibility."""
    if debug:
        level, fmt = logging.DEBUG, "%(asctime)s %(name)s: %(message)s"
    elif verbose:
        level, fmt = logging.INFO, "%(message)s"
    else:
        level, fmt = logging.WARNING, "%(levelname)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, stream=sys.stderr)
    logging.getLogger("framework").setLevel(level)


@click.group()
@click.version_option(version="1.0.0")
def cli() -> None:
    """Docs QnA Agent - Answer questions about Hive documentation."""
    pass


@cli.command()
@click.option("--owner", default=repo_owner, help="GitHub repo owner")
@click.option("--repo", default=repo_name, help="GitHub repo name")
@click.option("--token", envvar="GITHUB_TOKEN", help="GitHub token for rate limits")
def bootstrap_cmd(owner: str, repo: str, token: str | None) -> None:
    """Fetch docs from GitHub to local workspace. Run before first use."""
    try:
        count = bootstrap(owner=owner, repo=repo, github_token=token)
        click.echo(f"Bootstrap complete: {count} .md files written to {DOCS_DIR}")
    except httpx.HTTPError as e:
        click.echo(f"Bootstrap failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--question", "-q", type=str, required=True, help="Question to ask")
@click.option("--quiet", is_flag=True, help="Only output result JSON")
@click.option("--verbose", "-v", is_flag=True, help="Show execution details")
@click.option("--debug", is_flag=True, help="Show debug logging")
def run(question: str, quiet: bool, verbose: bool, debug: bool) -> None:
    """Execute one-shot Q&A. Docs are auto-synced on first run."""
    if not quiet:
        setup_logging(verbose=verbose, debug=debug)

    context = {"question": question}
    result = asyncio.run(default_agent.run(context))

    output_data = {
        "success": result.success,
        "steps_executed": result.steps_executed,
        "output": result.output,
    }
    if result.error:
        output_data["error"] = result.error

    click.echo(json.dumps(output_data, indent=2, default=str))
    sys.exit(0 if result.success else 1)


@cli.command()
@click.option("--bootstrap", "do_bootstrap", is_flag=True, help="Bootstrap docs before starting")
@click.option("--verbose", "-v", is_flag=True, help="Show execution details")
@click.option("--debug", is_flag=True, help="Show debug logging")
def tui(do_bootstrap: bool, verbose: bool, debug: bool) -> None:
    """Launch the TUI dashboard for interactive Q&A."""
    setup_logging(verbose=verbose, debug=debug)

    try:
        from framework.tui.app import AdenTUI
    except ImportError:
        click.echo("TUI requires the 'textual' package. Install with: pip install textual")
        sys.exit(1)

    from framework.llm import LiteLLMProvider
    from framework.runner.tool_registry import ToolRegistry
    from framework.runtime.agent_runtime import create_agent_runtime
    from framework.runtime.execution_stream import EntryPointSpec

    async def run_with_tui() -> None:
        agent = DocsqnaAgent()

        # Sync docs from repo into workspace, or bootstrap from GitHub if --bootstrap
        if do_bootstrap:
            try:
                count = bootstrap(owner=repo_owner, repo=repo_name)
                if count > 0:
                    logging.getLogger(__name__).info("Fetched %d files from GitHub", count)
            except Exception as e:
                logging.getLogger(__name__).warning("Bootstrap failed: %s", e)
        else:
            n = sync_docs_from_repo()
            if n > 0:
                logging.getLogger(__name__).info("Synced %d files from docs/ to knowledge base", n)
            else:
                try:
                    count = bootstrap(owner=repo_owner, repo=repo_name)
                    if count > 0:
                        logging.getLogger(__name__).info("Fetched %d files from GitHub (no local docs)", count)
                except Exception as e:
                    logging.getLogger(__name__).warning("Could not load docs: %s", e)

        agent._tool_registry = ToolRegistry()
        # Match Runner's session context so tools see bootstrap docs
        agent._tool_registry.set_session_context(
            workspace_id="default",
            agent_id="docs_qna_agent-graph",
            session_id="current",
        )

        tools_path = Path(__file__).parent / "tools.py"
        agent._tool_registry.discover_from_module(tools_path)

        storage_path = Path.home() / ".hive" / "agents" / "docs_qna_agent"
        storage_path.mkdir(parents=True, exist_ok=True)

        llm = LiteLLMProvider(
            model=agent.config.model,
            api_key=agent.config.api_key,
            api_base=agent.config.api_base,
        )

        tools = list(agent._tool_registry.get_tools().values())
        tool_executor = agent._tool_registry.get_executor()
        graph = agent._build_graph()

        runtime = create_agent_runtime(
            graph=graph,
            goal=agent.goal,
            storage_path=storage_path,
            entry_points=[
                EntryPointSpec(
                    id="start",
                    name="Docs QnA",
                    entry_node="qna_node",
                    trigger_type="manual",
                    isolation_level="isolated",
                ),
            ],
            llm=llm,
            tools=tools,
            tool_executor=tool_executor,
        )

        await runtime.start()

        try:
            app = AdenTUI(runtime)
            await app.run_async()
        finally:
            await runtime.stop()

    asyncio.run(run_with_tui())


@cli.command()
@click.option("--json", "output_json", is_flag=True)
def info(output_json: bool) -> None:
    """Show agent information."""
    info_data = default_agent.info()
    if output_json:
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"Agent: {info_data['name']}")
        click.echo(f"Version: {info_data['version']}")
        click.echo(f"Description: {info_data['description']}")
        click.echo(f"\nNodes: {', '.join(info_data['nodes'])}")
        click.echo(f"Client-facing: {', '.join(info_data['client_facing_nodes'])}")
        click.echo(f"Entry: {info_data['entry_node']}")
        click.echo(f"Terminal: {', '.join(info_data['terminal_nodes'])}")


@cli.command()
def verify() -> None:
    """Verify docs are synced and show the path file tools will use."""
    import os

    env_base = os.environ.get("HIVE_WORKSPACES_DIR")
    base = Path(env_base).resolve() if env_base else (Path.home() / ".hive" / "workdir" / "workspaces")
    docs_path = base / "default" / "docs_qna_agent" / "docs"

    click.echo(f"Docs path (session root for file tools): {docs_path}")
    n = sync_docs_from_repo()
    if n > 0:
        click.echo(f"Synced {n} files from repo docs/")
    elif docs_path.exists():
        count = sum(1 for _ in docs_path.rglob("*") if _.is_file())
        click.echo(f"Path exists with {count} files (no local docs to sync)")
    else:
        click.echo("Path empty or missing. Run: bootstrap")
        try:
            count = bootstrap(owner=repo_owner, repo=repo_name)
            if count > 0:
                click.echo(f"Fetched {count} files from GitHub")
        except Exception as e:
            click.echo(f"Bootstrap failed: {e}", err=True)
            sys.exit(1)


@cli.command()
def validate() -> None:
    """Validate agent structure."""
    validation = default_agent.validate()
    if validation["valid"]:
        click.echo("Agent is valid")
        if validation["warnings"]:
            for warning in validation["warnings"]:
                click.echo(f"  WARNING: {warning}")
    else:
        click.echo("Agent has errors:")
        for error in validation["errors"]:
            click.echo(f"  ERROR: {error}")
    sys.exit(0 if validation["valid"] else 1)


if __name__ == "__main__":
    cli()
