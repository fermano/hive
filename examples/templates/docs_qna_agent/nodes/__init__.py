"""Node definitions for Docs QnA Agent."""

from framework.graph import NodeSpec

qna_node = NodeSpec(
    id="qna_node",
    name="Docs QnA",
    description="Answer questions about Hive docs using list_dir, grep_search, and view_file",
    node_type="event_loop",
    client_facing=True,
    max_node_visits=0,
    input_keys=["question"],
    output_keys=["response"],
    success_criteria=(
        "Answer is grounded in the docs, cites sources, and says 'I don't know' "
        "when the docs do not contain the answer."
    ),
    system_prompt="""\
You are a documentation Q&A assistant. Answer the user's question using only the pre-populated docs.

**Workflow (use these tools):**
1. list_docs(path=".") — list files in docs root (e.g. getting-started.md, key_concepts/)
2. search_docs(pattern="<regex>", path=".") — find files containing text
3. read_doc(path="<file>") — read full content (e.g. "getting-started.md" or "key_concepts/graph.md")

**Search budget — do NOT loop forever:**
- After 2–3 search_docs and 2–3 read_doc calls, if you haven't found the answer, STOP.
- Say "I don't know" or "The docs don't cover this" and call set_output.

**Rules:**
- Ground every claim in the docs — cite file and section.
- If not in docs, say "I don't know." Never invent information.
- Keep answers concise but complete.

**STEP 1:** Use list_docs, search_docs, read_doc to find and read relevant docs, then answer.
**STEP 2:** Call set_output("response", "<your answer or 'I don't know'>")
""",
    tools=["list_docs", "search_docs", "read_doc"],
)

__all__ = ["qna_node"]
