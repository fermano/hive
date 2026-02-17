# Docs QnA Agent

Answers questions about Hive documentation using pre-populated markdown files. Cites sources and says "I don't know" when docs don't contain the answer. Docs are stored at `~/.hive/workdir/workspaces/default/docs_qna_agent-graph/current/` to match the Runner's session context.

**Docs are auto-imported** on startup: the agent syncs from the repo's `/docs` directory when run from the hive repo. If no local docs (e.g. installed package), it fetches from GitHub.

## Usage

### 1. Run one-shot Q&A

```bash
PYTHONPATH=core:examples/templates uv run python -m docs_qna_agent run --question "How do I create an agent?"
```

### 2. Interactive TUI

```bash
PYTHONPATH=core:examples/templates uv run python -m docs_qna_agent tui
```

Use `--bootstrap` to fetch docs from GitHub instead of local sync:

```bash
PYTHONPATH=core:examples/templates uv run python -m docs_qna_agent tui --bootstrap
```

### 3. Manual bootstrap (optional)

```bash
PYTHONPATH=core:examples/templates uv run python -m docs_qna_agent bootstrap
```

## Options

- `bootstrap`: Fetch all .md files from GitHub (default: adenhq/hive docs/)
- `run -q, --question`: One-shot question (required)
- `tui --bootstrap`: Fetch docs from GitHub before launching TUI (instead of local sync)
- `info`, `validate`: Standard metadata and validation
- `verify`: Check that docs are synced and show the path tools will use

## Troubleshooting

If the agent says "no documentation found":

1. **Run `verify`** to confirm docs exist at the expected path:
   ```bash
   PYTHONPATH=core:examples/templates uv run python -m docs_qna_agent verify
   ```

2. **Sync manually**:
   ```bash
   PYTHONPATH=core:examples/templates uv run python -m docs_qna_agent bootstrap
   ```

3. **Different workspace path** (e.g. Docker): set `HIVE_WORKSPACES_DIR` to the base workspaces path before running.
