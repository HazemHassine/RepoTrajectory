"use client";

import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ScoreBar, StatusBadge } from "@/components/ui";
import type { RepositoryRecord } from "@/lib/api";
import { assessment, compact, getNumber, relativeDate } from "@/lib/format";

type Sort = "name" | "stars" | "momentum" | "health" | "risk";

export function RepositoryDirectory({ records }: { records: RepositoryRecord[] }) {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState("All languages");
  const [sort, setSort] = useState<Sort>("stars");
  const languages = useMemo(() => ["All languages", ...Array.from(new Set(records.map((record) => record.primary_language).filter(Boolean) as string[])).sort()], [records]);
  const filtered = useMemo(() => records
    .filter((record) => (!query || `${record.full_name} ${record.description}`.toLowerCase().includes(query.toLowerCase())) && (language === "All languages" || record.primary_language === language))
    .sort((a, b) => {
      if (sort === "name") return a.full_name.localeCompare(b.full_name);
      if (sort === "stars") return b.stars - a.stars;
      if (sort === "momentum") return (b.metric?.momentum_score ?? -1) - (a.metric?.momentum_score ?? -1);
      if (sort === "health") return (b.metric?.health_score ?? -1) - (a.metric?.health_score ?? -1);
      return (b.metric?.bus_factor_risk ?? -1) - (a.metric?.bus_factor_risk ?? -1);
    }), [records, query, language, sort]);

  return <div className="panel overflow-hidden">
    <div className="grid gap-px border-b border-[#343a34] bg-[#343a34] md:grid-cols-[1fr_220px_220px]">
      <label className="flex h-12 items-center gap-3 bg-[#101310] px-4 focus-within:bg-[#171b17]"><MagnifyingGlassIcon className="size-4 text-[#c7ff00]" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="SEARCH NAME OR DESCRIPTION /" className="min-w-0 flex-1 bg-transparent font-mono text-[10px] uppercase tracking-[.08em] outline-none placeholder:text-[#70776f]" /></label>
      <select value={language} onChange={(event) => setLanguage(event.target.value)} className="h-12 border-0 bg-[#101310] px-4 font-mono text-[10px] font-bold uppercase outline-none focus:bg-[#171b17]"><option>{languages[0]}</option>{languages.slice(1).map((value) => <option key={value}>{value}</option>)}</select>
      <select value={sort} onChange={(event) => setSort(event.target.value as Sort)} className="h-12 border-0 bg-[#101310] px-4 font-mono text-[10px] font-bold uppercase outline-none focus:bg-[#171b17]"><option value="stars">Sort / Stars</option><option value="momentum">Sort / Momentum</option><option value="health">Sort / Health</option><option value="risk">Sort / Concentration</option><option value="name">Sort / Name</option></select>
    </div>
    <div className="flex items-center justify-between border-b border-[#343a34] px-5 py-2 font-mono text-[9px] uppercase tracking-[.1em] text-[#70776f]"><span>{filtered.length} records visible</span><span>Index / live</span></div>
    <div className="overflow-x-auto"><table className="w-full min-w-[980px]">
      <thead><tr className="border-b border-[#343a34] bg-[#101310]"><th className="table-head px-5 py-3">Repository</th><th className="table-head px-4 py-3">Assessment</th><th className="table-head px-4 py-3">Scale</th><th className="table-head px-4 py-3">Momentum</th><th className="table-head px-4 py-3">Health</th><th className="table-head px-4 py-3">Human commits</th><th className="table-head px-4 py-3">Automation</th><th className="table-head px-4 py-3">Last sync</th></tr></thead>
      <tbody><AnimatePresence initial={false}>
        {filtered.map((record, index) => {
          const state = assessment(record.metric);
          return <motion.tr layout key={record.full_name} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ delay: Math.min(index * .018, .32) }} className="group border-b border-[#343a34] last:border-0 hover:bg-[#171b17]">
            <td className="max-w-[320px] px-5 py-4"><div className="flex items-start gap-3"><span className="font-mono text-[9px] text-[#70776f]">{String(index + 1).padStart(3, "0")}</span><div className="min-w-0"><Link href={`/repositories/${record.owner}/${record.name}`} className="font-mono text-[13px] font-bold group-hover:text-[#c7ff00]">{record.full_name}</Link><p className="mt-1 truncate text-xs text-[#9ba399]">{record.description || "No description provided"}</p></div></div></td>
            <td className="px-4"><StatusBadge status={state.status} tone={state.tone} /></td>
            <td className="px-4"><b className="font-mono text-xs">{compact(record.stars)}</b><span className="block font-mono text-[9px] uppercase text-[#70776f]">stars</span></td>
            <td className="px-4"><ScoreBar compact value={record.metric?.momentum_score} /></td>
            <td className="px-4"><ScoreBar compact value={record.metric?.health_score} /></td>
            <td className="px-4 font-mono text-xs">{compact(getNumber(record.metric, "velocity", "commits"))}</td>
            <td className="px-4 font-mono text-xs">{getNumber(record.metric, "velocity", "automation_share") == null ? "—" : `${Math.round(getNumber(record.metric, "velocity", "automation_share")! * 100)}%`}</td>
            <td className="px-4 font-mono text-[10px] text-[#9ba399]">{relativeDate(record.last_ingested_at)}</td>
          </motion.tr>;
        })}
      </AnimatePresence></tbody>
    </table>{filtered.length === 0 && <div className="p-10 text-center font-mono text-[10px] uppercase text-[#9ba399]">No repositories match these filters.</div>}</div>
  </div>;
}
