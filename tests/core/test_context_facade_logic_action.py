"""MVP1 drift coverage for LOGIC actions no longer receiving Context facade."""

from __future__ import annotations

from pathlib import Path

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.graph_assembler import assemble_graph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _score_logic_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        """---
name: inputs-facade-score
description: Score segments with a deterministic LOGIC action.
---
Compile and run this graph skill with graph-skill-runtime.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: inputs-facade-score
description: Score segments with a deterministic LOGIC action.
io:
  inputs:
    type: object
    required: [segments]
    properties:
      segments:
        type: array
        items:
          type: object
  outputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
phases:
  - id: score
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "score" / "LOGIC.md",
        """---
name: score
io:
  inputs:
    type: object
    required: [segments]
    properties:
      segments:
        type: array
        items:
          type: object
  outputs:
    type: object
    required: [report]
    properties:
      report:
        type: string
actions: [score]
validator: false
---
<action>score</action>
""",
    )
    _write(
        root / "phases" / "score" / "actions" / "score.py",
        "def score(inputs):\n"
        "    segments = inputs['segments']\n"
        "    return {'report': f'{type(inputs).__name__}:scored {len(segments)} segments'}\n",
    )


def test_logic_action_receives_plain_dict_not_context_facade(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = tmp_path / "inputs-facade-score"
    _score_logic_skill(skill_root)
    compiled = compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)

    result = assemble_graph(compiled, skill_resolver=mock_skill_resolver).graph.invoke(
        {
            "data": {"inputs": {"segments": [{"content": "opening"}]}},
            "flow": {},
            "messages": [],
            "run_id": "r1",
        }
    )

    assert result["data"]["phase_outputs"]["score"] == {"report": "dict:scored 1 segments"}
