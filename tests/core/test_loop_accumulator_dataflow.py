"""A loop phase provides its accumulator downstream — nothing else.

Decision doc: .kiro/specs/decision-2026-08-15-engine-loop-accumulator-dataflow.md

At runtime a `iterate.mode=loop` phase writes exactly one thing to the
blackboard: `accumulate.var`, after the last round
(`graph_assembler.py:_build_loop_iterate_phase`). Its `io.outputs` describes
something else entirely — the contract for ONE round of the body, which is
validated on every round and must contain `accumulate.from`.

The compile-time dataflow checker used to read `io.outputs` as "what this phase
provides", so the two disagreed and no skill could satisfy both: naming the
accumulator in `io.outputs` made every round fail output validation, and
leaving it out made every downstream consumer of the accumulator a compile
error.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from graph_skill_runtime.core.compiler import compile_skill
from graph_skill_runtime.core.exceptions import SkillLoadError

_GRAPH = """schema_version: gskill.graph.v1
graph_id: root
description: Exercise loop accumulator dataflow.
io:
  inputs:
    type: object
    required: [items]
    properties:
      items: {type: array, items: {type: object}}
  outputs:
    type: object
    required: [report]
    properties:
      report: {type: string}
phases:
  - id: crunch
    depends_on: [input]
    output: false
  - id: finalize
    depends_on: [crunch]
    output: true
"""

# The body produces `round_result` every round; the engine folds that into the
# `tally` accumulator and writes ONLY `tally` to the blackboard at the end.
_CRUNCH = """---
name: crunch
actions:
  - crunch_one
validator: false
iterate:
  mode: loop
  over: items
  item_var: current_item
  accumulate:
    var: tally
    init: {}
    from: round_result
    merge: merge
io:
  inputs:
    type: object
    required: [items, current_item, tally]
    properties:
      items: {type: array, items: {type: object}}
      current_item: {type: object}
      tally: {type: object}
  outputs:
    type: object
    required: [round_result]
    properties:
      round_result: {type: object}
---
<action>crunch_one</action>
"""

_FINALIZE = """---
name: finalize
actions:
  - render_report
validator: false
io:
  inputs:
    type: object
    required: [{finalize_input}]
    properties:
      {finalize_input}: {{type: object}}
  outputs:
    type: object
    required: [report]
    properties:
      report: {{type: string}}
---
<action>render_report</action>
"""

_CRUNCH_ACTION = '''def crunch_one(inputs):
    return {"round_result": {str(inputs["current_item"]["id"]): True}}
'''

_FINALIZE_ACTION = '''def render_report(inputs):
    return {"report": "done"}
'''


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _loop_skill(parent: Path, *, finalize_input: str) -> Path:
    root = parent / "loop-accumulator"
    _write(
        root / "SKILL.md",
        """---
name: loop-accumulator
description: Exercise loop accumulator dataflow.
metadata:
  gskill: gskill.graph.v1
---
""",
    )
    _write(root / "graph.yaml", _GRAPH)
    _write(root / "phases" / "crunch" / "LOGIC.md", _CRUNCH)
    _write(root / "phases" / "crunch" / "actions" / "crunch_one.py", _CRUNCH_ACTION)
    _write(root / "phases" / "finalize" / "LOGIC.md", _FINALIZE.format(finalize_input=finalize_input))
    _write(root / "phases" / "finalize" / "actions" / "render_report.py", _FINALIZE_ACTION)
    return root


def test_downstream_may_consume_the_accumulator(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    """`finalize` reads `tally`, the accumulator the loop actually writes. That
    is the only field the loop puts on the blackboard, so it must compile."""
    skill_root = _loop_skill(tmp_path, finalize_input="tally")

    compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)  # must not raise


def test_downstream_may_not_consume_a_per_round_output(
    tmp_path: Path, mock_skill_resolver: object
) -> None:
    """`round_result` is the per-round body contract, folded into the
    accumulator and then dropped. A downstream phase asking for it is reading a
    field that never reaches the blackboard, and compile must say so."""
    skill_root = _loop_skill(tmp_path, finalize_input="round_result")

    with pytest.raises(SkillLoadError) as exc_info:
        compile_skill(skill_root, cache=False, skill_resolver=mock_skill_resolver)

    issues = list(getattr(exc_info.value.compile_result, "issues", []) or [])
    codes = {str(getattr(issue, "rule_id", getattr(issue, "code", ""))) for issue in issues}
    assert "[F-v3-graph-dataflow-source-missing]" in codes, codes
    assert any("round_result" in str(getattr(issue, "message", "")) for issue in issues), issues
