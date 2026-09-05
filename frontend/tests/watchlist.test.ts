import assert from "node:assert/strict";
import test from "node:test";
// @ts-ignore Node executes the source directly; no test bundler or browser dependency.
import { coverage, parseWatchlist, safeSourceUrl, upsertWatch } from "../lib/watchlist.ts";

const entry = { githubId: 123, fullName: "org/tool", reason: "Try for RAG", blocker: "Need Windows",
  tags: ["rag"], watchedAt: "2026-01-01T00:00:00Z" };
test("watchlist persists reason, blocker and stable identity", () => {
  assert.deepEqual(parseWatchlist(JSON.stringify(upsertWatch([], entry))), [entry]);
});
test("editing a watch preserves original date and survives rename", () => {
  const edited = upsertWatch([entry], { ...entry, fullName: "new/tool", watchedAt: "2026-02-01T00:00:00Z" });
  assert.equal(edited.length, 1);
  assert.equal(edited[0].watchedAt, entry.watchedAt);
});
test("missing and zero coverage remain distinct", () => {
  assert.equal(coverage(0), "0%");
  assert.equal(coverage(null), "Unknown");
  assert.equal(coverage(undefined), "Unknown");
});
test("invalid stored data cannot create arbitrary repository paths", () => {
  assert.deepEqual(parseWatchlist(JSON.stringify([{ ...entry, fullName: "../private/path" }])), []);
  assert.throws(() => parseWatchlist("{broken"));
});
test("evidence links reject script URLs", () => {
  assert.equal(safeSourceUrl("javascript:alert(1)"), undefined);
  assert.equal(safeSourceUrl("https://osv.dev/"), "https://osv.dev/");
});
