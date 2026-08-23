"""HTTP Basic Auth boundary for the operator API."""

import os
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBasic,
    HTTPBasicCredentials,
    HTTPBearer,
)

ADMIN_USERNAME = "admin"
basic_security = HTTPBasic(auto_error=False)
agent_security = HTTPBearer(auto_error=False)


def require_basic_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_security)],
) -> str:
    """Validate operator credentials and fail closed when configuration is absent."""

    expected_password = os.getenv("BASIC_AUTH_PASSWORD")
    if credentials is None or expected_password is None:
        raise _unauthorized()

    username_matches = secrets.compare_digest(credentials.username, ADMIN_USERNAME)
    password_matches = secrets.compare_digest(credentials.password, expected_password)
    if not username_matches or not password_matches:
        raise _unauthorized()
    return credentials.username


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Basic"},
    )


def require_agent_credential(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(agent_security),
    ],
) -> str:
    """Extract an agent Bearer credential without logging or returning it."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials
