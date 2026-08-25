using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;

namespace TrueNasController.Agent.Infrastructure;

public sealed class NetworkSnapshotCollector
{
    public (IReadOnlyList<string> IpAddresses, IReadOnlyList<string> MacAddresses) Collect()
    {
        var addresses = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var macAddresses = new HashSet<string>(StringComparer.OrdinalIgnoreCase);

        foreach (var networkInterface in NetworkInterface.GetAllNetworkInterfaces())
        {
            if (networkInterface.OperationalStatus != OperationalStatus.Up ||
                networkInterface.NetworkInterfaceType == NetworkInterfaceType.Loopback)
            {
                continue;
            }

            var mac = networkInterface.GetPhysicalAddress().GetAddressBytes();
            if (mac.Length > 0)
            {
                macAddresses.Add(string.Join(":", mac.Select(value => value.ToString("X2"))));
            }

            try
            {
                foreach (var address in networkInterface.GetIPProperties().UnicastAddresses)
                {
                    if (address.Address.AddressFamily != AddressFamily.InterNetwork ||
                        IPAddress.IsLoopback(address.Address) ||
                        address.Address.ToString().StartsWith("169.254.", StringComparison.Ordinal))
                    {
                        continue;
                    }

                    addresses.Add(address.Address.ToString());
                }
            }
            catch (NetworkInformationException)
            {
                // An interface may disappear while the service is collecting a snapshot.
            }
        }

        return (addresses.Order(StringComparer.Ordinal).ToArray(), macAddresses.Order(StringComparer.Ordinal).ToArray());
    }
}
