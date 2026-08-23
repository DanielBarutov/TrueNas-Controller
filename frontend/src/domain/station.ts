export type StationRole = "admin" | "client";
export type StationStatus = "online" | "stale" | "offline" | "disabled";

export interface Station {
  id: string;
  station_id: string;
  display_name: string;
  hostname: string;
  role: StationRole;
  status: StationStatus;
  enabled: boolean;
  deleted_at: string | null;
}

export const statusLabel: Record<StationStatus, string> = {
  online: "Online",
  stale: "Stale",
  offline: "Offline",
  disabled: "Disabled",
};

export const statusDescription: Record<StationStatus, string> = {
  online: "Свежий heartbeat получен; станция может участвовать в read-only проверках.",
  stale: "Heartbeat устарел; состояние Windows нельзя считать актуальным.",
  offline: "Агент не отвечает; выбор станции для publish заблокирован.",
  disabled: "Станция отключена оператором и не должна использоваться.",
};
