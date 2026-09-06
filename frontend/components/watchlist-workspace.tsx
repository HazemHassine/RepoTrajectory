"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { productApi, type Changes } from "@/lib/product-api";
import { parseWatchlist, WATCH_KEY, type WatchEntry } from "@/lib/watchlist";
import { ChangeList } from "./project-brief";
import { WatchButton } from "./watch-button";

export function WatchlistWorkspace() {
  const [entries, setEntries] = useState<WatchEntry[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const refresh = useCallback(() => {
    try { setEntries(parseWatchlist(localStorage.getItem(WATCH_KEY))); setError(""); }
    catch { setError("Could not read local watchlist. Existing browser data has been preserved."); }
    setReady(true);
  }, []);
  useEffect(() => {
    refresh();
    window.addEventListener("storage", refresh);
    window.addEventListener("watchlist-change", refresh);
    return () => {
      window.removeEventListener("storage", refresh);
      window.removeEventListener("watchlist-change", refresh);
    };
  }, [refresh]);
  if (!ready) return <p role="status">Loading your watchlist…</p>;
  return <div className="space-y-5">
    {error && <p role="alert">{error}</p>}
    {!entries.length && !error && <div className="panel p-8">
      <h2 className="text-xl">Your watchlist is empty</h2>
      <p className="my-4 text-[#9a9a9a]">Save projects to find them here.</p>
      <Link className="button-primary" href="/topics">Explore topics</Link>
    </div>}
    {entries.map(entry => <article className="panel space-y-4 p-5" key={entry.githubId}>
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div><Link className="text-xl font-semibold text-[#ccf200]" href={`/repositories/${entry.fullName}`}>{entry.fullName}</Link>
          <p className="text-xs text-[#9a9a9a]">Watching since {new Date(entry.watchedAt).toLocaleDateString("en-GB")}</p></div>
        <button className="button-secondary" onClick={() => {
          try {
            const current = parseWatchlist(localStorage.getItem(WATCH_KEY));
            localStorage.setItem(WATCH_KEY, JSON.stringify(current.filter(e => e.githubId !== entry.githubId)));
            refresh();
          } catch { setError("Could not remove watch entry."); }
        }}>Remove watch</button>
      </div>
      <p><span className="text-[#9a9a9a]">Notes: </span>{entry.reason}</p>
      {entry.blocker && <p><span className="text-[#9a9a9a]">Blocker: </span>{entry.blocker}</p>}
      {!!entry.tags.length && <p className="text-xs text-[#9a9a9a]">{entry.tags.join(" · ")}</p>}
      <WatchButton githubId={entry.githubId} fullName={entry.fullName} />
      <WatchChanges entry={entry} />
    </article>)}
  </div>;
}

function WatchChanges({ entry }: { entry: WatchEntry }) {
  const [data, setData] = useState<Changes | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setError(""); setData(null);
    productApi.changes(entry.githubId, entry.watchedAt).then(result => {
      if (active) setData(result);
    }).catch(() => { if (active) setError("Changes unavailable; the source or catalog may be offline."); });
    return () => { active = false; };
  }, [entry.githubId, entry.watchedAt, attempt]);
  return <section className="space-y-3 border-t border-[#222] pt-4">
    <h3 className="font-semibold">Since you saved it</h3>
    {error ? <p role="alert">{error} <button className="text-[#ccf200]" onClick={() => setAttempt(attempt + 1)}>Retry</button></p>
      : data ? <>
        <ChangeList items={data.items} />
        {(data.truncated || Date.parse(entry.watchedAt) < Date.parse(data.retention_start)) && <p className="text-xs text-amber-300">This is a bounded change history; older or additional events may be omitted.</p>}
      </> : <p role="status">Loading recorded changes…</p>}
    <p className="text-xs text-[#9a9a9a]">Updates depend on collection coverage; blockers aren’t checked automatically.</p>
  </section>;
}
