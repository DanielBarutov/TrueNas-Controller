export type DatasetStatus = "current" | "retired" | "deleted" | "cleanup_failed";

export interface Dataset {
  id: string;
  job_id: string;
  station_id: string;
  source_dataset: string;
  dataset_name: string;
  snapshot_ref: string;
  mapping_ref: string;
  status: DatasetStatus;
  is_current: boolean;
  created_at: string;
  deleted_at: string | null;
  last_error: string | null;
}

export const datasetStatusLabel: Record<DatasetStatus, string> = {
  current: "Используется",
  retired: "Готов к удалению",
  deleted: "Удалён",
  cleanup_failed: "Ошибка удаления",
};
