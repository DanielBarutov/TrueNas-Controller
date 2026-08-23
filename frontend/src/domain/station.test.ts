import { describe, expect, it } from "vitest";
import { isStationSelectableForPublish, type Station } from "./station";

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
