"""Typed public contracts for explicit optional integration installation."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from graph_skill_runtime.domain.models import ContractModel


class IntegrationTarget(StrEnum):
    """Host ecosystems with a first-party projection renderer."""

    CLAUDE = "claude"
    CODEX = "codex"
    COPILOT = "copilot"
    CURSOR = "cursor"
    GEMINI = "gemini"
    OPENCODE = "opencode"


class IntegrationScope(StrEnum):
    """Whether a projection is visible to one project or the current user."""

    PROJECT = "project"
    USER = "user"


class IntegrationOperation(StrEnum):
    INSTALL = "install"
    UNINSTALL = "uninstall"


class IntegrationAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    REMOVE = "remove"
    UNCHANGED = "unchanged"


class IntegrationResourceKind(StrEnum):
    FILE = "file"
    JSON_ENTRY = "json_entry"
    TEXT_BLOCK = "text_block"


class IntegrationRequest(ContractModel):
    """Explicit authorization boundary for one multi-host operation."""

    schema_version: Literal["gskill.integration-request.v1"] = "gskill.integration-request.v1"
    kind: Literal["integration_request"] = "integration_request"
    integration_id: Literal["moirai"] = "moirai"
    targets: tuple[IntegrationTarget, ...] = Field(min_length=1)
    scope: IntegrationScope
    project_root: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def _validate_scope_and_targets(self) -> Self:
        if len(set(self.targets)) != len(self.targets):
            raise ValueError("targets must be unique")
        if self.scope is IntegrationScope.PROJECT and self.project_root is None:
            raise ValueError("project_root is required for project scope")
        if self.scope is IntegrationScope.USER and self.project_root is not None:
            raise ValueError("project_root is not valid for user scope")
        return self


class HostDetection(ContractModel):
    """Read-only evidence used to expand the CLI's ``detected`` target."""

    schema_version: Literal["gskill.host-detection.v1"] = "gskill.host-detection.v1"
    kind: Literal["host_detection"] = "host_detection"
    target: IntegrationTarget
    detected: bool
    executable: str | None = Field(default=None, min_length=1)
    evidence: str = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_executable_evidence(self) -> Self:
        if self.detected != (self.executable is not None):
            raise ValueError("detected and executable must describe the same discovery result")
        return self


class HostDetectionResult(ContractModel):
    """Complete, read-only detection report for every supported renderer."""

    schema_version: Literal["gskill.host-detection-result.v1"] = (
        "gskill.host-detection-result.v1"
    )
    kind: Literal["host_detection_result"] = "host_detection_result"
    detections: tuple[HostDetection, ...]

    @model_validator(mode="after")
    def _validate_complete_target_set(self) -> Self:
        targets = tuple(item.target for item in self.detections)
        if len(targets) != len(set(targets)):
            raise ValueError("host detections must contain each target exactly once")
        if set(targets) != set(IntegrationTarget):
            raise ValueError("host detections must cover every supported integration target")
        return self


class IntegrationChange(ContractModel):
    """One planned projection mutation or verified no-op."""

    schema_version: Literal["gskill.integration-change.v1"] = "gskill.integration-change.v1"
    kind: Literal["integration_change"] = "integration_change"
    target: IntegrationTarget
    resource_id: str = Field(min_length=1)
    resource_kind: IntegrationResourceKind
    action: IntegrationAction
    path: str = Field(min_length=1)
    selector: tuple[str, ...] = ()
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class IntegrationConflict(ContractModel):
    """A safety refusal that prevents every mutation in the operation."""

    schema_version: Literal["gskill.integration-conflict.v1"] = "gskill.integration-conflict.v1"
    kind: Literal["integration_conflict"] = "integration_conflict"
    target: IntegrationTarget
    resource_id: str = Field(min_length=1)
    path: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class IntegrationPlan(ContractModel):
    """Complete preflight result for a multi-host integration operation."""

    schema_version: Literal["gskill.integration-plan.v1"] = "gskill.integration-plan.v1"
    kind: Literal["integration_plan"] = "integration_plan"
    operation: IntegrationOperation
    integration_id: Literal["moirai"] = "moirai"
    asset_version: str = Field(min_length=1)
    scope: IntegrationScope
    targets: tuple[IntegrationTarget, ...] = Field(min_length=1)
    changes: tuple[IntegrationChange, ...] = ()
    conflicts: tuple[IntegrationConflict, ...] = ()
    can_apply: bool

    @model_validator(mode="after")
    def _validate_plan_consistency(self) -> Self:
        if len(self.targets) != len(set(self.targets)):
            raise ValueError("plan targets must be unique")
        if self.can_apply == bool(self.conflicts):
            raise ValueError("can_apply must be true exactly when the plan has no conflicts")
        target_set = set(self.targets)
        if any(change.target not in target_set for change in self.changes):
            raise ValueError("every planned change must belong to a requested target")
        if any(conflict.target not in target_set for conflict in self.conflicts):
            raise ValueError("every conflict must belong to a requested target")
        return self


class IntegrationResult(ContractModel):
    """Outcome returned by SDK and CLI after planning or applying once."""

    schema_version: Literal["gskill.integration-result.v1"] = "gskill.integration-result.v1"
    kind: Literal["integration_result"] = "integration_result"
    status: Literal["planned", "installed", "uninstalled", "unchanged", "conflict"]
    plan: IntegrationPlan
    applied_changes: int = Field(ge=0)

    @model_validator(mode="after")
    def _validate_result_consistency(self) -> Self:
        if self.status in {"planned", "conflict"} and self.applied_changes != 0:
            raise ValueError(f"{self.status} results cannot report applied changes")
        if self.status == "conflict" and self.plan.can_apply:
            raise ValueError("a conflict result requires a non-applicable plan")
        if self.status != "conflict" and not self.plan.can_apply:
            raise ValueError("only a conflict result may contain a non-applicable plan")
        if self.status == "installed" and self.plan.operation is not IntegrationOperation.INSTALL:
            raise ValueError("installed status requires an install plan")
        if self.status == "uninstalled" and self.plan.operation is not IntegrationOperation.UNINSTALL:
            raise ValueError("uninstalled status requires an uninstall plan")
        return self


__all__ = [
    "HostDetection",
    "HostDetectionResult",
    "IntegrationAction",
    "IntegrationChange",
    "IntegrationConflict",
    "IntegrationOperation",
    "IntegrationPlan",
    "IntegrationRequest",
    "IntegrationResourceKind",
    "IntegrationResult",
    "IntegrationScope",
    "IntegrationTarget",
]
