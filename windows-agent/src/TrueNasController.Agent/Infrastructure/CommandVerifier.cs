using System.Globalization;
using System.Text;
using System.Text.Json;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;
using TrueNasController.Agent.Domain;

namespace TrueNasController.Agent.Infrastructure;

public sealed class CommandVerifier
{
    private readonly Ed25519PublicKeyParameters _publicKey;

    private CommandVerifier(Ed25519PublicKeyParameters publicKey)
    {
        _publicKey = publicKey;
    }

    public static CommandVerifier? FromBase64Url(string? encoded)
    {
        if (string.IsNullOrWhiteSpace(encoded))
        {
            return null;
        }

        try
        {
            var value = encoded.Trim();
            var raw = Convert.FromBase64String(value.Replace('-', '+').Replace('_', '/')
                .PadRight(value.Length + ((4 - value.Length % 4) % 4), '='));
            if (raw.Length != 32)
            {
                throw new FormatException("Ed25519 public key must contain 32 bytes");
            }

            return new CommandVerifier(new Ed25519PublicKeyParameters(raw, 0));
        }
        catch (Exception exception) when (exception is FormatException or ArgumentException)
        {
            throw new InvalidOperationException("command verify key is not valid base64url Ed25519", exception);
        }
    }

    public bool Verify(AgentCommand command)
    {
        if (command.Name != "refresh_process_snapshot" ||
            command.ExpiresAt.ToUniversalTime() <= DateTimeOffset.UtcNow ||
            string.IsNullOrWhiteSpace(command.Signature))
        {
            return false;
        }

        try
        {
            var encoded = command.Signature.Replace('-', '+').Replace('_', '/');
            var signature = Convert.FromBase64String(
                encoded.PadRight(encoded.Length + ((4 - encoded.Length % 4) % 4), '='));
            if (signature.Length != 64)
            {
                return false;
            }

            var signer = new Ed25519Signer();
            signer.Init(false, _publicKey);
            var payload = CanonicalPayload(command);
            signer.BlockUpdate(payload, 0, payload.Length);
            return signer.VerifySignature(signature);
        }
        catch (FormatException)
        {
            return false;
        }
    }

    private static byte[] CanonicalPayload(AgentCommand command)
    {
        var expiresAt = command.ExpiresAt.UtcDateTime.ToString(
            "yyyy-MM-dd'T'HH:mm:ss.ffffff+00:00",
            CultureInfo.InvariantCulture);
        var json = JsonSerializer.Serialize(new
        {
            command_id = command.CommandId.ToString("D"),
            expires_at = expiresAt,
            name = command.Name,
            protocol_version = "1",
        }, new JsonSerializerOptions
        {
            WriteIndented = false,
        });
        return Encoding.UTF8.GetBytes(json);
    }
}
