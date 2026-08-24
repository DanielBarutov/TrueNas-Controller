"""FastAPI application factory and read-only routes."""

from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status

from application.agent_commands import (
    AcknowledgeAgentCommandUseCase,
    AgentCommandAcknowledgementRejectedError,
    AgentCommandAgentNotFoundError,
    AgentCommandIssueError,
    AgentCommandUnauthorizedError,
    IssueAgentCommandUseCase,
)
from application.lifecycle import (
    AgentUnauthorizedError,
    CreateStationUseCase,
    EnrollAgentUseCase,
    EnrollmentRejectedError,
    HeartbeatRejectedError,
    ReceiveHeartbeatUseCase,
)
from application.ports import StationListQuery
from application.preflight import EvaluateStationPreflightUseCase, StationNotFoundError
from application.publish_commands import (
    CreatePublishJobUseCase,
    PublishDraftValidationError,
    PublishIdempotencyConflictError,
    PublishJobNotFoundError,
)
from application.publish_confirmation import (
    PreparePublishJobUseCase,
    PublishConfirmationStateError,
)
from application.publish_dispatch import DispatchPublishJobUseCase, PublishDispatchStateError
from application.publish_queries import GetPublishJobUseCase
from domain.snapshot import DriveInfo, ProcessInfo, ProcessSnapshot
from presentation.auth import require_agent_credential, require_basic_auth
from presentation.lifecycle_schemas import (
    AgentCommandIssueRequest,
    AgentCommandIssueResponse,
    AgentCommandResponse,
    AgentEnrollRequest,
    AgentEnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    StationCreateRequest,
    StationRegistrationResponse,
)
from presentation.preflight_schemas import CheckResponse, PreflightRequest, PreflightResponse
from presentation.publish_schemas import (
    PublishDispatchResponse,
    PublishJobCreateRequest,
    PublishJobDraftResponse,
    PublishJobResponse,
    PublishPrepareRequest,
    PublishPrepareResponse,
)
from presentation.schemas import StationResponse


