from uuid import uuid4

import pytest

from agent.config import AgentConfig, AgentConfigError


def test_agent_config_requires_safe_runtime_values() -> None:
    station_id = uuid4()
    config = AgentConfig.from_env(
        {
            "AGENT_API_BASE_URL": "https://controller.example",
            "AGENT_STATION_ID": str(station_id),
            "AGENT_VERSION": "0.1.0",
            "AGENT_HOSTNAME": "CLIENT-01",
            "AGENT_CREDENTIAL_PATH": "C:\\ProgramData\\controller\\credential",
            "AGENT_COMMAND_VERIFY_KEY": "public-key-for-test",
        }
    )

    assert config.station_id == station_id
    assert config.heartbeat_url == "https://controller.example/api/v1/agents/heartbeat"
    assert config.enrollment_url == "https://controller.example/api/v1/agents/enroll"
    assert config.command_verify_key == "public-key-for-test"


def test_agent_config_rejects_missing_or_insecure_defaults() -> None:
    with pytest.raises(AgentConfigError):
        AgentConfig.from_env({})
    with pytest.raises(AgentConfigError):
        AgentConfig.from_env(
            {
                "AGENT_API_BASE_URL": "http://controller.example",
                "AGENT_STATION_ID": str(uuid4()),
                "AGENT_VERSION": "0.1.0",
                "AGENT_HOSTNAME": "CLIENT-01",
                "AGENT_CREDENTIAL_PATH": "credential",
            }
        )
