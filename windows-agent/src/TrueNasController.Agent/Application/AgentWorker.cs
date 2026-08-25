using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using TrueNasController.Agent.Domain;
using TrueNasController.Agent.Infrastructure;

namespace TrueNasController.Agent.Application;

public sealed class AgentWorker : BackgroundService
{
    private readonly string _configPath;
    private readonly ILogger<AgentWorker> _logger;

    public AgentWorker(string configPath, ILogger<AgentWorker> logger)
    {
        _configPath = configPath;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        // Loading config and DPAPI happens after the Windows service has entered
        // the running state. This keeps slow disk/crypto/network work out of SCM
        // startup and avoids the classic 1053 timeout.
        AgentConfig config;
        string credential;
        try
        {
            config = AgentConfig.Load(_configPath);
            var store = new JsonFileCredentialStore(config.CredentialPath);
            credential = store.Load();
        }
        catch (Exception exception)
        {
            _logger.LogError(exception, "agent configuration or credential cannot be loaded");
            return;
        }

        var verifier = CommandVerifier.FromBase64Url(config.CommandVerifyKey);
        var collector = new SnapshotCollector();
        using var client = new ControllerClient(config);
        var acknowledged = new HashSet<Guid>();
        var interval = TimeSpan.FromSeconds(Math.Clamp(config.HeartbeatIntervalSeconds, 1, 3600));

        _logger.LogInformation("TrueNAS Controller Agent started for station {StationId}", config.StationId);
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                var response = await SendHeartbeatAsync(
                    config,
                    credential,
                    collector,
                    client,
                    stoppingToken);
                await ProcessCommandsAsync(
                    response.Commands ?? Array.Empty<AgentCommand>(),
                    config,
                    credential,
                    collector,
                    client,
                    verifier,
                    acknowledged,
                    stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception exception)
            {
                _logger.LogWarning(exception, "agent heartbeat cycle failed; retrying later");
            }

            try
            {
                await Task.Delay(interval, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                break;
            }
        }

        _logger.LogInformation("TrueNAS Controller Agent stopped");
    }

    private static Task<HeartbeatResponse> SendHeartbeatAsync(
        AgentConfig config,
        string credential,
        SnapshotCollector collector,
        ControllerClient client,
        CancellationToken cancellationToken) =>
        client.SendHeartbeatAsync(collector.Collect(config), credential, cancellationToken);

    private async Task ProcessCommandsAsync(
        IReadOnlyList<AgentCommand> commands,
        AgentConfig config,
        string credential,
        SnapshotCollector collector,
        ControllerClient client,
        CommandVerifier? verifier,
        HashSet<Guid> acknowledged,
        CancellationToken cancellationToken)
    {
        if (commands.Count == 0)
        {
            return;
        }

        if (verifier is null)
        {
            _logger.LogWarning(
                "Controller returned {Count} command(s), but no command verify key is configured",
                commands.Count);
            return;
        }

        foreach (var command in commands)
        {
            if (acknowledged.Contains(command.CommandId) || !verifier.Verify(command))
            {
                _logger.LogWarning("Rejected an invalid or expired agent command {CommandId}", command.CommandId);
                continue;
            }

            if (command.Name == "refresh_process_snapshot")
            {
                await SendHeartbeatAsync(config, credential, collector, client, cancellationToken);
                await client.AcknowledgeAsync(command.CommandId, credential, cancellationToken);
                acknowledged.Add(command.CommandId);
                _logger.LogInformation("Executed and acknowledged command {CommandId}", command.CommandId);
            }
        }
    }
}
