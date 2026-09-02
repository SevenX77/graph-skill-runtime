from __future__ import annotations

import json
import re
from pathlib import Path

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.graph_assembler import assemble_graph


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _base(root: Path, phases: str) -> None:
    phase_entries = []
    for match in re.finditer(r'<phase id="([^"]+)" src="([^"]+)" depends_on="([^"]*)"', phases):
        deps = [dep for dep in re.split(r"[\s,]+", match.group(3).strip()) if dep]
        phase_entries.append((match.group(1), deps))
    depended_on = {dep for _, deps in phase_entries for dep in deps}
    phase_yaml = "\n".join(
        "\n".join(
            (
                f"  - id: {phase_id}",
                "    depends_on: [{deps}]".format(deps=", ".join(deps) if deps else "input"),
                f"    output: {str(phase_id not in depended_on).lower()}",
            )
        )
        for phase_id, deps in phase_entries
    )
    _write(
        root / "SKILL.md",
        f"""---
name: {root.name}
description: Phase outputs flow fixture for gamma2 dataflow coverage.
---
Compile and run this graph skill with graph-skill-runtime.
""",
    )
    _write(
        root / "graph.yaml",
        f"""schema_version: gskill.graph.v1
graph_id: gamma2-flow
description: Phase outputs flow fixture for gamma2 dataflow coverage.
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    type: object
    properties:
      review_input:
        type: string
phases:
{phase_yaml}
""",
    )


def _logic_action(root: Path, phase: str, action: str, body: str, outputs: list[str] | None = None) -> None:
    output_properties = {}
    if outputs is not None:
        for out in outputs:
            output_properties[out] = {"type": "string"}
    else:
        output_properties = {
            "segments_summary": {"type": "string"},
            "review_input": {"type": "string"},
        }
    output_yaml = json.dumps({"type": "object", "properties": output_properties}, ensure_ascii=False, indent=4).replace("\n", "\n    ")
    _write(
        root / "phases" / phase / "LOGIC.md",
        f"""---
name: {phase}
io:
  inputs:
    type: object
    properties: {{}}
  outputs:
    {output_yaml}
---
<action>{action}</action>
""",
    )
    _write(root / "phases" / phase / "actions" / f"{action}.py", body)


def test_downstream_phase_reads_upstream_phase_outputs_in_same_graph(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    skill_root = tmp_path / "gamma2-flow"
    _base(
        skill_root,
        '<phase id="segment" src="phases/segment" depends_on="" />\n'
        '<phase id="review" src="phases/review" depends_on="segment" />\n',
    )
    _logic_action(
        skill_root,
        "segment",
        "segment",
        "def segment(inputs):\n    return {'segments_summary': 'chapter summary'}\n",
        outputs=["segments_summary"],
    )
    _logic_action(
        skill_root,
        "review",
        "review",
        "def review(inputs):\n"
        "    return {'review_input': inputs.get('segments_summary', 'missing')}\n",
        outputs=["review_input"],
    )

    compiled = compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)
    result = assemble_graph(compiled, skill_resolver=mock_skill_resolver).graph.invoke(
        {"data": {"inputs": {}}, "flow": {}, "messages": [], "run_id": "r1"}
    )

    assert result["data"]["phase_outputs"]["review"] == {"review_input": "chapter summary"}
