# Templates

A template is a working agent scaffold that follows the standard Hive export structure. Copy it, rename it, customize the goal/nodes/edges, and run it.

## What's in a template

Each template is a complete agent package:

```
template_name/
├── __init__.py       # Package exports
├── __main__.py       # CLI entry point
├── agent.py          # Goal, edges, graph spec, agent class
├── agent.json        # Agent definition (used by build-from-template)
├── config.py         # Runtime configuration
├── nodes/
│   └── __init__.py   # Node definitions (NodeSpec instances)
└── README.md         # What this template demonstrates
```

## How to use a template

### Option 1: Build from template (recommended)

Use the `/hive-create` skill and select "From a template" to interactively pick a template, customize the goal/nodes/graph, and export a new agent.

### Option 2: Manual copy

```bash
# 1. Copy to your exports directory
cp -r examples/templates/deep_research_agent exports/my_research_agent

# 2. Update the module references in __main__.py and __init__.py

# 3. Customize goal, nodes, edges, and prompts

# 4. Run it
uv run python -m exports.my_research_agent --input '{"topic": "..."}'
```

## Available templates

| Template | Description |
|----------|-------------|
| [deep_research_agent](deep_research_agent/) | Interactive research agent that searches diverse sources, evaluates findings with user checkpoints, and produces a cited HTML report |
| [docs_qna_agent](docs_qna_agent/) | Answers questions about Hive documentation using pre-populated markdown files; cites sources and says "I don't know" when docs don't contain the answer |
| [email_inbox_management](email_inbox_management/) | Manages Gmail inbox using user-defined free-text rules — fetches emails, applies rules (trash, spam, star, labels), and executes Gmail actions |
| [job_hunter](job_hunter/) | Analyzes resume, finds matching job opportunities, lets user select which to pursue, then generates resume customization and cold outreach emails |
| [tech_news_reporter](tech_news_reporter/) | Researches the latest technology and AI news from the web and produces a well-organized report |
| [vulnerability_assessment](vulnerability_assessment/) | Passive OSINT-based website vulnerability scanner — SSL, headers, DNS, ports, tech stack; produces letter-grade risk scores and remediation reports |
