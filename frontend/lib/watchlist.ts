export const WATCH_KEY = "repotrajectory.watchlist.v1";
export type WatchEntry = {
  githubId: number; fullName: string; reason: string; blocker: string; tags: string[];
  watchedAt: string;
};

export function parseWatchlist(raw: string | null): WatchEntry[] {
  if (!raw) return [];
  const data: unknown = JSON.parse(raw);
  if (!Array.isArray(data)) throw new Error("Watchlist data is invalid.");
  return data.filter((entry): entry is WatchEntry => {
    if (!entry || typeof entry !== "object") return false;
    const e = entry as Partial<WatchEntry>;
    return Number.isSafeInteger(e.githubId) && Number(e.githubId) > 0
      && typeof e.fullName === "string" && /^[\w.-]+\/[\w.-]+$/.test(e.fullName)
      && typeof e.reason === "string" && typeof e.blocker === "string"
      && Array.isArray(e.tags) && e.tags.every(t => typeof t === "string")
      && typeof e.watchedAt === "string" && Number.isFinite(Date.parse(e.watchedAt));
  }).slice(0, 100);
}

export function upsertWatch(entries: WatchEntry[], entry: WatchEntry): WatchEntry[] {
  const old = entries.find(e => e.githubId === entry.githubId);
  if (!old && entries.length >= 100) throw new Error("The local beta watchlist is limited to 100 projects.");
  const saved = { ...entry, reason: entry.reason.slice(0, 2000), blocker: entry.blocker.slice(0, 1000),
    tags: entry.tags.slice(0, 10), watchedAt: old?.watchedAt ?? entry.watchedAt };
  return [saved, ...entries.filter(e => e.githubId !== entry.githubId)];
}

export function coverage(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? "Unknown" : `${Math.round(value * 100)}%`;
}

export function safeSourceUrl(value: string | null): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch { return undefined; }
}
