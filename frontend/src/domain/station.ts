export type StationRole = "admin" | "client";
export type StationStatus = "online" | "stale" | "offline" | "disabled";
export type StationSortField = "display_name" | "hostname" | "role" | "status";
export type SortDirection = "asc" | "desc";

export interface Station {
  id: string;
  station_id: string;
  display_name: string;
  hostname: string;
  role: StationRole;
  status: StationStatus;
  enabled: boolean;
  deleted_at: string | null;
  target_name?: string | null;
  target_iqn?: string | null;
  initiator_iqn?: string | null;
}

export interface StationSetupReport {
  report_version: "1";
  station: {
    station_id: string;
    display_name: string;
    hostname: string;
    role: StationRole;
  };
  agent: {
    agent_uuid: string;
    agent_version: string;
    hostname: string;
  };
  network: {
    ip_addresses: string[];
    mac_addresses: string[];
  };
  drives: Array<{
    letter: string;
    present: boolean;
    free_bytes: number | null;
  }>;
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

export const stationSortFieldLabel: Record<StationSortField, string> = {
  display_name: "Имя станции",
  hostname: "Hostname",
  role: "Роль",
  status: "Статус",
};

const statusSortOrder: Record<StationStatus, number> = {
  online: 0,
  stale: 1,
  offline: 2,
  disabled: 3,
};

export function sortStations(
  stations: Station[],
  field: StationSortField,
  direction: SortDirection,
): Station[] {
  const collator = new Intl.Collator("ru", { numeric: true, sensitivity: "base" });
  const multiplier = direction === "asc" ? 1 : -1;

  return [...stations].sort((left, right) => {
    const comparison = field === "status"
      ? statusSortOrder[left.status] - statusSortOrder[right.status]
      : collator.compare(left[field], right[field]);
    return comparison * multiplier || collator.compare(left.station_id, right.station_id);
  });
}

export function isStationSelectableForPublish(station: Station): boolean {
  return station.role === "client" && station.status === "online";
}

export function parseStationSetupReport(raw: string): StationSetupReport {
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error("Отчёт клиента должен быть валидным JSON.");
  }

  const report = asRecord(value);
  const station = asRecord(report.station);
  const agent = asRecord(report.agent);
  const network = asRecord(report.network);
  const drives = Array.isArray(report.drives) ? report.drives.map(asRecord) : [];
  const role = requireString(station.role, "station.role");

  if (report.report_version !== "1") {
    throw new Error("Неподдерживаемая версия отчёта клиента.");
  }
  if (role !== "client") {
    throw new Error("Отчёт должен описывать client station.");
  }
  if (drives.length === 0) {
    throw new Error("В отчёте отсутствует информация о диске D:.");
  }

  return {
    report_version: "1",
    station: {
      station_id: requireString(
        station.station_id ?? agent.agent_uuid,
        "station.station_id",
      ),
      display_name: requireString(station.display_name, "station.display_name"),
      hostname: requireString(station.hostname, "station.hostname"),
      role,
    },
    agent: {
      agent_uuid: requireString(agent.agent_uuid, "agent.agent_uuid"),
      agent_version: requireString(agent.agent_version, "agent.agent_version"),
      hostname: requireString(agent.hostname, "agent.hostname"),
    },
    network: {
      ip_addresses: stringArray(network.ip_addresses, "network.ip_addresses"),
      mac_addresses: stringArray(network.mac_addresses, "network.mac_addresses"),
    },
    drives: drives.map((drive, index) => ({
      letter: requireString(drive.letter, `drives[${index}].letter`),
      present: typeof drive.present === "boolean" ? drive.present : false,
      free_bytes: typeof drive.free_bytes === "number" ? drive.free_bytes : null,
    })),
  };
}

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Отчёт клиента имеет неверную структуру.");
  }
  return value as Record<string, unknown>;
}

function requireString(value: unknown, field: string): string {
  if (typeof value !== "string" || value.trim() === "") {
    throw new Error(`В отчёте отсутствует поле ${field}.`);
  }
  return value.trim();
}

function stringArray(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || !value.every((item) => typeof item === "string")) {
    throw new Error(`Поле ${field} должно быть списком строк.`);
  }
  return value.map((item) => item.trim()).filter(Boolean);
}
