import type { Station, StationRole } from "../../domain/station";

export interface Credentials {
  username: string;
  password: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class ControllerApi {
  constructor(private readonly credentials: Credentials) {}

  async health(): Promise<{ status: string }> {
    return this.request<{ status: string }>("/health");
  }

  async listStations(): Promise<Station[]> {
    return this.request<Station[]>("/api/v1/stations");
  }

  async createStation(input: {
    display_name: string;
    hostname: string;
    role: StationRole;
  }): Promise<Station & { enrollment_token: string; enrollment_expires_at: string }> {
    return this.request("/api/v1/stations", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const authorization = btoa(`${this.credentials.username}:${this.credentials.password}`);
    const response = await fetch(path, {
      ...init,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: `Basic ${authorization}`,
        ...init.headers,
      },
    });
    if (!response.ok) {
      let detail = `Request failed with status ${response.status}`;
      try {
        const body = (await response.json()) as { detail?: string };
        detail = body.detail ?? detail;
      } catch {
        // Keep the safe status-only message when the response is not JSON.
      }
      throw new ApiError(detail, response.status);
    }
    return (await response.json()) as T;
  }
}
