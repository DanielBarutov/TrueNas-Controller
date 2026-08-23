"""Composition root for the Game Update Controller API."""

import os

from fastapi import FastAPI

from application.lifecycle import CreateStationUseCase, EnrollAgentUseCase, ReceiveHeartbeatUseCase
from application.preflight import EvaluateStationPreflightUseCase
from application.publish_commands import CreatePublishJobUseCase
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
    return create_app(
        ListStationsUseCase(uow_factory),
        station_registry=CreateStationUseCase(uow_factory),
        enroll_agent=EnrollAgentUseCase(uow_factory),
        receive_heartbeat=ReceiveHeartbeatUseCase(uow_factory),
        evaluate_preflight=EvaluateStationPreflightUseCase(uow_factory),
        create_publish_job=CreatePublishJobUseCase(uow_factory),
        get_publish_job=GetPublishJobUseCase(uow_factory),
    )


app = build_app()
