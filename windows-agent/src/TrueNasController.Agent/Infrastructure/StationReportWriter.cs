using System.Net.NetworkInformation;
using System.Text.Json;
using TrueNasController.Agent.Domain;

namespace TrueNasController.Agent.Infrastructure;

public static class StationReportWriter
{
    public const string DefaultAgentVersion = "0.2.0-native";

    public static Guid LoadOrCreateIdentity(string? identityPath = null)
    {
        var path = identityPath is null ? DefaultIdentityPath() : Path.GetFullPath(identityPath);
        try
        {
            var raw = JsonSerializer.Deserialize<Dictionary<string, string>>(
                File.ReadAllText(path), JsonDefaults.Options);
            if (raw is not null && raw.TryGetValue("agent_uuid", out var value) && Guid.TryParse(value, out var uuid))
            {
                return uuid;
            }

            throw new InvalidOperationException($"agent identity file is invalid: {path}");
        }
        catch (FileNotFoundException)
        {
            var uuid = Guid.NewGuid();
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, JsonSerializer.Serialize(
                new Dictionary<string, string> { ["agent_uuid"] = uuid.ToString("D") },
                JsonDefaults.Options));
            return uuid;
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException($"cannot read agent identity file: {path}", exception);
        }
    }

    public static string Write(
        string? outputPath,
        string? identityPath,
        string agentVersion,
        bool text)
    {
        var hostname = Environment.MachineName;
        var agentUuid = LoadOrCreateIdentity(identityPath);
        var network = new NetworkSnapshotCollector().Collect();
        var drive = ReadDrive();
        var report = new
        {
            report_version = "1",
            station = new
            {
                station_id = agentUuid,
                display_name = hostname,
                hostname,
                role = "client",
            },
            agent = new
            {
                agent_uuid = agentUuid,
                agent_version = agentVersion,
                hostname,
                platform = $"{Environment.OSVersion.Platform} {Environment.OSVersion.Version}".Trim(),
            },
            network = new
            {
                ip_addresses = network.IpAddresses,
                mac_addresses = network.MacAddresses,
            },
            drives = new[] { drive },
            collected_at = DateTimeOffset.UtcNow,
        };
        var json = JsonSerializer.Serialize(report, JsonDefaults.Options);
        if (!string.IsNullOrWhiteSpace(outputPath))
        {
            var path = Path.GetFullPath(outputPath);
            Directory.CreateDirectory(Path.GetDirectoryName(path)!);
            File.WriteAllText(path, json + Environment.NewLine);
            Console.WriteLine($"Station report written to: {path}");
        }

        if (text)
        {
            Console.WriteLine($"display_name: {hostname}");
            Console.WriteLine($"hostname: {hostname}");
            Console.WriteLine("role: client");
            Console.WriteLine($"agent_uuid: {agentUuid:D}");
            Console.WriteLine($"agent_version: {agentVersion}");
            Console.WriteLine();
        }

        Console.WriteLine(json);
        return json;
    }

    public static string DefaultIdentityPath()
    {
        var localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
        if (string.IsNullOrWhiteSpace(localAppData))
        {
            localAppData = OperatingSystem.IsWindows()
                ? @"C:\Users\Public\AppData\Local"
                : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".local", "state");
        }

        return Path.Combine(localAppData, "TrueNasController", "agent", "identity.json");
    }

    private static object ReadDrive()
    {
        try
        {
            var drive = new System.IO.DriveInfo("D:");
            return new
            {
                letter = "D:",
                present = drive.IsReady,
                free_bytes = drive.IsReady ? drive.AvailableFreeSpace : (long?)null,
            };
        }
        catch (Exception)
        {
            return new { letter = "D:", present = false, free_bytes = (long?)null };
        }
    }
}
