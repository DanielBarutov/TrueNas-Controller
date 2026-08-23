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
from application.lifecycle import CreateStationUseCase, EnrollAgentUseCase, ReceiveHeartbeatUseCase
from application.preflight import EvaluateStationPreflightUseCase
from application.publish_commands import CreatePublishJobUseCase
from application.publish_confirmation import PreparePublishJobUseCase
from application.publish_dispatch import DispatchPublishJobUseCase
from application.publish_queries import GetPublishJobUseCase
from application.stations import ListStationsUseCase
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
        enroll_agent=EnrollAgentUseCase(uow_factory),
        receive_heartbeat=ReceiveHeartbeatUseCase(uow_factory),
        evaluate_preflight=preflight,
        create_publish_job=CreatePublishJobUseCase(uow_factory),
        get_publish_job=GetPublishJobUseCase(uow_factory),
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
