"""Ed25519 signing and verification for server-issued agent commands."""

import base64
from datetime import datetime
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from agent.protocol import ServerCommand
from domain.agent_command import canonical_command_payload


class CommandSigningError(ValueError):
    """A command signing key or signature encoding is invalid."""


class Ed25519CommandSigner:
    """Sign only the versioned command fields sent to agents."""

    def __init__(self, private_key: Ed25519PrivateKey) -> None:
        self._private_key = private_key

    def sign(self, command_id: UUID, name: str, expires_at: datetime) -> str:
        payload = canonical_command_payload(command_id, name, expires_at)
        signature = self._private_key.sign(payload)
        return _encode(signature)


class Ed25519CommandVerifier:
    """Callable verifier suitable for ``AgentCommandValidator``."""

    def __init__(self, public_key: Ed25519PublicKey) -> None:
        self._public_key = public_key

    @classmethod
    def from_base64(cls, encoded_key: str) -> "Ed25519CommandVerifier":
        """Build a verifier from an external URL-safe base64 public key."""

        if not encoded_key:
            raise CommandSigningError("command public key is missing")
        try:
            raw_key = base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
            public_key = Ed25519PublicKey.from_public_bytes(raw_key)
        except (ValueError, TypeError, base64.binascii.Error) as exc:
            raise CommandSigningError("command public key is invalid") from exc
        return cls(public_key)

    def __call__(self, command: ServerCommand) -> bool:
        try:
            signature = _decode(command.signature)
            payload = canonical_command_payload(
                command.command_id,
                command.name,
                command.expires_at,
            )
            self._public_key.verify(signature, payload)
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    if not value or len(value) > 128:
        raise CommandSigningError("command signature has an invalid length")
    try:
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, base64.binascii.Error) as exc:
        raise CommandSigningError("command signature is not valid base64") from exc
