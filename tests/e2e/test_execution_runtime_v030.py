from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.graph_assembler import assemble_graph


class ToolCallingChatModel:
    def __init__(self, calls: list[list[dict[str, Any]]] | None = None) -> None:
        self.calls = calls or [
            [
                {
                    "name": "finish_task",
                    "args": {"business_data_md": "## item-1\n- answer: ok\n"},
                    "id": "finish-1",
                }
            ]
        ]
        self.system_prompts: list[str] = []
        self.tool_messages: list[Any] = []

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> ToolCallingChatModel:
        del tools, kwargs
        return self

    def invoke(self, messages: list[Any]) -> AIMessage:
        self.system_prompts.append(str(messages[0].content))
        self.tool_messages.extend(message for message in messages if getattr(message, "name", None))
        tool_calls = self.calls.pop(0) if self.calls else []
        return AIMessage(content="", tool_calls=tool_calls)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _agent_skill(parent: Path) -> Path:
    root = parent / "e2e-agent"
    _write(
        root / "SKILL.md",
        """---
name: e2e-agent
description: Exercise portable agent execution end to end.
metadata:
  gskill: gskill.graph.v1
---
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise portable agent execution end to end.
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
phases:
  - id: main
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "main" / "AGENT.md",
        """---
name: main
io:
  inputs:
    type: object
    properties:
      topic:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
references:
  - id: R1
    path: references/r1.md
    summary: Runtime reference
examples:
  - id: E2
    path: examples/e2.md
    summary: Runtime document example
---
<role>
Executor.
</role>
<goal>
Use @reference:R1 and @example:E2.
</goal>
<step id="S1" name="Read">
Read the resource registries.
</step>
<protocol id="P1">
Cite evidence.
</protocol>
<example id="E1">
Inline example.
</example>
""",
    )
    _write(root / "references" / "r1.md", "reference body")
    _write(root / "examples" / "e2.md", "document example body")
    return root


def _subgraph_parent(parent: Path) -> Path:
    root = parent / "e2e-parent"
    child = root / "graphs" / "child"
    _write(
        root / "SKILL.md",
        """---
name: e2e-parent
description: Exercise flat-registry subgraph execution end to end.
metadata:
  gskill: gskill.graph.v1
---
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: Exercise flat-registry subgraph execution end to end.
io:
  inputs:
    type: object
    properties:
      public:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
      saw_parent_secret:
        type: boolean
phases:
  - id: sub
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "sub" / "SUBGRAPH.md",
        """---
name: sub
graph: child
io:
  inputs:
    type: object
    properties:
      public:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
      saw_parent_secret:
        type: boolean
---
""",
    )
    _write(
        child / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: child
description: Inspect isolated child graph inputs.
io:
  inputs:
    type: object
    properties:
      public:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
      saw_parent_secret:
        type: boolean
phases:
  - id: inspect
    depends_on: [input]
    output: true
""",
    )
    _write(
        child / "phases" / "inspect" / "LOGIC.md",
        """---
name: inspect
io:
  inputs:
    type: object
    properties:
      public:
        type: string
  outputs:
    type: object
    properties:
      answer:
        type: string
      saw_parent_secret:
        type: boolean
---
<action>inspect</action>
""",
    )
    _write(
        child / "phases" / "inspect" / "actions" / "inspect.py",
        "def inspect(inputs):\n"
        "    return {\n"
        "        'answer': inputs.get('public'),\n"
        "        'saw_parent_secret': inputs.get('parent_secret') is not None,\n"
        "    }\n",
    )
    return root


def test_minimal_agent_run_uses_cognitive_prompt_and_prefilled_knowledge_base(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    root = _agent_skill(tmp_path)
    chat = ToolCallingChatModel()

    compiled = compile_skill(root, cache=False, skill_resolver=mock_skill_resolver)
    assemble_graph(compiled, chat_model=chat, skill_resolver=mock_skill_resolver).graph.invoke(
        {"data": {"inputs": {"topic": "T"}}, "flow": {}, "messages": [], "run_id": "r1"}
    )

    prompt = chat.system_prompts[0]
    for slot in (
        "role",
        "goal",
        "thinking_style",
        "knowledge_base",
        "examples",
        "ambiguity_feedback",
        "protocol_citation",
        "critical_reminders",
    ):
        assert f"<{slot}>" in prompt
    knowledge_base = prompt[prompt.index("<knowledge_base>") : prompt.index("</knowledge_base>")]
    assert "reference body" in knowledge_base


def test_agent_can_call_read_example_for_declared_document_example(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    root = _agent_skill(tmp_path)
    chat = ToolCallingChatModel(
        [
            [{"name": "read_example", "args": {"example_id": "E2"}, "id": "read-example-1"}],
            [{"name": "finish_task", "args": {"business_data_md": "## item-1\n- answer: ok\n"}, "id": "finish-1"}],
        ]
    )

    compiled = compile_skill(root, cache=False, skill_resolver=mock_skill_resolver)
    assemble_graph(compiled, chat_model=chat, skill_resolver=mock_skill_resolver).graph.invoke(
        {"data": {"inputs": {"topic": "T"}}, "flow": {}, "messages": [], "run_id": "r1"}
    )

    assert any("document example body" in str(message.content) for message in chat.tool_messages)


def test_subgraph_path_runs_and_child_data_does_not_inherit_parent(
    tmp_path: Path,
    mock_skill_resolver: object,
) -> None:
    root = _subgraph_parent(tmp_path)

    compiled = compile_skill(root, cache=False, skill_resolver=mock_skill_resolver)
    result = assemble_graph(compiled, skill_resolver=mock_skill_resolver).graph.invoke(
        {
            "data": {
                "inputs": {"public": "visible"},
                "phase_outputs": {"parent": {"parent_secret": "hidden"}},
                "scratch": {"parent_secret": "hidden"},
            },
            "flow": {"trace": "parent"},
            "messages": ["parent-message"],
            "run_id": "r1",
        }
    )

    assert result["data"]["answer"] == "visible"
    assert result["data"]["saw_parent_secret"] is False
