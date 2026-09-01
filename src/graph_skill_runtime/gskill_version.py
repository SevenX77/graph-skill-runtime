"""Single compatibility identity for the runtime and portable gSkill syntax."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Final, Literal, get_args

GSKILL_MAJOR: Final = 1
GSKILL_SCHEMA_VERSION: Final = "gskill.graph.v1"
GSKILL_METADATA_KEY: Final = "gskill"
GSkillSchemaVersion = Literal["gskill.graph.v1"]


def distribution_major(distribution_version: str) -> int:
    """Return the positive major component of a PEP 440-compatible release string."""

    head, separator, _tail = distribution_version.partition(".")
    if not separator or not head.isascii() or not head.isdigit():
        raise ValueError(f"invalid graph-skill-runtime version: {distribution_version!r}")
    major = int(head)
    if major < 1:
        raise ValueError("graph-skill-runtime major version must be positive")
    return major


def assert_version_contract() -> None:
    """Fail if the installed distribution and portable syntax majors drift."""

    if get_args(GSkillSchemaVersion) != (GSKILL_SCHEMA_VERSION,):
        raise RuntimeError("gSkill schema version constant and Literal type disagree")
    try:
        distribution_version = version("graph-skill-runtime")
    except PackageNotFoundError:
        return
    if distribution_major(distribution_version) != GSKILL_MAJOR:
        raise RuntimeError(
            "graph-skill-runtime distribution major and gSkill syntax major disagree"
        )


assert_version_contract()


__all__ = [
    "GSKILL_MAJOR",
    "GSKILL_METADATA_KEY",
    "GSKILL_SCHEMA_VERSION",
    "GSkillSchemaVersion",
    "distribution_major",
]
