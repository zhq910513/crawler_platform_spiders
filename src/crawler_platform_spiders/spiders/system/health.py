from __future__ import annotations

from pydantic import Field

from crawler_platform_spiders.context import TaskContext
from crawler_platform_spiders.errors import AuthenticationError
from crawler_platform_spiders.models import StrictModel, TaskResult
from crawler_platform_spiders.registry import task


class HealthParameters(StrictModel):
    message: str = Field(default="health check passed", min_length=1, max_length=200)
    sleep_seconds: float = Field(default=0.0, ge=0.0, le=10.0)
    raise_login_error: bool = False


@task(
    "system.health",
    description="Validate runner, structured logs, cancellation and error propagation.",
    parameter_model=HealthParameters,
    default_timeout_seconds=60,
)
def run(context: TaskContext) -> TaskResult:
    params = context.parameters_as(HealthParameters)
    context.logger.info("Health task started", event="health_started")
    if params.sleep_seconds:
        context.sleep(params.sleep_seconds)
    if params.raise_login_error:
        raise AuthenticationError(
            "SYSTEM.LOGIN_FAILED",
            "Simulated login failure",
            retryable=False,
        )
    context.logger.info(params.message, event="health_completed")
    return TaskResult.success(params.message, metrics={"healthy": True})
