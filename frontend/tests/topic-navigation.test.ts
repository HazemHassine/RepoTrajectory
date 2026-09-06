import assert from "node:assert/strict";
import test from "node:test";
// @ts-ignore Node executes source directly.
import { normalizeTopicQuery, topicHref } from "../lib/topic-navigation.ts";

test("topic pagination preserves search, language and sort with safe encoding", () => {
  const href = topicHref("data", { q: "C++ & SQL", language: "C++", sort: "stars", cursor: "a+/=" });
  const url = new URL(href, "https://example.test");
  assert.equal(url.searchParams.get("q"), "C++ & SQL");
  assert.equal(url.searchParams.get("language"), "C++");
  assert.equal(url.searchParams.get("cursor"), "a+/=");
  assert.equal(url.searchParams.get("sort"), "stars");
});

test("first page clears cursor without losing the selected filters", () => {
  const filters = normalizeTopicQuery({ q: "  database  ", sort: "updated", cursor: "next" });
  assert.equal(topicHref("data", { ...filters, cursor: undefined }), "/topics/data?q=database&sort=updated");
});

test("invalid sort and repeated query values do not reach the topic API", () => {
  assert.deepEqual(normalizeTopicQuery({ q: ["a", "b"], language: ["Python"], sort: "invalid" }), {
    q: undefined, language: undefined, sort: "relevance", cursor: undefined,
  });
});
