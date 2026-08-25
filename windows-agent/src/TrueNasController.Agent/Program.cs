using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using TrueNasController.Agent.Application;
using TrueNasController.Agent.Infrastructure;

return await NativeAgentProgram.RunAsync(args);

internal static class NativeAgentProgram
{
    private const string ServiceCommand = "--service";

    public static async Task<int> RunAsync(string[] args)
    {
        try
        {
            var command = args.FirstOrDefault()?.ToLowerInvariant();
            switch (command)
            {
                case "report":
                    StationReportWriter.Write(
                        CommandLine.Value(args, "--output"),
                        CommandLine.Value(args, "--identity-path"),
                        CommandLine.Value(args, "--agent-version") ?? StationReportWriter.DefaultAgentVersion,
                        CommandLine.Has(args, "--text"));
                    return 0;

                case "install":
                    await NativeInstaller.InstallAsync(args, CancellationToken.None);
                    return 0;

                case "remove":
                    WindowsServiceManager.Remove();
                    Console.WriteLine("Windows Service removed");
                    return 0;

                case "start":
                    WindowsServiceManager.StartAndWait();
                    Console.WriteLine("Windows Service is running");
                    return 0;

                case "stop":
                    WindowsServiceManager.Stop();
                    Console.WriteLine("Windows Service stopped");
                    return 0;

                case "foreground":
                    return await RunHostAsync(
                        CommandLine.Value(args, "--config") ?? DefaultConfigPath(),
                        useWindowsService: false);

                case ServiceCommand:
                case null:
                    return await RunHostAsync(
                        CommandLine.Value(args, "--config") ?? DefaultConfigPath(),
                        useWindowsService: true);

                default:
                    PrintUsage();
                    return 2;
            }
        }
        catch (Exception exception)
        {
            Console.Error.WriteLine($"ERROR: {exception.Message}");
            return 1;
        }
    }

    private static async Task<int> RunHostAsync(string configPath, bool useWindowsService)
    {
        var builder = Host.CreateApplicationBuilder(Array.Empty<string>());
        if (useWindowsService)
        {
            builder.Services.AddWindowsService(options => options.ServiceName = WindowsServiceManager.ServiceName);
        }

        builder.Services.AddHostedService(_ => new AgentWorker(
            Path.GetFullPath(configPath),
            _.GetRequiredService<Microsoft.Extensions.Logging.ILogger<AgentWorker>>()));
        using var host = builder.Build();
        if (!useWindowsService)
        {
            Console.WriteLine("Foreground agent started; press Ctrl+C to stop.");
        }

        await host.RunAsync();
        return 0;
    }

    private static string DefaultConfigPath() =>
        Path.Combine(AppContext.BaseDirectory, "agent.json");

    private static void PrintUsage()
    {
        Console.WriteLine("TrueNasControllerAgent");
        Console.WriteLine("  report [--output PATH] [--identity-path PATH] [--text]");
        Console.WriteLine("  install --controller-url URL [--report PATH] [--allow-insecure-http]");
        Console.WriteLine("          [--command-verify-key KEY] [--install-dir PATH]");
        Console.WriteLine("  foreground --config PATH");
        Console.WriteLine("  start | stop | remove");
    }
}
