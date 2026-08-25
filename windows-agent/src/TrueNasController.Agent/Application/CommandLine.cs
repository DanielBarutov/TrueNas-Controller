namespace TrueNasController.Agent.Application;

public static class CommandLine
{
    public static string? Value(IReadOnlyList<string> args, string name)
    {
        for (var index = 0; index < args.Count - 1; index++)
        {
            if (string.Equals(args[index], name, StringComparison.OrdinalIgnoreCase))
            {
                return args[index + 1];
            }
        }

        return null;
    }

    public static bool Has(IReadOnlyList<string> args, string name) =>
        args.Any(item => string.Equals(item, name, StringComparison.OrdinalIgnoreCase));
}
