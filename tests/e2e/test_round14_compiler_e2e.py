"""Portable multi-graph compiler end-to-end tests.

The focused compiler suites own individual diagnostic rules. This file proves
that one real bundle containing agent, logic, subgraph, external-skill,
reference, example, action, and flat-registry products compiles as a whole.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from graph_skill_runtime.core.exceptions import SkillLoadError
from graph_skill_runtime.core.loader import CompiledSkill, SkillLoader
from graph_skill_runtime.core.manifest import AgentNodeAST, LogicNodeAST, SubgraphNodeAST
from graph_skill_runtime.core.skill_resolver_protocol import SkillResolutionError


class DictSkillResolver:
    """Minimal resolver mapping Agent Skills names to portable bundle roots."""

    def __init__(self, mapping: dict[str, Path]) -> None:
        self.mapping = mapping

    def resolve_skill(self, skill_id: str) -> Path:
        try:
            return self.mapping[skill_id]
        except KeyError as exc:
            raise SkillResolutionError(
                skill_id,
                "not registered by the test resolver",
                code="[F-v3-skill-not-registered]",
            ) from exc


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _external_echo_skill(root: Path) -> None:
    _write(
        root / "SKILL.md",
        """---
name: e2e-echo
description: Echo a review note for the caller.
---
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: Echo a review note for the caller.
io:
  inputs:
    type: object
    required: [note]
    properties:
      note: {type: string}
  outputs:
    type: object
    required: [echoed]
    properties:
      echoed: {type: string}
phases:
  - id: echo
    depends_on: [input]
    output: true
""",
    )
    _write(
        root / "phases" / "echo" / "LOGIC.md",
        """---
name: echo
io:
  inputs:
    type: object
    required: [note]
    properties:
      note: {type: string}
  outputs:
    type: object
    required: [echoed]
    properties:
      echoed: {type: string}
actions: [echo]
validator: false
---
<action>echo</action>
""",
    )
    _write(
        root / "phases" / "echo" / "actions" / "echo.py",
        "def echo(inputs):\n    return {'echoed': inputs['note']}\n",
    )


def _pipeline(root: Path) -> None:
    _write(
        root / "SKILL.md",
        """---
