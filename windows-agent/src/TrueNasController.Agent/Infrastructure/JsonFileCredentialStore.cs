using System.Security.Cryptography;
using System.Security.AccessControl;
using System.Security.Principal;
using System.Text;

namespace TrueNasController.Agent.Infrastructure;

public sealed class JsonFileCredentialStore
{
    private readonly string _path;

    public JsonFileCredentialStore(string path)
    {
        _path = path;
    }

    public bool Exists => File.Exists(_path);

    public string Load(out bool legacyUserScope)
    {
        var encrypted = File.ReadAllBytes(_path);
        try
        {
            legacyUserScope = false;
            return Decode(ProtectedData.Unprotect(encrypted, null, DataProtectionScope.LocalMachine));
        }
        catch (CryptographicException)
        {
            legacyUserScope = true;
            return Decode(ProtectedData.Unprotect(encrypted, null, DataProtectionScope.CurrentUser));
        }
    }

    public string Load()
    {
        return Load(out _);
    }

    public void Save(string credential)
    {
        if (string.IsNullOrWhiteSpace(credential) || credential.Contains('\n') || credential.Contains('\r'))
        {
            throw new InvalidOperationException("agent credential must be a non-empty single-line value");
        }

        var directory = Path.GetDirectoryName(_path);
        if (!string.IsNullOrWhiteSpace(directory))
        {
            Directory.CreateDirectory(directory);
        }

        var encrypted = ProtectedData.Protect(
            Encoding.UTF8.GetBytes(credential),
            null,
            DataProtectionScope.LocalMachine);
        var temporaryPath = $"{_path}.{Guid.NewGuid():N}.tmp";
        File.WriteAllBytes(temporaryPath, encrypted);
        WindowsFileSecurity.Secure(temporaryPath);
        File.Move(temporaryPath, _path, overwrite: true);
        WindowsFileSecurity.Secure(_path);
    }

    public void Preflight()
    {
        var probePath = $"{_path}.{Guid.NewGuid():N}.check";
        var probe = new JsonFileCredentialStore(probePath);
        try
        {
            probe.Save("credential-store-preflight");
            if (probe.Load() != "credential-store-preflight")
            {
                throw new InvalidOperationException("credential store preflight did not round-trip");
            }
        }
        finally
        {
            File.Delete(probePath);
        }
    }

    public void Clear()
    {
        if (File.Exists(_path))
        {
            File.Delete(_path);
        }
    }

    private static string Decode(byte[] value)
    {
        var credential = Encoding.UTF8.GetString(value);
        if (string.IsNullOrWhiteSpace(credential))
        {
            throw new InvalidOperationException("stored agent credential is empty");
        }

        return credential;
    }
}

public static class WindowsFileSecurity
{
    public static void Secure(string path)
    {
        var security = new FileSecurity();
        security.SetAccessRuleProtection(isProtected: true, preserveInheritance: false);
        AddRule(security, WellKnownSidType.LocalSystemSid);
        AddRule(security, WellKnownSidType.BuiltinAdministratorsSid);
        new FileInfo(path).SetAccessControl(security);
    }

    private static void AddRule(FileSecurity security, WellKnownSidType sidType)
    {
        var sid = new SecurityIdentifier(sidType, null);
        var rights = FileSystemRights.Read | FileSystemRights.Write | FileSystemRights.Delete;
        security.AddAccessRule(new FileSystemAccessRule(
            sid,
            rights,
            AccessControlType.Allow));
    }
}
