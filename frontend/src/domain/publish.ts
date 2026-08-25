export type CheckStatus = "pass" | "block" | "unknown" | "warning";

export interface PreflightCheck {
  status: CheckStatus;
  code: string;
  message: string;
  observed_at: string;
  source_snapshot_id: string | null;
}

export interface PreflightReport {
  station_id: string;
  status: CheckStatus;
  can_publish: boolean;
  evaluated_at: string;
  checks: PreflightCheck[];
}

export type PublishJobStatus =
  | "draft"
  | "preflight"
  | "awaiting_confirmation"
  | "publishing"
  | "switching"
  | "verifying"
  | "completed"
  | "partial_failure"
  | "failed";

export interface PublishJobDraft {
  id: string;
  idempotency_key: string;
  correlation_id: string;
  label: string;
  source_dataset: string;
  status: PublishJobStatus;
  dry_run: boolean;
  allow_hot_switch: boolean;
  station_ids: string[];
}

export interface PublishGate {
  status: "ready" | "blocked";
  can_advance: boolean;
  selected_station_ids: string[];
  reasons: string[];
}

export interface PublishPrepareResponse {
  job_id: string;
  status: PublishJobStatus;
  client_confirmation: boolean | null;
  gate: PublishGate;
  admin_report: PreflightReport | null;
  client_reports: PreflightReport[];
}

export interface PublishDispatchResponse {
  job_id: string;
  status: PublishJobStatus;
  accepted: boolean;
}

export interface PublishTargetReadModel {
  station_id: string;
  selected: boolean;
  preflight_status: string | null;
  switch_status: string | null;
  verify_status: string | null;
  error_code: string | null;
  error_message: string | null;
  progress_percent: number;
}

export interface PublishJobReadModel {
  id: string;
  idempotency_key: string;
  correlation_id: string;
  label: string;
  source_dataset: string;
  description: string | null;
  status: PublishJobStatus;
  dry_run: boolean;
  allow_hot_switch: boolean;
  targets: PublishTargetReadModel[];
}

export const checkStatusLabel: Record<CheckStatus, string> = {
  pass: "PASS",
  block: "BLOCK",
  unknown: "UNKNOWN",
  warning: "WARNING",
};

export const checkStatusDescription: Record<CheckStatus, string> = {
  pass: "Проверка пройдена.",
  block: "Проверка блокирует публикацию.",
  unknown: "Нельзя подтвердить безопасность по текущим данным.",
  warning: "Есть предупреждение; решение остаётся за серверной политикой.",
};

export const publishStatusLabel: Record<PublishJobStatus, string> = {
  draft: "Черновик",
  preflight: "Preflight",
  awaiting_confirmation: "Ожидает подтверждения",
  publishing: "Принято в публикацию",
  switching: "Переключение",
  verifying: "Проверка",
  completed: "Завершено",
  partial_failure: "Частичный сбой",
  failed: "Ошибка",
};
