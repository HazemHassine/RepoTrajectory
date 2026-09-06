import { getV2, postV2 } from "./api";

export type Fact = {
  label: string; value: string | null; source_url: string | null;
  observed_at: string | null; basis: "direct" | "derived" | "attributed" | "missing";
};
export type Evidence = {
  id: number; source: string; kind: string; title: string; excerpt: string | null;
  author: string | null; url: string; published_at: string | null; observed_at: string;
  details: Record<string, unknown>;
};
export type Change = {
  id: number; kind: string; title: string; evidence_id: number | null;
  source_url: string; occurred_at: string; observed_at: string;
};
export type SourceLink = {
  source: string; external_id: string; canonical_url: string; match_method: string;
  match_confidence: number; verification: string; provenance_url: string; observed_at: string;
};
export type Source = {
  source: string; external_id: string; status: "healthy" | "stale" | "degraded";
  last_success_at: string | null; last_error: string | null; next_refresh_at: string;
  facts: Record<string, unknown>;
};
export type Brief = {
  github_id: number; full_name: string; description: Fact; readme_excerpt: Fact;
  facts: Fact[]; missing: string[]; evidence: Evidence[]; changes: Change[];
  external_sources: { links: SourceLink[]; sources: Source[] };
  evidence_fingerprint: string; synthesis_mode: "deterministic";
};
export type Constraints = {
  context: string; language?: string; license?: string; package_ecosystem?: "npm" | "pypi";
  activity_within_days?: number; deployment?: "self-hosted" | "saas-acceptable";
};
export type Comparison = {
  constraints: Constraints; projects: { brief: Brief; fit: {
    constraint: string; status: "matches" | "differs" | "unknown";
    explanation: string; source_url: string | null;
  }[] }[]; recommendation: string | null; limitation: string; synthesis_mode: "structured";
};
export type Topic = {
  slug: string; name: string; description: string; terms: string[];
  parent_slug?: string | null; repository_count?: number;
};
export type TopicFilters = { q?: string; language?: string; sort?: string; cursor?: string };
export type TopicDetail = {
  topic: Topic; projects: {
    github_id: number; full_name: string; description: string | null;
    primary_language: string | null; matched_terms: string[]; pushed_at: string | null; stars: number;
  }[]; changes: Change[]; limit: number;
  total_count?: number; next_cursor?: string | null;
  languages?: { value: string; count: number }[];
};
export type Changes = { items: Change[]; retention_start: string; truncated: boolean };
export const productApi = {
  brief: (owner: string, name: string) => getV2<Brief>(`/repositories/${encodeURIComponent(owner)}/${encodeURIComponent(name)}/brief`),
  changes: (id: number, since: string) => getV2<Changes>(`/repositories/by-id/${id}/changes?since=${encodeURIComponent(since)}`),
  compare: (ids: number[], constraints: Constraints) => postV2<Comparison>("/compare/context", { github_ids: ids, constraints }),
  topics: () => getV2<Topic[]>("/topics"),
  topic: (slug: string, filters: TopicFilters = {}) => {
    const query = new URLSearchParams({ limit: "30" });
    for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
    return getV2<TopicDetail>(`/topics/${encodeURIComponent(slug)}?${query}`);
  },
};
