import type { Station, StationRole } from "../../domain/station";
import type {
  PreflightReport,
  PublishDispatchResponse,
  PublishJobReadModel,
  PublishJobDraft,
  PublishHistoryItem,
  PublishPrepareResponse,
} from "../../domain/publish";

export interface Credentials {
  username: string;
  password: string;
}

export type ProcessRuleSeverity = "blocking" | "warning";
export type ProcessRuleRole = StationRole | null;

export interface ProcessRule {
  id: string;
  name: string;
  role: ProcessRuleRole;
  required_closed: boolean;
  severity: ProcessRuleSeverity;
  enabled: boolean;
  persistent_policy: boolean;
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
    target_name?: string;
    target_iqn?: string;
    initiator_iqn?: string;
  }): Promise<Station & { enrollment_token: string; enrollment_expires_at: string }> {
    return this.request("/api/v1/stations", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async createProvisioningToken(): Promise<{ provisioning_token: string; expires_at: string }> {
    return this.request("/api/v1/provisioning-tokens", {
      method: "POST",
      body: JSON.stringify({}),
    });
  }

  async deleteStation(stationId: string): Promise<void> {
    await this.request<void>(`/api/v1/stations/${stationId}`, {
      method: "DELETE",
    });
  }

  async updateStationStorageMapping(
    stationId: string,
    input: { target_name?: string | null; target_iqn?: string | null; initiator_iqn?: string | null },
  ): Promise<Station> {
    return this.request(`/api/v1/stations/${stationId}/storage-mapping`, {
      method: "PATCH",
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
    source_dataset: string;
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
    input: { admin_station_id?: string | null; confirmation: boolean | null },
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

  async listPublishJobs(limit = 50): Promise<PublishHistoryItem[]> {
    return this.request(`/api/v1/publish/jobs?limit=${limit}`);
  }

  async listProcessRules(): Promise<ProcessRule[]> {
    return this.request("/api/v1/process-rules");
  }

  async createProcessRule(input: Omit<ProcessRule, "id">): Promise<ProcessRule> {
    return this.request("/api/v1/process-rules", {
      method: "POST",
      body: JSON.stringify(input),
    });
  }

  async deleteProcessRule(ruleId: string): Promise<void> {
    await this.request<void>(`/api/v1/process-rules/${ruleId}`, { method: "DELETE" });
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
    if (response.status === 204) {
      return undefined as T;
    }
    return (await response.json()) as T;
  }
}
