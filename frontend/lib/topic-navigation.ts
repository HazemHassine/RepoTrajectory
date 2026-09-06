export type TopicQuery = { q?: string; language?: string; sort?: string; cursor?: string };

export function topicHref(slug: string, filters: TopicQuery = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) if (value) query.set(key, value);
  return `/topics/${encodeURIComponent(slug)}${query.size ? `?${query}` : ""}`;
}

export function normalizeTopicQuery(params: Record<string, string | string[] | undefined>): TopicQuery {
  const single = (key: string) => typeof params[key] === "string" ? params[key] as string : undefined;
  const sort = single("sort");
  return {
    q: single("q")?.trim() || undefined,
    language: single("language") || undefined,
    sort: sort && ["relevance", "stars", "updated"].includes(sort) ? sort : "relevance",
    cursor: single("cursor") || undefined,
  };
}
