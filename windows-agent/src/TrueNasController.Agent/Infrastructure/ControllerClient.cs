using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using TrueNasController.Agent.Domain;

namespace TrueNasController.Agent.Infrastructure;

public sealed class ControllerClient : IDisposable
{
    private readonly HttpClient _httpClient;
    private readonly AgentConfig _config;

    public ControllerClient(AgentConfig config)
    {
        ValidateUrl(config.ControllerUrl, config.AllowInsecureHttp);
        _config = config;
        _httpClient = new HttpClient(new HttpClientHandler { UseProxy = false })
        {
            Timeout = TimeSpan.FromSeconds(15),
        };
    }

    public async Task<EnrollmentResponse> EnrollAsync(
        string enrollmentToken,
        IReadOnlyList<string> ipAddresses,
        IReadOnlyList<string> macAddresses,
        CancellationToken cancellationToken)
    {
        var request = new
        {
            enrollment_token = enrollmentToken,
            agent_uuid = _config.AgentUuid,
            hostname = _config.Hostname,
            agent_version = _config.AgentVersion,
            ip_addresses = ipAddresses,
            mac_addresses = macAddresses,
        };
        using var response = await PostJsonAsync(
            _config.EnrollmentUrl,
            request,
            bearer: null,
            cancellationToken);
        if (response.StatusCode == HttpStatusCode.Conflict)
        {
            throw new InvalidOperationException(
                "enrollment rejected: token is invalid, expired, or already used; create a new station");
        }

        await EnsureSuccessAsync(response, "enrollment");
        var result = await DeserializeAsync<EnrollmentResponse>(response, "enrollment response");
        if (string.IsNullOrWhiteSpace(result.Credential))
        {
            throw new InvalidOperationException("enrollment response contains an empty credential");
        }

        return result;
    }

    public async Task<EnrollmentResponse> BootstrapAsync(
        string provisioningToken,
        string displayName,
        IReadOnlyList<string> ipAddresses,
        IReadOnlyList<string> macAddresses,
        CancellationToken cancellationToken)
    {
        var request = new
        {
            provisioning_token = provisioningToken,
            station_id = _config.StationId,
            display_name = displayName,
            hostname = _config.Hostname,
            role = "client",
            agent_uuid = _config.AgentUuid,
            agent_version = _config.AgentVersion,
            ip_addresses = ipAddresses,
            mac_addresses = macAddresses,
        };
        using var response = await PostJsonAsync(
            $"{_config.ControllerUrl.TrimEnd('/')}/api/v1/agents/bootstrap",
            request,
            bearer: null,
            cancellationToken);
        if (response.StatusCode == HttpStatusCode.Conflict)
        {
            throw new InvalidOperationException(
                "automatic station bootstrap rejected: provisioning token is invalid, expired, already used, or the station already has an agent");
        }

        await EnsureSuccessAsync(response, "station bootstrap");
        var result = await DeserializeAsync<EnrollmentResponse>(response, "station bootstrap response");
        if (string.IsNullOrWhiteSpace(result.Credential))
        {
            throw new InvalidOperationException("station bootstrap response contains an empty credential");
        }

        return result;
    }

    public async Task<HeartbeatResponse> SendHeartbeatAsync(
        HeartbeatPayload payload,
        string credential,
        CancellationToken cancellationToken)
    {
        using var response = await PostJsonAsync(
            _config.HeartbeatUrl,
            payload,
            credential,
            cancellationToken);
        await EnsureSuccessAsync(response, "heartbeat");
        return await DeserializeAsync<HeartbeatResponse>(response, "heartbeat response");
    }

    public async Task AcknowledgeAsync(
        Guid commandId,
        string credential,
        CancellationToken cancellationToken)
    {
        using var response = await PostJsonAsync(
            $"{_config.ControllerUrl.TrimEnd('/')}/api/v1/agents/commands/{commandId:D}/ack",
            new { },
            credential,
            cancellationToken);
        await EnsureSuccessAsync(response, "command acknowledgement");
    }

    private async Task<HttpResponseMessage> PostJsonAsync(
        string url,
        object body,
        string? bearer,
        CancellationToken cancellationToken)
    {
        using var request = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(
                JsonSerializer.Serialize(body, JsonDefaults.Options),
                Encoding.UTF8,
                "application/json"),
        };
        if (!string.IsNullOrWhiteSpace(bearer))
        {
            request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", bearer);
        }

        try
        {
            return await _httpClient.SendAsync(request, cancellationToken);
        }
        catch (HttpRequestException exception)
        {
            throw new InvalidOperationException(
                "controller request failed; check Controller URL, port and firewall",
                exception);
        }
        catch (TaskCanceledException exception) when (!cancellationToken.IsCancellationRequested)
        {
            throw new InvalidOperationException("controller request timed out", exception);
        }
    }

    private static async Task EnsureSuccessAsync(HttpResponseMessage response, string operation)
    {
        if ((int)response.StatusCode is >= 200 and < 300)
        {
            return;
        }

        var detail = await response.Content.ReadAsStringAsync();
        if (detail.Length > 300)
        {
            detail = detail[..300];
        }

        if (response.StatusCode is HttpStatusCode.Unauthorized or HttpStatusCode.Forbidden)
        {
            throw new ControllerUnauthorizedException(
                $"{operation} rejected with HTTP {(int)response.StatusCode}: {detail}");
        }

        throw new InvalidOperationException(
            $"{operation} rejected with HTTP {(int)response.StatusCode}: {detail}");
    }

    private static async Task<T> DeserializeAsync<T>(HttpResponseMessage response, string operation)
    {
        try
        {
            var result = await response.Content.ReadFromJsonAsync<T>(JsonDefaults.Options);
            return result ?? throw new InvalidOperationException($"{operation} is empty");
        }
        catch (JsonException exception)
        {
            throw new InvalidOperationException($"{operation} is malformed", exception);
        }
    }

    private static void ValidateUrl(string value, bool allowInsecureHttp)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) ||
            string.IsNullOrWhiteSpace(uri.Host) ||
            (uri.Scheme != Uri.UriSchemeHttps &&
             !(allowInsecureHttp && uri.Scheme == Uri.UriSchemeHttp)))
        {
            throw new ArgumentException(
                "Controller URL must be a full HTTPS URL, or HTTP with --allow-insecure-http");
        }
    }

    public void Dispose() => _httpClient.Dispose();
}

public sealed class ControllerUnauthorizedException : InvalidOperationException
{
    public ControllerUnauthorizedException(string message)
        : base(message)
    {
    }
}
