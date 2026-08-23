import { describe, expect, it } from "vitest";
import { knowledgeDocuments } from "./registry";

describe("knowledge registry", () => {
  it("contains only non-secret operator documents", () => {
    expect(knowledgeDocuments.length).toBeGreaterThanOrEqual(3);
    expect(new Set(knowledgeDocuments.map((document) => document.id)).size)
      .toBe(knowledgeDocuments.length);
    for (const document of knowledgeDocuments) {
      expect(document.title).not.toHaveLength(0);
      expect(document.description).not.toHaveLength(0);
      expect(document.content).not.toMatch(/BASIC_AUTH_PASSWORD\s*=\s*"\d{8,}"/);
      expect(document.content).not.toContain("TrueNAS API key");
    }
  });
});
