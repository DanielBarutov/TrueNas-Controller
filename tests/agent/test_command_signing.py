import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
import pytest

from agent.command_signing import (
    CommandSigningError,
    Ed25519CommandSigner,
    Ed25519CommandVerifier,
)
from agent.protocol import AgentCommandValidator, ServerCommand


def test_ed25519_command_signature_round_trips_through_validator() -> None:
    private_key = Ed25519PrivateKey.generate()
    signer = Ed25519CommandSigner(private_key)
    command = ServerCommand(
        uuid4(),
        "refresh_process_snapshot",
        datetime(2026, 8, 23, 12, 1, tzinfo=UTC),
        "",
    )
    signed = ServerCommand(
        command.command_id,
        command.name,
        command.expires_at,
        signer.sign(command.command_id, command.name, command.expires_at),
    )

    validated = AgentCommandValidator(Ed25519CommandVerifier(private_key.public_key())).validate(
        signed,
        now=datetime(2026, 8, 23, 12, tzinfo=UTC),
    )

    assert validated == signed


def test_ed25519_command_signature_rejects_tampering_and_wrong_key() -> None:
    private_key = Ed25519PrivateKey.generate()
    command = ServerCommand(
        uuid4(),
        "refresh_process_snapshot",
        datetime.now(UTC) + timedelta(minutes=1),
        "",
    )
    signature = Ed25519CommandSigner(private_key).sign(
        command.command_id,
        command.name,
        command.expires_at,
    )
    verifier = Ed25519CommandVerifier(private_key.public_key())

    assert (
        verifier(ServerCommand(command.command_id, "run_shell", command.expires_at, signature))
        is False
    )
    assert (
        verifier(ServerCommand(command.command_id, command.name, command.expires_at, "bad"))
        is False
    )
    assert (
        Ed25519CommandVerifier(Ed25519PrivateKey.generate().public_key())(
            ServerCommand(command.command_id, command.name, command.expires_at, signature)
        )
        is False
    )


def test_ed25519_verifier_loads_external_public_key_only() -> None:
    private_key = Ed25519PrivateKey.generate()
    encoded_key = base64.urlsafe_b64encode(private_key.public_key().public_bytes_raw())
    encoded_key = encoded_key.rstrip(b"=").decode("ascii")

    verifier = Ed25519CommandVerifier.from_base64(encoded_key)

    assert verifier is not None
    with pytest.raises(CommandSigningError):
        Ed25519CommandVerifier.from_base64("not-a-public-key")
