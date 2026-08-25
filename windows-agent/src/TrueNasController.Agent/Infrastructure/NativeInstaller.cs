using System.Text.Json;
using System.Security.Cryptography;
using TrueNasController.Agent.Application;
using TrueNasController.Agent.Domain;

namespace TrueNasController.Agent.Infrastructure;

public static class NativeInstaller
{
    public static async Task InstallAsync(IReadOnlyList<string> args, CancellationToken cancellationToken)
    {
        EnsureWindows();
        var controllerUrl = Required(args, "--controller-url");
        var reportPath = Required(args, "--report");
        var report = LoadReport(reportPath);
        var stationId = ParseUuid(report.Station.StationId, "station.station_id");
        var agentUuid = ParseUuid(report.Agent.AgentUuid, "agent.agent_uuid");
        if (stationId != agentUuid)
        {
            throw new InvalidOperationException(
                "station.station_id and agent.agent_uuid must be the same stable UUID from station-report.json");
        }
        var installDirectory = Path.GetFullPath(
            CommandLine.Value(args, "--install-dir") ??
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData), "TrueNasController", "agent"));
        var agentVersion = CommandLine.Value(args, "--agent-version") ?? report.Agent.AgentVersion;
        var allowInsecureHttp = CommandLine.Has(args, "--allow-insecure-http");
        var commandVerifyKey = CommandLine.Value(args, "--command-verify-key");
        var sourceExecutable = CommandLine.Value(args, "--source-executable") ?? Environment.ProcessPath;

        if (string.IsNullOrWhiteSpace(sourceExecutable) || !File.Exists(sourceExecutable))
        {
            throw new InvalidOperationException(
                "native installer must be launched from the published TrueNasControllerAgent.exe");
        }

        var credentialPath = Path.Combine(installDirectory, "agent.credential");
        var configPath = Path.Combine(installDirectory, "agent.json");
        var targetExecutable = Path.Combine(installDirectory, "TrueNasControllerAgent.exe");
        WindowsServiceManager.TryStop();
        Directory.CreateDirectory(installDirectory);
        if (!Path.GetFullPath(sourceExecutable).Equals(Path.GetFullPath(targetExecutable), StringComparison.OrdinalIgnoreCase))
        {
            File.Copy(sourceExecutable, targetExecutable, overwrite: true);
        }

        var config = new AgentConfig(
            ControllerUrl: controllerUrl.TrimEnd('/'),
            StationId: stationId,
            AgentUuid: agentUuid,
            AgentVersion: agentVersion,
            Hostname: report.Agent.Hostname,
            CredentialPath: credentialPath,
            CommandVerifyKey: commandVerifyKey,
            AllowInsecureHttp: allowInsecureHttp);

        if (CommandLine.Has(args, "--dry-run"))
        {
            using var _ = new ControllerClient(config);
            Console.WriteLine($"source: {sourceExecutable}");
            Console.WriteLine($"install: {installDirectory}");
            Console.WriteLine($"service: {WindowsServiceManager.ServiceName} (LocalSystem)");
            Console.WriteLine($"controller: {config.ControllerUrl}");
            Console.WriteLine($"station: {config.StationId:D}");
            Console.WriteLine($"agent: {config.AgentUuid:D} / {config.Hostname} / {config.AgentVersion}");
            Console.WriteLine("dry-run: no token requested and no files or services changed");
            return;
        }

        config.Save(configPath);

        var store = new JsonFileCredentialStore(credentialPath);
        Console.WriteLine("[1/5] Проверка защищённого хранилища DPAPI");
        store.Preflight();
        string? credential = null;
        if (store.Exists)
        {
            try
            {
                credential = store.Load(out var legacyUserScope);
                using var client = new ControllerClient(config);
                var probe = new SnapshotCollector().Collect(config);
                await client.SendHeartbeatAsync(probe, credential, cancellationToken);
                Console.WriteLine("[2/5] Существующий credential подтверждён для этой station");
                if (legacyUserScope)
                {
                    Console.WriteLine("[2/5] Переписываю старый credential в область LocalMachine");
                    store.Save(credential);
                }
            }
            catch (ControllerUnauthorizedException)
            {
                Console.WriteLine(
                    "[2/5] Старый credential отклонён для этой station; требуется новый enrollment");
                store.Clear();
                credential = null;
            }
            catch (CryptographicException)
            {
                Console.WriteLine("[2/5] Старый credential повреждён; требуется новый enrollment");
                store.Clear();
                credential = null;
            }
            catch (InvalidOperationException exception) when (exception.Message.Contains("stored agent credential", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("[2/5] Старый credential повреждён; требуется новый enrollment");
                store.Clear();
                credential = null;
            }
        }

        if (credential is null)
        {
            Console.WriteLine("[2/5] Введите одноразовый enrollment-токен (ввод отображается)");
            var token = Console.ReadLine()?.Trim();
            if (string.IsNullOrWhiteSpace(token))
            {
                throw new InvalidOperationException("enrollment token cannot be empty");
            }

            var network = new NetworkSnapshotCollector().Collect();
            using var client = new ControllerClient(config);
            var enrollment = await client.EnrollAsync(token, network.IpAddresses, network.MacAddresses, cancellationToken);
            if (enrollment.StationId != stationId)
            {
                throw new InvalidOperationException(
                    $"Controller returned station {enrollment.StationId}, expected {stationId}");
            }

            store.Save(enrollment.Credential);
            credential = enrollment.Credential;
        }

        if (string.IsNullOrWhiteSpace(credential))
        {
            throw new InvalidOperationException("agent credential is empty after enrollment");
        }

        Console.WriteLine("[3/5] Регистрация Windows Service от имени LocalSystem");
        WindowsServiceManager.Install(targetExecutable, configPath);
        Console.WriteLine("[4/5] Запуск Windows Service");
        WindowsServiceManager.StartAndWait();
        Console.WriteLine("[5/5] Готово: агент отправляет heartbeat");
        Console.WriteLine($"Service: {WindowsServiceManager.ServiceName}");
    }

    private static StationReport LoadReport(string path)
    {
        try
        {
            var report = JsonSerializer.Deserialize<StationReport>(
                File.ReadAllText(path), JsonDefaults.Options);
            if (report is null || report.ReportVersion != "1" || report.Station.Role != "client")
            {
                throw new InvalidOperationException("station report version or role is unsupported");
            }

            return report;
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException($"cannot read station report: {path}", exception);
        }
        catch (IOException exception)
        {
            throw new InvalidOperationException($"cannot read station report: {path}", exception);
        }
    }

    private static string Required(IReadOnlyList<string> args, string name) =>
        CommandLine.Value(args, name) is { Length: > 0 } value
            ? value
            : throw new InvalidOperationException($"required argument is missing: {name}");

    private static Guid ParseUuid(string value, string field) =>
        Guid.TryParse(value, out var result)
            ? result
            : throw new InvalidOperationException($"{field} must be a UUID");

    private static void EnsureWindows()
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new PlatformNotSupportedException("native installer requires Windows");
        }
    }
}
