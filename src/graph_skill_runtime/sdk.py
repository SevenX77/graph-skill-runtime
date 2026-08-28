"""Thin Python facade over the same application service used by CLI and MCP."""

from __future__ import annotations

from graph_skill_runtime.application.service import RuntimeApplication
from graph_skill_runtime.composition import create_application
from graph_skill_runtime.domain.models import (
    CompileRequest,
    CompileResult,
    ConfigResolution,
    GoldenEvaluationRequest,
    GoldenEvaluationResult,
    InspectRequest,
    InspectResult,
    PredictRequest,
    ResumeRequest,
    RunInvocation,
    RunPreset,
    RunResult,
    RuntimeProfileOverlay,
    SubmitAgentResultRequest,
)
from graph_skill_runtime.integrations.installer import IntegrationInstaller
from graph_skill_runtime.integrations.models import (
    HostDetectionResult,
    IntegrationPlan,
    IntegrationRequest,
    IntegrationResult,
)


def _application(application: RuntimeApplication | None) -> RuntimeApplication:
    return application if application is not None else create_application()


def compile(
    request: CompileRequest, *, application: RuntimeApplication | None = None
) -> CompileResult:
    return _application(application).compile(request)


def resolve_run(
    invocation: RunInvocation,
    *,
    portable_runtime: RuntimeProfileOverlay | None = None,
    portable_defaults: RunPreset | None = None,
    application: RuntimeApplication | None = None,
) -> ConfigResolution:
    return _application(application).resolve_run(
        invocation,
        portable_runtime=portable_runtime,
        portable_defaults=portable_defaults,
    )


def predict(
    request: PredictRequest, *, application: RuntimeApplication | None = None
) -> RunResult:
    return _application(application).predict(request)


def run(
    invocation: RunInvocation, *, application: RuntimeApplication | None = None
) -> RunResult:
    return _application(application).run(invocation)


def resume(
    request: ResumeRequest, *, application: RuntimeApplication | None = None
) -> RunResult:
    return _application(application).resume(request)


def submit_agent_result(
    request: SubmitAgentResultRequest,
    *,
    application: RuntimeApplication | None = None,
) -> RunResult:
    return _application(application).submit_agent_result(request)


def evaluate_golden(
    request: GoldenEvaluationRequest,
    *,
    application: RuntimeApplication | None = None,
) -> GoldenEvaluationResult:
    return _application(application).evaluate_golden(request)


def inspect(
    request: InspectRequest, *, application: RuntimeApplication | None = None
) -> InspectResult:
    return _application(application).inspect(request)


def detect_integration_hosts(
    *, installer: IntegrationInstaller | None = None
) -> HostDetectionResult:
    """Report PATH-based host discovery without writing any host state."""

    active_installer = installer or IntegrationInstaller()
    return HostDetectionResult(detections=active_installer.detect_hosts())


def plan_integration_install(
    request: IntegrationRequest,
    *,
    installer: IntegrationInstaller | None = None,
) -> IntegrationPlan:
    return (installer or IntegrationInstaller()).plan_install(request)


def install_integration(
    request: IntegrationRequest,
    *,
    installer: IntegrationInstaller | None = None,
) -> IntegrationResult:
    return (installer or IntegrationInstaller()).install(request)


def plan_integration_uninstall(
    request: IntegrationRequest,
    *,
    installer: IntegrationInstaller | None = None,
) -> IntegrationPlan:
    return (installer or IntegrationInstaller()).plan_uninstall(request)


def uninstall_integration(
    request: IntegrationRequest,
    *,
    installer: IntegrationInstaller | None = None,
) -> IntegrationResult:
    return (installer or IntegrationInstaller()).uninstall(request)
