"use client";

import { ArrowsRightLeftIcon } from "@heroicons/react/20/solid";
import Link from "next/link";
import { motion } from "motion/react";
import { useMemo, useState } from "react";

import { ChangeBadge, ScoreBar, StatusBadge } from "@/components/ui";
import type { RepositoryRecord } from "@/lib/api";
import { assessment, compact, duration, getNumber } from "@/lib/format";

type Ranking = "momentum" | "health" | "delivery" | "resilience" | "responsiveness";
const tabs: Array<{ key: Ranking; label: string; description: string }> = [
  { key: "momentum", label: "Momentum", description: "Normalized growth and activity acceleration" },
  { key: "health", label: "Community health", description: "Responsiveness, contributors, delivery, and cadence" },
  { key: "delivery", label: "Delivery", description: "Human commits in the selected period" },
  { key: "resilience", label: "Resilience", description: "Lower concentration of human contribution activity" },
  { key: "responsiveness", label: "Merge cycle", description: "Median time to merge resolved pull requests" },
];

export function RankingWorkspace({ records }: { records: RepositoryRecord[] }) {
  const [active, setActive] = useState<Ranking>("momentum");
  const [selected, setSelected] = useState<string[]>([]);
  const ordered = useMemo(() => [...records].sort((a, b) => rankingSortValue(b, active) - rankingSortValue(a, active)), [records, active]);
  const toggle = (name: string) => setSelected((current) => current.includes(name) ? current.filter((item) => item !== name) : current.length < 2 ? [...current, name] : [current[1], name]);
  const compareHref = selected.length === 2 ? `/compare?a=${encodeURIComponent(selected[0])}&b=${encodeURIComponent(selected[1])}` : "#";
  return <div className="space-y-4"><div className="flex flex-wrap items-end justify-between gap-4"><div className="flex max-w-full gap-1 overflow-x-auto rounded-md border border-[#343a34] bg-[#101310] p-1">{tabs.map((tab) => <motion.button whileHover={{ y: -2 }} key={tab.key} onClick={() => setActive(tab.key)} className={`whitespace-nowrap rounded px-3 py-2 text-xs font-semibold ${active === tab.key ? "bg-[#c7ff00] text-[#080a08]" : "text-[#9ba399] hover:bg-[#171b17]"}`}>{tab.label}</motion.button>)}</div><Link aria-disabled={selected.length !== 2} href={compareHref} className={`button-secondary ${selected.length !== 2 ? "pointer-events-none opacity-45" : ""}`}><ArrowsRightLeftIcon className="size-4" />Compare selected ({selected.length}/2)</Link></div><div className="panel overflow-hidden"><div className="flex items-center justify-between border-b border-[#343a34] bg-[#101310] px-5 py-3"><p className="text-xs text-[#9ba399]">{tabs.find((tab) => tab.key === active)?.description}</p><p className="font-mono text-[11px] text-[#70776f]">Cohort n={records.length}</p></div><div className="overflow-x-auto"><table className="w-full min-w-[900px]"><thead><tr className="border-b border-[#343a34]"><th className="w-12 px-5" /><th className="table-head px-2 py-3">Rank</th><th className="table-head px-4 py-3">Repository</th><th className="table-head px-4 py-3">Assessment</th><th className="table-head px-4 py-3">Ranked value</th><th className="table-head px-4 py-3">Period change</th><th className="table-head px-4 py-3">Evidence</th><th className="table-head px-4 py-3">Confidence</th></tr></thead><tbody>{ordered.map((record, index) => {const state=assessment(record.metric);const value=rankingDisplayValue(record,active);return <motion.tr layout transition={{ type: "spring", stiffness: 320, damping: 30 }} key={record.full_name} className="border-b border-[#343a34] last:border-0 hover:bg-[#101310]"><td className="px-5"><input aria-label={`Select ${record.full_name}`} type="checkbox" checked={selected.includes(record.full_name)} onChange={() => toggle(record.full_name)} className="size-4 accent-[#c7ff00]" /></td><td className="px-2 font-mono text-sm font-semibold">{String(index+1).padStart(2,"0")}</td><td className="px-4 py-4"><Link href={`/repositories/${record.owner}/${record.name}`} className="font-mono text-[13px] font-semibold hover:text-[#c7ff00]">{record.full_name}</Link><span className="mt-1 block text-[11px] text-[#70776f]">{record.primary_language ?? "Unknown"} · {compact(record.stars)} stars</span></td><td className="px-4"><StatusBadge status={state.status} tone={state.tone}/></td><td className="min-w-[130px] px-4">{active === "responsiveness" ? <span className="font-mono text-sm font-semibold">{duration(value)}</span> : <ScoreBar compact value={value} tone={active === "resilience" || active === "health" ? "green" : "blue"}/>}</td><td className="px-4"><ChangeBadge value={getNumber(record.metric,"velocity",active === "delivery" ? "commit_change" : "pr_change")}/></td><td className="px-4 font-mono text-xs">{compact(getNumber(record.metric,"data_quality","event_count"))} events</td><td className="px-4 font-mono text-xs">{Math.round(getNumber(record.metric,"data_quality","confidence_score") ?? 0)}%</td></motion.tr>})}</tbody></table></div></div>{records.length < 3 && <p className="text-xs leading-5 text-[#9ba399]">Rank positions are directional with this small cohort. Add more repositories before treating placement as a benchmark.</p>}</div>;
}

function rankingDisplayValue(record: RepositoryRecord, ranking: Ranking): number | null {
  if (ranking === "momentum") return record.metric?.momentum_score ?? null;
  if (ranking === "health") return record.metric?.health_score ?? null;
  if (ranking === "delivery") return getNumber(record.metric,"velocity","commits");
  if (ranking === "resilience") return getNumber(record.metric,"community","resilience_score");
  const hours = getNumber(record.metric,"responsiveness","median_pr_merge_hours");
  return hours;
}
function rankingSortValue(record: RepositoryRecord, ranking: Ranking): number { const value=rankingDisplayValue(record,ranking); return value==null?-Infinity:ranking==="responsiveness"?-value:value; }
