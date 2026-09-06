"use client";
import { useEffect, useState } from "react";
import { parseWatchlist, upsertWatch, WATCH_KEY } from "@/lib/watchlist";

export function WatchButton({ githubId, fullName }: { githubId: number; fullName: string }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [blocker, setBlocker] = useState("");
  const [tags, setTags] = useState("");
  const [status, setStatus] = useState("");
  useEffect(() => {
    try {
      const old = parseWatchlist(localStorage.getItem(WATCH_KEY)).find(e => e.githubId === githubId);
      if (old) { setReason(old.reason); setBlocker(old.blocker); setTags(old.tags.join(", ")); setStatus("Watching"); }
    } catch { setStatus("Local storage unavailable or unreadable"); }
  }, [githubId]);
  return <div className="space-y-3">
    <button className="button-primary" onClick={() => setOpen(!open)}>{status === "Watching" ? "Edit watch" : "Watch"}</button>
    {open && <form className="panel space-y-3 p-4" onSubmit={e => {
      e.preventDefault();
      try {
        const entries = parseWatchlist(localStorage.getItem(WATCH_KEY));
        const next = upsertWatch(entries, { githubId, fullName, reason, blocker,
          tags: tags.split(",").map(t => t.trim()).filter(Boolean), watchedAt: new Date().toISOString() });
        localStorage.setItem(WATCH_KEY, JSON.stringify(next));
        window.dispatchEvent(new Event("watchlist-change"));
        setStatus("Watching"); setOpen(false);
      } catch (error) { setStatus(error instanceof Error ? error.message : "Could not save watchlist."); }
    }}>
      <label className="block text-sm">Notes
        <textarea className="input mt-1 w-full bg-[#111]" required maxLength={2000} value={reason} onChange={e => setReason(e.target.value)} />
      </label>
      <label className="block text-sm">Blocker (optional)
        <input className="input mt-1 w-full bg-[#111]" maxLength={1000} value={blocker} onChange={e => setBlocker(e.target.value)} />
      </label>
      <label className="block text-sm">Tags, separated by commas
        <input className="input mt-1 w-full bg-[#111]" maxLength={300} value={tags} onChange={e => setTags(e.target.value)} />
      </label>
      <p className="text-xs text-[#9a9a9a]">Saved only in this browser.</p>
      <button className="button-primary" type="submit">Save</button>
    </form>}
    {status && <p role="status" className="text-xs text-[#9a9a9a]">{status}</p>}
  </div>;
}