name: round14-e2e-pipeline
description: Compile a complete portable agent, logic, and subgraph pipeline.
---
Use graph-skill-runtime to compile and run this graph skill.
""",
    )
    _write(
        root / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: root
description: Full portable compiler pipeline.
io:
  inputs:
    type: object
    required: [chapter_content]
    properties:
      chapter_content: {type: string}
  outputs:
    type: object
    required: [report]
    properties:
      report: {type: string}
phases:
  - id: segment
    depends_on: [input]
    output: false
  - id: score
    depends_on: [segment]
    output: false
  - id: expand
    depends_on: [score]
    output: true
""",
    )
    _write(
        root / "phases" / "segment" / "AGENT.md",
        """---
name: segment
llm_role: analyst
io:
  inputs:
    type: object
    required: [chapter_content]
    properties:
      chapter_content: {type: string}
  outputs:
    type: object
    required: [segments]
    properties:
      segments:
        type: array
        items: {type: object}
subagents:
  - name: echo_helper
    target_skill: e2e-echo
    description: Echo a concise review note for an ambiguous boundary.
subgraphs:
  - name: deep_dive
    graph: e2e-expander
    description: Delegate deep expansion to the internal graph.
references:
  - id: R1
    path: references/segmentation-guide.md
    summary: Narrative segmentation decision rules.
examples:
  - id: E2
    path: examples/long-case.md
    summary: A mixed-timeline segmentation example.
max_iterations: 8
---
<role>
You are a narrative segmentation editor.
</role>

<goal>
Segment chapter_content using @reference:R1, @example:E2, and @example:E1.
</goal>

<step id="S1" name="read_reference">
Read the segmentation criteria from @reference:R1 and follow @protocol:P1.
</step>

<step id="S2" name="review_with_subagent">
Ask @subagent:echo_helper for a review note when a boundary is ambiguous.
</step>

<step id="S3" name="finish">
Call @tool:finish_task with structured segment data.
</step>

<protocol id="P1">
Keep setting explanation separate from physical events unless they are inseparable.
</protocol>

<example id="E1">
Separate a setting explanation from immediate character action.
</example>
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
        items: {type: object}
  outputs:
    type: object
    required: [brief]
    properties:
      brief: {type: string}
actions: [score]
validator: false
---
<action>score</action>
""",
    )
    _write(
        root / "phases" / "score" / "actions" / "score.py",
        "def score(inputs):\n"
        "    return {'brief': f\"scored {len(inputs['segments'])} segments\"}\n",
    )
    _write(
        root / "phases" / "expand" / "SUBGRAPH.md",
        """---
name: expand
graph: e2e-expander
allow_sequential_overwrite: [report]
io:
  inputs:
    type: object
    required: [brief]
    properties:
      brief: {type: string}
  outputs:
    type: object
    required: [report]
    properties:
      report: {type: string}
validator: false
---
""",
    )

    child = root / "graphs" / "e2e-expander"
    _write(
        child / "graph.yaml",
        """schema_version: gskill.graph.v1
graph_id: e2e-expander
description: Expand a scored brief into a report.
io:
  inputs:
    type: object
    required: [brief]
    properties:
      brief: {type: string}
  outputs:
    type: object
    required: [report]
    properties:
      report: {type: string}
phases:
  - id: build
    depends_on: [input]
    output: true
""",
    )
    _write(
        child / "phases" / "build" / "LOGIC.md",
        """---
name: build
io:
  inputs:
    type: object
    required: [brief]
    properties:
      brief: {type: string}
  outputs:
    type: object
    required: [report]
    properties:
      report: {type: string}
actions: [build]
validator: false
---
<action>build</action>
""",
    )
    _write(
        child / "phases" / "build" / "actions" / "build.py",
        "def build(inputs):\n    return {'report': inputs['brief']}\n",
    )
    _write(root / "references" / "segmentation-guide.md", "Segmentation rules.\n")
    _write(root / "examples" / "long-case.md", "A long mixed-timeline example.\n")


@pytest.fixture
def pipeline_root(tmp_path: Path) -> Path:
    root = tmp_path / "round14-e2e-pipeline"
    _pipeline(root)
    _external_echo_skill(tmp_path / "external" / "e2e-echo")
    return root


def _resolver_for(root: Path) -> DictSkillResolver:
    return DictSkillResolver({"e2e-echo": root.parent / "external" / "e2e-echo"})


def test_full_pipeline_skill_compiles_into_expected_products(pipeline_root: Path) -> None:
    compiled: CompiledSkill = SkillLoader().compile_skill(
        pipeline_root,
        skill_resolver=_resolver_for(pipeline_root),
    )

    assert compiled.skill_manifest.name == "round14-e2e-pipeline"
    assert compiled.manifest.schema_version == "gskill.graph.v1"
    assert compiled.manifest.graph_id == "root"
    assert [phase.id for phase in compiled.manifest.phases] == ["segment", "score", "expand"]
    assert sorted(compiled.manifest.io.inputs["properties"]) == ["chapter_content"]
    assert sorted(compiled.manifest.io.outputs["properties"]) == ["report"]
    assert sorted(compiled.graph_registry) == ["e2e-expander", "root"]

    topology = compiled.raw["graph_topology"]
    assert topology["order"] == ["segment", "score", "expand"]
    by_name = {entry["name"]: entry for entry in topology["phases"]}
    assert by_name["segment"]["depends_on"] == ["input"]
    assert by_name["score"]["depends_on"] == ["segment"]
    assert by_name["expand"]["depends_on"] == ["score"]
    assert by_name["expand"]["output"] is True

    modes = {node.phase_name: node.mode for node in compiled.nodes}
    assert modes == {"segment": "agent", "score": "logic", "expand": "subgraph"}

    segment = next(node.ast for node in compiled.nodes if node.phase_name == "segment")
    assert isinstance(segment, AgentNodeAST)
    assert segment.role == "You are a narrative segmentation editor."
    assert [step.id for step in segment.steps] == ["S1", "S2", "S3"]
    assert [reference.id for reference in segment.references] == ["R1"]
    assert [example.id for example in segment.examples] == ["E2"]
    assert [example.id for example in segment.examples_inline] == ["E1"]
    assert [(item.name, item.target_skill) for item in segment.subagents] == [
        ("echo_helper", "e2e-echo")
    ]
    assert [(item.name, item.graph) for item in segment.subgraphs] == [
        ("deep_dive", "e2e-expander")
    ]
    assert segment.max_iterations == 8

    score = next(node.ast for node in compiled.nodes if node.phase_name == "score")
    assert isinstance(score, LogicNodeAST)
    assert score.actions == ["score"]
    assert "score" in compiled.actions.for_phase("score")

    expand = next(node.ast for node in compiled.nodes if node.phase_name == "expand")
    assert isinstance(expand, SubgraphNodeAST)
    assert expand.graph == "e2e-expander"

    echo = compiled.subagents_by_phase["segment"][0]
    assert echo.target_skill == "e2e-echo"
    assert echo.root == pipeline_root.parent / "external" / "e2e-echo"
    assert sorted(echo.input_schema["properties"]) == ["note"]