def create_app(
    station_query: StationListQuery,
    station_registry: CreateStationUseCase | None = None,
    enroll_agent: EnrollAgentUseCase | None = None,
    receive_heartbeat: ReceiveHeartbeatUseCase | None = None,
    evaluate_preflight: EvaluateStationPreflightUseCase | None = None,
    create_publish_job: CreatePublishJobUseCase | None = None,
    get_publish_job: GetPublishJobUseCase | None = None,
    prepare_publish_job: PreparePublishJobUseCase | None = None,
    dispatch_publish_job: DispatchPublishJobUseCase | None = None,
    issue_agent_command: IssueAgentCommandUseCase | None = None,
    acknowledge_agent_command: AcknowledgeAgentCommandUseCase | None = None,
) -> FastAPI:
    """Create the HTTP application from application-layer dependencies."""

    app = FastAPI(title="Game Update Controller")

    @app.get("/health", dependencies=[Depends(require_basic_auth)])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/stations", response_model=list[StationResponse])
    async def list_stations(
        include_disabled: bool = Query(default=False),
        _: Annotated[str, Depends(require_basic_auth)] = "",
    ) -> list[StationResponse]:
        stations = await station_query.execute(include_disabled=include_disabled)
        return [StationResponse.from_domain(station) for station in stations]

    if station_registry is not None:

        @app.post(
            "/api/v1/stations",
            response_model=StationRegistrationResponse,
            status_code=status.HTTP_201_CREATED,
        )
        async def create_station(
            payload: StationCreateRequest,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> StationRegistrationResponse:
            result = await station_registry.execute(
                station_id=payload.station_id,
                display_name=payload.display_name,
                hostname=payload.hostname,
                role=payload.role,
            )
            return StationRegistrationResponse(
                **StationResponse.from_domain(result.station).model_dump(),
                enrollment_token=result.enrollment_token,
                enrollment_expires_at=result.enrollment_expires_at,
            )

    if enroll_agent is not None:

        @app.post("/api/v1/agents/enroll", response_model=AgentEnrollResponse)
        async def enroll(
            payload: AgentEnrollRequest,
        ) -> AgentEnrollResponse:
            try:
                result = await enroll_agent.execute(
                    enrollment_token=payload.enrollment_token,
                    agent_uuid=payload.agent_uuid,
                    hostname=payload.hostname,
                    agent_version=payload.agent_version,
                    ip_addresses=tuple(payload.ip_addresses),
                    mac_addresses=tuple(payload.mac_addresses),
                )
            except EnrollmentRejectedError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            return AgentEnrollResponse(
                station_id=result.station_id,
                credential=result.credential,
                server_time=result.server_time,
            )

    if receive_heartbeat is not None:

        @app.post("/api/v1/agents/heartbeat", response_model=HeartbeatResponse)
        async def heartbeat(
            payload: HeartbeatRequest,
            credential: Annotated[str, Depends(require_agent_credential)],
        ) -> HeartbeatResponse:
            snapshot = ProcessSnapshot(
                station_id=payload.station_id,
                captured_at=payload.captured_at,
                agent_version=payload.agent_version,
                processes=tuple(
                    ProcessInfo(name=item.name, pid=item.pid, path=item.path)
                    for item in payload.processes
                ),
                drives=tuple(
                    DriveInfo(
                        letter=item.letter,
                        present=item.present,
                        free_bytes=item.free_bytes,
                    )
                    for item in payload.drives
                ),
            )
            try:
                result = await receive_heartbeat.execute(
                    credential=credential,
                    snapshot=snapshot,
                    hostname=payload.hostname,
                    ip_addresses=tuple(payload.ip_addresses)
                    if payload.ip_addresses is not None
                    else None,
                    mac_addresses=tuple(payload.mac_addresses)
                    if payload.mac_addresses is not None
                    else None,
                )
            except AgentUnauthorizedError as error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(error),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from error
            except HeartbeatRejectedError as error:
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error
            return HeartbeatResponse(
                status="accepted",
                station_id=result.station_id,
                received_at=result.received_at,
                commands=[
                    AgentCommandResponse(
                        command_id=command.id,
                        name=command.name.value,
                        expires_at=command.expires_at,
                        signature=command.signature,
                    )
                    for command in result.commands
                ],
            )

    if issue_agent_command is not None:

        @app.post(
            "/api/v1/agents/{agent_uuid}/commands",
            response_model=AgentCommandIssueResponse,
            status_code=status.HTTP_201_CREATED,
        )
        async def issue_command(
            agent_uuid: UUID,
            payload: AgentCommandIssueRequest,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> AgentCommandIssueResponse:
            try:
                command = await issue_agent_command.execute(
                    agent_uuid=agent_uuid,
                    name=payload.name,
                    ttl=timedelta(seconds=payload.ttl_seconds),
                )
            except AgentCommandAgentNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            except AgentCommandIssueError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=str(error),
                ) from error
            return AgentCommandIssueResponse(
                command_id=command.id,
                name=command.name.value,
                expires_at=command.expires_at,
                status=command.status.value,
            )

    if acknowledge_agent_command is not None:

        @app.post(
            "/api/v1/agents/commands/{command_id}/ack",
            status_code=status.HTTP_204_NO_CONTENT,
        )
        async def acknowledge_command(
            command_id: UUID,
            credential: Annotated[str, Depends(require_agent_credential)],
        ) -> None:
            try:
                await acknowledge_agent_command.execute(
                    credential=credential,
                    command_id=command_id,
                )
            except AgentCommandUnauthorizedError as error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=str(error),
                    headers={"WWW-Authenticate": "Bearer"},
                ) from error
            except AgentCommandAcknowledgementRejectedError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error

    if evaluate_preflight is not None:

        @app.post("/api/v1/preflight", response_model=PreflightResponse)
        async def preflight(
            payload: PreflightRequest,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> PreflightResponse:
            try:
                report = await evaluate_preflight.execute(
                    station_id=payload.station_id,
                    max_snapshot_age=timedelta(seconds=payload.max_snapshot_age_seconds),
                    required_drive_letter=payload.required_drive_letter,
                    min_free_bytes=payload.min_free_bytes,
                )
            except StationNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            return PreflightResponse(
                station_id=report.station_id,
                status=report.status,
                can_publish=report.can_publish,
                evaluated_at=report.evaluated_at,
                checks=[
                    CheckResponse(
                        status=check.status,
                        code=check.code,
                        message=check.message,
                        observed_at=check.observed_at,
                        source_snapshot_id=check.source_snapshot_id,
                    )
                    for check in report.checks
                ],
            )

    if create_publish_job is not None:

        @app.post(
            "/api/v1/publish/jobs",
            response_model=PublishJobDraftResponse,
            status_code=status.HTTP_201_CREATED,
        )
        async def create_publish_job_route(
            payload: PublishJobCreateRequest,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> PublishJobDraftResponse:
            try:
                draft = await create_publish_job.execute(
                    label=payload.label,
                    game_name=payload.game_name,
                    description=payload.description,
                    station_ids=tuple(payload.station_ids),
                    idempotency_key=payload.idempotency_key,
                    correlation_id=payload.correlation_id or uuid4(),
                    dry_run=payload.dry_run,
                    allow_hot_switch=payload.allow_hot_switch,
                )
            except PublishIdempotencyConflictError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            except PublishDraftValidationError as error:
                raise HTTPException(
                    status_code=422,
                    detail=str(error),
                ) from error
            return PublishJobDraftResponse.from_draft(draft)

    if get_publish_job is not None:

        @app.get(
            "/api/v1/publish/jobs/{job_id}",
            response_model=PublishJobResponse,
        )
        async def get_publish_job_route(
            job_id: UUID,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> PublishJobResponse:
            try:
                view = await get_publish_job.execute(job_id)
            except PublishJobNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            return PublishJobResponse.from_view(view)

    if prepare_publish_job is not None:

        @app.post(
            "/api/v1/publish/jobs/{job_id}/prepare",
            response_model=PublishPrepareResponse,
        )
        async def prepare_publish_job_route(
            job_id: UUID,
            payload: PublishPrepareRequest,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> PublishPrepareResponse:
            try:
                result = await prepare_publish_job.execute(
                    job_id=job_id,
                    admin_station_id=payload.admin_station_id,
                    confirmation=payload.confirmation,
                )
            except PublishJobNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            except PublishConfirmationStateError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            return PublishPrepareResponse.from_result(result)

    if dispatch_publish_job is not None:

        @app.post(
            "/api/v1/publish/jobs/{job_id}/dispatch",
            response_model=PublishDispatchResponse,
        )
        async def dispatch_publish_job_route(
            job_id: UUID,
            _: Annotated[str, Depends(require_basic_auth)],
        ) -> PublishDispatchResponse:
            try:
                result = await dispatch_publish_job.execute(job_id=job_id)
            except PublishJobNotFoundError as error:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=str(error),
                ) from error
            except PublishDispatchStateError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            return PublishDispatchResponse(
                job_id=result.job.id,
                status=result.job.status,
            )

    return app
