using System.Diagnostics;
using TrueNasController.Agent.Domain;

namespace TrueNasController.Agent.Infrastructure;

public sealed class SnapshotCollector
{
    private readonly NetworkSnapshotCollector _network = new();

    public HeartbeatPayload Collect(AgentConfig config)
    {
        var (ipAddresses, macAddresses) = _network.Collect();
        return new HeartbeatPayload(
            ProtocolVersion: "1",
            StationId: config.StationId,
            Hostname: config.Hostname,
            IpAddresses: ipAddresses,
            MacAddresses: macAddresses,
            AgentVersion: config.AgentVersion,
            CapturedAt: DateTimeOffset.UtcNow,
            Processes: CollectProcesses(),
            Drives: CollectDrives(config.DriveLetter));
    }

    private static IReadOnlyList<Domain.ProcessInfo> CollectProcesses()
    {
        var processes = new List<Domain.ProcessInfo>();
        foreach (var process in Process.GetProcesses())
        {
            try
            {
                string? path = null;
                try
                {
                    path = process.MainModule?.FileName;
                }
                catch (Exception)
                {
                    // Reading another process path can be denied under LocalSystem.
                }

                processes.Add(new Domain.ProcessInfo(
                    $"{process.ProcessName}.exe",
                    process.Id,
                    path));
            }
            catch (Exception)
            {
                // A process can exit between enumeration and inspection.
            }
            finally
            {
                process.Dispose();
            }
        }

        return processes
            .OrderBy(item => item.Name, StringComparer.OrdinalIgnoreCase)
            .ThenBy(item => item.Pid)
            .Take(512)
            .ToArray();
    }

    private static IReadOnlyList<Domain.DriveInfo> CollectDrives(string requestedLetter)
    {
        var letter = requestedLetter.Trim().TrimEnd('\\').ToUpperInvariant();
        if (!letter.EndsWith(":", StringComparison.Ordinal))
        {
            letter += ":";
        }

        try
        {
            var drive = new System.IO.DriveInfo(letter);
            return new[]
            {
                new Domain.DriveInfo(letter, drive.IsReady, drive.IsReady ? drive.AvailableFreeSpace : null),
            };
        }
        catch (IOException)
        {
            return new[] { new Domain.DriveInfo(letter, false, null) };
        }
        catch (UnauthorizedAccessException)
        {
            return new[] { new Domain.DriveInfo(letter, false, null) };
        }
    }
}
