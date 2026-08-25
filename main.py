"""Composition root for the Game Update Controller API."""

import base64
import binascii
import os

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI

from agent.command_signing import Ed25519CommandSigner
from application.agent_commands import (
    AcknowledgeAgentCommandUseCase,
    IssueAgentCommandUseCase,
)
from application.lifecycle import (
    BootstrapAgentUseCase,
    CreateProvisioningTokenUseCase,
    CreateStationUseCase,
    DeleteStationUseCase,
    EnrollAgentUseCase,
    ReceiveHeartbeatUseCase,
)
from application.preflight import EvaluateStationPreflightUseCase
from application.process_rules import (
    CreateProcessRuleUseCase,
    DeleteProcessRuleUseCase,
    ListProcessRulesUseCase,
)
from application.publish_commands import CreatePublishJobUseCase
from application.publish_confirmation import PreparePublishJobUseCase
from application.publish_dispatch import DispatchPublishJobUseCase
from application.publish_queries import GetPublishJobUseCase, ListPublishJobsUseCase
from application.stations import (
    ListStationsUseCase,
    UpdateStationStorageMappingUseCase,
    UpdateStationUseCase,
)
from presentation.http import create_app
from repository.database import create_engine, create_session_factory
from repository.uow import SqlAlchemyUnitOfWorkFactory


def build_app(database_url: str | None = None) -> FastAPI:
    """Wire concrete infrastructure without executing migrations."""

    resolved_database_url = database_url or os.getenv(
        "DATABASE_URL", "sqlite+aiosqlite:///./local.db"
    )
    engine = create_engine(resolved_database_url)
    session_factory = create_session_factory(engine)
    uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
    command_signer = _command_signer_from_env()
    preflight = EvaluateStationPreflightUseCase(uow_factory)
    return create_app(
        ListStationsUseCase(uow_factory),
        station_registry=CreateStationUseCase(uow_factory),
        provisioning_token=CreateProvisioningTokenUseCase(uow_factory),
        delete_station=DeleteStationUseCase(uow_factory),
        enroll_agent=EnrollAgentUseCase(uow_factory),
        bootstrap_agent=BootstrapAgentUseCase(uow_factory),
        receive_heartbeat=ReceiveHeartbeatUseCase(uow_factory),
        evaluate_preflight=preflight,
        list_process_rules=ListProcessRulesUseCase(uow_factory),
        create_process_rule=CreateProcessRuleUseCase(uow_factory),
        delete_process_rule=DeleteProcessRuleUseCase(uow_factory),
        create_publish_job=CreatePublishJobUseCase(uow_factory),
        get_publish_job=GetPublishJobUseCase(uow_factory),
        list_publish_jobs=ListPublishJobsUseCase(uow_factory),
        update_station=UpdateStationUseCase(uow_factory),
        update_station_storage_mapping=UpdateStationStorageMappingUseCase(uow_factory),
        prepare_publish_job=PreparePublishJobUseCase(uow_factory, preflight),
        dispatch_publish_job=DispatchPublishJobUseCase(uow_factory),
        issue_agent_command=(
            IssueAgentCommandUseCase(uow_factory, command_signer)
            if command_signer is not None
            else None
        ),
        acknowledge_agent_command=AcknowledgeAgentCommandUseCase(uow_factory),
    )


def _command_signer_from_env() -> Ed25519CommandSigner | None:
    """Load the controller signing key without placing it in source or logs."""

    encoded_key = os.getenv("AGENT_COMMAND_SIGNING_PRIVATE_KEY", "").strip()
    if not encoded_key:
        return None
    try:
        private_key_bytes = base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    except (ValueError, binascii.Error) as exc:
        raise RuntimeError("AGENT_COMMAND_SIGNING_PRIVATE_KEY is invalid") from exc
    return Ed25519CommandSigner(private_key)


app = build_app()
