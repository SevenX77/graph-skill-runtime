from __future__ import annotations

import pytest
from pydantic import ValidationError

from graph_skill_runtime.integrations.models import (
    HostDetection,
    HostDetectionResult,
    IntegrationOperation,
    IntegrationPlan,
    IntegrationResult,
    IntegrationScope,
    IntegrationTarget,
)


def _detections() -> tuple[HostDetection, ...]:
    return tuple(
        HostDetection(
            target=target,
            detected=False,
            evidence=f"{target.value} is not on PATH",
        )
        for target in IntegrationTarget
    )


def _plan(operation: IntegrationOperation = IntegrationOperation.INSTALL) -> IntegrationPlan:
    return IntegrationPlan(
        operation=operation,
        asset_version="test",
        scope=IntegrationScope.USER,
        targets=(IntegrationTarget.CODEX,),
        can_apply=True,
    )


def test_host_detection_requires_executable_exactly_when_detected() -> None:
    with pytest.raises(ValidationError, match="detected and executable"):
        HostDetection(
            target=IntegrationTarget.CODEX,
            detected=True,
            evidence="claimed detection without a path",
        )


def test_host_detection_result_requires_each_supported_target_once() -> None:
    with pytest.raises(ValidationError, match="every supported integration target"):
        HostDetectionResult(detections=_detections()[:-1])

    assert HostDetectionResult(detections=_detections()).detections == _detections()


def test_plan_rejects_a_can_apply_value_that_contradicts_conflicts() -> None:
    with pytest.raises(ValidationError, match="can_apply"):
        IntegrationPlan(
            operation=IntegrationOperation.INSTALL,
            asset_version="test",
            scope=IntegrationScope.USER,
            targets=(IntegrationTarget.CODEX,),
            can_apply=False,
        )


def test_result_status_must_match_plan_operation() -> None:
    with pytest.raises(ValidationError, match="uninstalled status requires"):
        IntegrationResult(status="uninstalled", plan=_plan(), applied_changes=1)

    result = IntegrationResult(
        status="uninstalled",
        plan=_plan(IntegrationOperation.UNINSTALL),
        applied_changes=1,
    )
    assert result.status == "uninstalled"
