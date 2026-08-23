from typing import Any

import pytest

from truenas_adapter.runtime import (
    ApiKeyJsonRpcTransport,
    TrueNASAuthenticationError,
    TrueNASRuntimeConfig,
    TrueNASRuntimeConfigError,
)


class RecordingTransport:
    def __init__(self, authentication_result: Any = True) -> None:
        self.authentication_result = authentication_result
        self.calls: list[tuple[str, object | None]] = []
        self.closed = False

    async def request(self, method: str, params: object | None = None) -> object:
        self.calls.append((method, params))
        if method == "auth.login_with_api_key":
            return self.authentication_result
        return {"method": method}

    async def close(self) -> None:
        self.closed = True


def test_runtime_config_requires_full_websocket_url_and_secret() -> None:
    with pytest.raises(TrueNASRuntimeConfigError):
        TrueNASRuntimeConfig.from_env({"TRUENAS_API_KEY": "secret"})
    with pytest.raises(TrueNASRuntimeConfigError):
        TrueNASRuntimeConfig.from_env(
            {"TRUENAS_WS_URL": "http://nas.example/api/current", "TRUENAS_API_KEY": "secret"}
        )
    with pytest.raises(TrueNASRuntimeConfigError):
        TrueNASRuntimeConfig.from_env({"TRUENAS_WS_URL": "wss://nas.example/api/current"})


@pytest.mark.asyncio
async def test_api_key_transport_authenticates_without_leaking_secret() -> None:
    inner = RecordingTransport()
    transport = ApiKeyJsonRpcTransport(
        inner,
        api_key="test-only-secret",
        authentication_method="auth.login_with_api_key",
    )

    assert await transport.request("core.ping") == {"method": "core.ping"}
    assert inner.calls == [
        ("auth.login_with_api_key", ["test-only-secret"]),
        ("core.ping", None),
    ]


@pytest.mark.asyncio
async def test_api_key_transport_fails_closed_on_rejected_key() -> None:
    inner = RecordingTransport(authentication_result=False)
    transport = ApiKeyJsonRpcTransport(
        inner,
        api_key="test-only-secret",
        authentication_method="auth.login_with_api_key",
    )

    with pytest.raises(TrueNASAuthenticationError) as error:
        await transport.request("core.ping")
    assert "test-only-secret" not in str(error.value)
    assert inner.calls == [("auth.login_with_api_key", ["test-only-secret"])]
