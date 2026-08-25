using System.ComponentModel;
using System.Runtime.InteropServices;
using System.ServiceProcess;

namespace TrueNasController.Agent.Infrastructure;

public static class WindowsServiceManager
{
    public const string ServiceName = "TrueNasControllerAgent";
    public const string DisplayName = "TrueNAS Controller Agent";

    private const uint ScManagerConnect = 0x0001;
    private const uint ScManagerCreateService = 0x0002;
    private const uint ServiceAllAccess = 0xF01FF;
    private const uint ServiceChangeConfig = 0x0002;
    private const uint ServiceQueryStatus = 0x0004;
    private const uint ServiceStart = 0x0010;
    private const uint ServiceStop = 0x0020;
    private const uint ServiceWin32OwnProcess = 0x00000010;
    private const uint ServiceAutoStart = 0x00000002;
    private const uint ServiceErrorNormal = 0x00000001;
    private const uint ServiceNoChange = 0xFFFFFFFF;

    public static void Install(string executablePath, string configPath)
    {
        EnsureWindows();
        var commandLine = $"\"{executablePath}\" --service --config \"{configPath}\"";
        var manager = OpenSCManager(null, null, ScManagerConnect | ScManagerCreateService);
        if (manager == IntPtr.Zero)
        {
            ThrowLastError("open Service Control Manager");
        }

        try
        {
            var service = OpenService(manager, ServiceName, ServiceChangeConfig | ServiceQueryStatus | ServiceStart);
            if (service != IntPtr.Zero)
            {
                try
                {
                    if (!ChangeServiceConfig(
                            service,
                            ServiceWin32OwnProcess,
                            ServiceAutoStart,
                            ServiceErrorNormal,
                            commandLine,
                            null,
                            null,
                            null,
                            "LocalSystem",
                            null,
                            DisplayName))
                    {
                        ThrowLastError("update Windows Service");
                    }
                }
                finally
                {
                    CloseServiceHandle(service);
                }

                return;
            }

            service = CreateService(
                manager,
                ServiceName,
                DisplayName,
                ServiceAllAccess,
                ServiceWin32OwnProcess,
                ServiceAutoStart,
                ServiceErrorNormal,
                commandLine,
                null,
                null,
                null,
                null,
                null);
            if (service == IntPtr.Zero)
            {
                ThrowLastError("register Windows Service");
            }

            CloseServiceHandle(service);
        }
        finally
        {
            CloseServiceHandle(manager);
        }
    }

    public static bool Exists()
    {
        if (!OperatingSystem.IsWindows())
        {
            return false;
        }

        try
        {
            using var controller = new ServiceController(ServiceName);
            _ = controller.Status;
            return true;
        }
        catch (InvalidOperationException)
        {
            return false;
        }
    }

    public static void StartAndWait()
    {
        EnsureWindows();
        using var controller = new ServiceController(ServiceName);
        try
        {
            if (controller.Status == ServiceControllerStatus.Stopped)
            {
                controller.Start();
            }

            controller.WaitForStatus(ServiceControllerStatus.Running, TimeSpan.FromSeconds(30));
            if (controller.Status != ServiceControllerStatus.Running)
            {
                throw new InvalidOperationException("Windows Service did not reach Running state");
            }
        }
        catch (Win32Exception exception)
        {
            throw new InvalidOperationException(
                $"could not start Windows Service (Windows error {exception.NativeErrorCode}: {exception.Message})",
                exception);
        }
    }

    public static void Stop()
    {
        EnsureWindows();
        using var controller = new ServiceController(ServiceName);
        try
        {
            if (controller.Status == ServiceControllerStatus.Stopped)
            {
                return;
            }

            controller.Stop();
            controller.WaitForStatus(ServiceControllerStatus.Stopped, TimeSpan.FromSeconds(30));
        }
        catch (InvalidOperationException exception) when (exception.InnerException is Win32Exception)
        {
            throw new InvalidOperationException("could not stop Windows Service", exception);
        }
    }

    public static void TryStop()
    {
        if (Exists())
        {
            Stop();
        }
    }

    public static void Remove()
    {
        EnsureWindows();
        var manager = OpenSCManager(null, null, ScManagerConnect);
        if (manager == IntPtr.Zero)
        {
            ThrowLastError("open Service Control Manager");
        }

        try
        {
            var service = OpenService(manager, ServiceName, ServiceStop | ServiceQueryStatus | 0x10000);
            if (service == IntPtr.Zero)
            {
                return;
            }

            try
            {
                TryStop();
                if (!DeleteService(service))
                {
                    ThrowLastError("remove Windows Service");
                }
            }
            finally
            {
                CloseServiceHandle(service);
            }
        }
        finally
        {
            CloseServiceHandle(manager);
        }
    }

    private static void EnsureWindows()
    {
        if (!OperatingSystem.IsWindows())
        {
            throw new PlatformNotSupportedException("Windows Service commands require Windows");
        }
    }

    private static void ThrowLastError(string operation)
    {
        var error = Marshal.GetLastWin32Error();
        throw new Win32Exception(error, $"could not {operation} (Windows error {error})");
    }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenSCManager(
        string? machineName,
        string? databaseName,
        uint desiredAccess);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr OpenService(
        IntPtr manager,
        string serviceName,
        uint desiredAccess);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr CreateService(
        IntPtr manager,
        string serviceName,
        string displayName,
        uint desiredAccess,
        uint serviceType,
        uint startType,
        uint errorControl,
        string binaryPathName,
        string? loadOrderGroup,
        string? tagId,
        string? dependencies,
        string? serviceStartName,
        string? password);

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ChangeServiceConfig(
        IntPtr service,
        uint serviceType,
        uint startType,
        uint errorControl,
        string? binaryPathName,
        string? loadOrderGroup,
        string? tagId,
        string? dependencies,
        string? serviceStartName,
        string? password,
        string? displayName);

    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool DeleteService(IntPtr service);

    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseServiceHandle(IntPtr handle);
}
