using System.Text.Json;
using System.Text.Json.Serialization;

namespace TrueNasController.Agent.Domain;

public sealed record AgentConfig(
    [property: JsonPropertyName("controller_url")] string ControllerUrl,
    [property: JsonPropertyName("station_id")] Guid StationId,
    [property: JsonPropertyName("agent_uuid")] Guid AgentUuid,
    [property: JsonPropertyName("agent_version")] string AgentVersion,
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("credential_path")] string CredentialPath,
    [property: JsonPropertyName("command_verify_key")] string? CommandVerifyKey = null,
    [property: JsonPropertyName("allow_insecure_http")] bool AllowInsecureHttp = false,
    [property: JsonPropertyName("heartbeat_interval_seconds")] int HeartbeatIntervalSeconds = 10,
    [property: JsonPropertyName("drive_letter")] string DriveLetter = "D:")
{
    public static AgentConfig Load(string path)
    {
        var json = File.ReadAllText(path);
        var config = JsonSerializer.Deserialize<AgentConfig>(json, JsonDefaults.Options);
        return config ?? throw new InvalidOperationException("agent configuration is empty");
    }

    public void Save(string path)
    {
        var directory = Path.GetDirectoryName(path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var temporaryPath = $"{path}.{Guid.NewGuid():N}.tmp";
        File.WriteAllText(temporaryPath, JsonSerializer.Serialize(this, JsonDefaults.Options));
        File.Move(temporaryPath, path, overwrite: true);
    }

    public string HeartbeatUrl => $"{ControllerUrl.TrimEnd('/')}/api/v1/agents/heartbeat";

    public string EnrollmentUrl => $"{ControllerUrl.TrimEnd('/')}/api/v1/agents/enroll";
}

public sealed record ProcessInfo(
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("pid")] int? Pid,
    [property: JsonPropertyName("path")] string? Path);

public sealed record DriveInfo(
    [property: JsonPropertyName("letter")] string Letter,
    [property: JsonPropertyName("present")] bool Present,
    [property: JsonPropertyName("free_bytes")] long? FreeBytes);

public sealed record HeartbeatPayload(
    [property: JsonPropertyName("protocol_version")] string ProtocolVersion,
    [property: JsonPropertyName("station_id")] Guid StationId,
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("ip_addresses")] IReadOnlyList<string> IpAddresses,
    [property: JsonPropertyName("mac_addresses")] IReadOnlyList<string> MacAddresses,
    [property: JsonPropertyName("agent_version")] string AgentVersion,
    [property: JsonPropertyName("captured_at")] DateTimeOffset CapturedAt,
    [property: JsonPropertyName("processes")] IReadOnlyList<ProcessInfo> Processes,
    [property: JsonPropertyName("drives")] IReadOnlyList<DriveInfo> Drives);

public sealed record HeartbeatResponse(
    [property: JsonPropertyName("status")] string Status,
    [property: JsonPropertyName("station_id")] Guid StationId,
    [property: JsonPropertyName("received_at")] DateTimeOffset ReceivedAt,
    [property: JsonPropertyName("commands")] IReadOnlyList<AgentCommand> Commands);

public sealed record AgentCommand(
    [property: JsonPropertyName("command_id")] Guid CommandId,
    [property: JsonPropertyName("name")] string Name,
    [property: JsonPropertyName("expires_at")] DateTimeOffset ExpiresAt,
    [property: JsonPropertyName("signature")] string Signature);

public sealed record EnrollmentResponse(
    [property: JsonPropertyName("station_id")] Guid StationId,
    [property: JsonPropertyName("credential")] string Credential,
    [property: JsonPropertyName("server_time")] DateTimeOffset ServerTime);

public sealed record StationReport(
    [property: JsonPropertyName("report_version")] string ReportVersion,
    [property: JsonPropertyName("station")] StationReportStation Station,
    [property: JsonPropertyName("agent")] StationReportAgent Agent);

public sealed record StationReportStation(
    [property: JsonPropertyName("station_id")] string StationId,
    [property: JsonPropertyName("display_name")] string DisplayName,
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("role")] string Role);

public sealed record StationReportAgent(
    [property: JsonPropertyName("agent_uuid")] string AgentUuid,
    [property: JsonPropertyName("agent_version")] string AgentVersion,
    [property: JsonPropertyName("hostname")] string Hostname,
    [property: JsonPropertyName("platform")] string Platform);

public static class JsonDefaults
{
    public static readonly JsonSerializerOptions Options = new(JsonSerializerDefaults.Web)
    {
        WriteIndented = true,
        PropertyNameCaseInsensitive = true,
    };
}
