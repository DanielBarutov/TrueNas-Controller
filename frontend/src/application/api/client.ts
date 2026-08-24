import type { Station, StationRole } from "../../domain/station";
import type {
  PreflightReport,
  PublishDispatchResponse,
  PublishJobReadModel,
  PublishJobDraft,
  PublishPrepareResponse,
} from "../../domain/publish";

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
    station_id?: string;
    display_name: string;
    hostname: string;
    role: StationRole;
  }): Promise<Station & { enrollment_token: string; enrollment_expires_at: string }> {
    return this.request("/api/v1/stations", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async preflight(input: {
    station_id: string;
    max_snapshot_age_seconds?: number;
    required_drive_letter?: string;
    min_free_bytes?: number;
  }): Promise<PreflightReport> {
    return this.request("/api/v1/preflight", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async createPublishJob(input: {
    label: string;
    game_name: string;
    description?: string;
    station_ids: string[];
    idempotency_key: string;
    dry_run: boolean;
    allow_hot_switch: boolean;
  }): Promise<PublishJobDraft> {
    return this.request("/api/v1/publish/jobs", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async preparePublishJob(
    jobId: string,
    input: { admin_station_id: string; confirmation: boolean | null },
  ): Promise<PublishPrepareResponse> {
    return this.request(`/api/v1/publish/jobs/${jobId}/prepare`, {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async dispatchPublishJob(jobId: string): Promise<PublishDispatchResponse> {
    return this.request(`/api/v1/publish/jobs/${jobId}/dispatch`, {
      method: "POST",
    });
  }

  async getPublishJob(jobId: string): Promise<PublishJobReadModel> {
    return this.request(`/api/v1/publish/jobs/${jobId}`);
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
