import { describe, expect, it } from "vitest";
import {
  isStationSelectableForPublish,
  parseStationSetupReport,
  type Station,
} from "./station";

const station = (overrides: Partial<Station>): Station => ({
  id: "station-row",
  station_id: "station-01",
  display_name: "Client 01",
  hostname: "CLIENT-01",
  role: "client",
  status: "online",
  enabled: true,
  deleted_at: null,
  ...overrides,
});

describe("isStationSelectableForPublish", () => {
  it("allows only online client stations", () => {
    expect(isStationSelectableForPublish(station({}))).toBe(true);
    expect(isStationSelectableForPublish(station({ status: "stale" }))).toBe(false);
    expect(isStationSelectableForPublish(station({ role: "admin" }))).toBe(false);
    expect(isStationSelectableForPublish(station({ status: "offline" }))).toBe(false);
  });
});

describe("parseStationSetupReport", () => {
  it("parses the client report used to prefill station creation", () => {
    const report = parseStationSetupReport(JSON.stringify({
      report_version: "1",
      station: { station_id: "station-01", display_name: "CLIENT-01", hostname: "CLIENT-01", role: "client" },
      agent: { agent_uuid: "agent-01", agent_version: "0.1.0", hostname: "CLIENT-01" },
      network: { ip_addresses: ["192.0.2.10"], mac_addresses: ["AA:BB:CC:DD:EE:FF"] },
      drives: [{ letter: "D:", present: true, free_bytes: 100 }],
    }));

    expect(report.station.hostname).toBe("CLIENT-01");
    expect(report.station.station_id).toBe("station-01");
    expect(report.agent.agent_uuid).toBe("agent-01");
  });

  it("rejects a malformed or non-client report", () => {
    expect(() => parseStationSetupReport("not-json")).toThrow("валидным JSON");
    expect(() => parseStationSetupReport(JSON.stringify({ report_version: "1" })))
      .toThrow("неверную структуру");
  });
});