def _schema_version_invalid(root: Path) -> None:
    graph = root / "graph.yaml"
    _write(graph, graph.read_text(encoding="utf-8").replace("gskill.graph.v1", "v0.3.0", 1))


def _agent_role_missing(root: Path) -> None:
    agent = root / "phases" / "segment" / "AGENT.md"
    text = agent.read_text(encoding="utf-8")
    start = text.index("<role>")
    end = text.index("</role>") + len("</role>\n\n")
    _write(agent, text[:start] + text[end:])


def _mention_target_missing(root: Path) -> None:
    agent = root / "phases" / "segment" / "AGENT.md"
    _write(
        agent,
        agent.read_text(encoding="utf-8").replace("@reference:R1", "@reference:UNKNOWN"),
    )


def _phase_mode_ambiguous(root: Path) -> None:
    _write(
        root / "phases" / "score" / "AGENT.md",
        "---\nname: score\n---\n<role>x</role>\n<goal>y</goal>\n",
    )


def _graph_cycle(root: Path) -> None:
    graph = root / "graph.yaml"
    _write(
        graph,
        graph.read_text(encoding="utf-8").replace(
            "  - id: segment\n    depends_on: [input]",
            "  - id: segment\n    depends_on: [expand]",
        ),
    )


def _physical_io(root: Path) -> None:
    _write(root / "io" / "inputs.json", "{}\n")


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (_schema_version_invalid, "[F-v3-graph-schema-version-mismatch]"),
        (_agent_role_missing, "[F-v3-agent-role-missing]"),
        (_mention_target_missing, "[F-v3-mention-target-not-found]"),
        (_phase_mode_ambiguous, "[F-v3-graph-phase-mode-ambiguous]"),
        (_graph_cycle, "[F-v3-graph-phase-cycle]"),
        (_physical_io, "[F-v3-graph-io-physical-file-deprecated]"),
    ],
)
def test_corrupted_pipeline_reports_precise_portable_diagnostic(
    pipeline_root: Path,
    mutate: Callable[[Path], None],
    expected_code: str,
) -> None:
    mutate(pipeline_root)

    with pytest.raises(SkillLoadError) as exc_info:
        SkillLoader().compile_skill(
            pipeline_root,
            skill_resolver=_resolver_for(pipeline_root),
        )

    assert exc_info.value.payload.code == expected_code
    assert exc_info.value.payload.source_path is not None


def test_unresolvable_subagent_target_raises_skill_not_registered(
    pipeline_root: Path,
) -> None:
    with pytest.raises(SkillResolutionError) as exc_info:
        SkillLoader().compile_skill(pipeline_root, skill_resolver=DictSkillResolver({}))

    assert exc_info.value.payload.code == "[F-v3-skill-not-registered]"


def test_missing_resolver_uses_default_local_resolver(pipeline_root: Path) -> None:
    with pytest.raises(SkillResolutionError) as exc_info:
        SkillLoader().compile_skill(pipeline_root)

    assert exc_info.value.payload.code == "[F-v3-skill-not-registered]"
