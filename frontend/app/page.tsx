import { ArrowRightIcon, ClockIcon } from "@heroicons/react/20/solid";
import Link from "next/link";

import { SignalMatrix } from "@/components/signal-matrix";
import { ChangeBadge, EmptyState, EvidenceItem, PageHeader, ScoreBar, SectionHeader, StatusBadge, WindowControl } from "@/components/ui";
import { api, mergeRepositories, type RepositoryRecord } from "@/lib/api";
import { assessment, compact, duration, getNumber, relativeDate } from "@/lib/format";

export default async function Overview({ searchParams }: { searchParams: Promise<{ window?: string }> }) {
  const requested = Number((await searchParams).window ?? 30);
  const window = [30, 90, 365].includes(requested) ? requested : 30;
  let records: RepositoryRecord[] = [];
  let unavailable = false;
  try {
    const [repositories, metrics] = await Promise.all([api.repos(), api.rankings("momentum", window)]);
    records = mergeRepositories(repositories, metrics);
  } catch {
    unavailable = true;
  }
  const scored = records.filter((record) => record.metric);
  const activeContributors = scored.reduce((sum, record) => sum + (getNumber(record.metric, "community", "active_contributors") ?? 0), 0);
  const releases = scored.reduce((sum, record) => sum + (getNumber(record.metric, "velocity", "releases") ?? 0), 0);
  const needsAttention = scored.filter((record) => ["At risk", "Watch", "Cooling", "Dormant"].includes(assessment(record.metric).status));
  const medianHealth = median(scored.map((record) => record.metric?.health_score ?? 0));
  const latestSync = records.map((record) => record.last_ingested_at).filter(Boolean).sort().at(-1) ?? null;

  return <main><PageHeader eyebrow="Portfolio intelligence" title="Ecosystem overview" description="A current, evidence-backed view of repository activity, delivery health, and contributor dependency." action={<div className="flex items-center gap-3"><span className="hidden items-center gap-1.5 text-xs text-[#9ba399] sm:flex"><ClockIcon className="size-3.5" />Updated {relativeDate(latestSync)}</span><WindowControl active={window} /></div>} />
    <div className="mx-auto max-w-[1440px] space-y-6 px-5 py-6 md:px-8 xl:px-10">
      {unavailable ? <EmptyState title="The API is not available" description="Start FastAPI on port 8000, then refresh this page. RepoTrajectory never substitutes fabricated analytics." /> : records.length === 0 ? <EmptyState /> : <>
        <section className="grid overflow-hidden rounded-lg border border-[#343a34] bg-[#101310] sm:grid-cols-2 xl:grid-cols-5">
          <Kpi label="Tracked repositories" value={records.length.toString()} note={`${scored.length} scored`} />
          <Kpi label="Median health" value={Math.round(medianHealth).toString()} note="Across scored set" />
          <Kpi label="Active contributors" value={compact(activeContributors)} note={`${window}-day human authors`} />
          <Kpi label="Stable releases" value={compact(releases)} note={`Published in ${window} days`} />
          <Kpi label="Needs attention" value={needsAttention.length.toString()} note="Cooling or dormant" alert={needsAttention.length > 0} />
        </section>

        <section className="grid gap-6 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,.75fr)]">
          <div className="panel overflow-hidden"><SectionHeader title="Signal matrix" description="Interactive portfolio map. Hover to inspect; click a repository to pin its readout." action={<span className="font-mono text-[9px] uppercase tracking-[.08em] text-[#9ba399]">0–100 normalized</span>} /><SignalMatrix records={records} /></div>
          <div className="panel overflow-hidden"><SectionHeader title="Signal ledger" description="Deterministic observations from the latest evidence." /><div className="px-5">{ledger(records).slice(0, 4).map((item, index) => <EvidenceItem key={`${item.title}-${index}`} {...item} />)}</div></div>
        </section>

        <section className="panel overflow-hidden"><SectionHeader title="Repository coverage" description={`${window}-day indicators with human activity separated from automation.`} action={<Link href="/repositories" className="text-xs font-semibold text-[#c7ff00]">Open directory →</Link>} /><div className="overflow-x-auto"><table className="w-full min-w-[920px]"><thead><tr className="border-b border-[#343a34] bg-[#101310]"><th className="table-head px-5 py-3">Repository</th><th className="table-head px-4 py-3">Assessment</th><th className="table-head px-4 py-3">Momentum</th><th className="table-head px-4 py-3">Health</th><th className="table-head px-4 py-3">Commit trend</th><th className="table-head px-4 py-3">Merge cycle</th><th className="table-head px-4 py-3">Concentration</th><th className="w-10" /></tr></thead><tbody>{records.map((record) => <RepositoryRow key={record.full_name} record={record} />)}</tbody></table></div></section>

        {records.length < 10 && <div className="flex items-start gap-3 rounded-lg border border-[#697168] bg-[#101310] px-5 py-4"><span className="mt-0.5 font-mono text-xs font-bold text-[#c7ff00]">N={records.length}</span><p className="text-xs leading-5 text-[#b9c0b7]"><b className="text-[#f1f4ec]">Cohort analysis is collecting baseline.</b> Correlations, “healthy under the radar,” and “popular but cooling” screens become defensible after at least 10 repositories and multiple historical snapshots.</p></div>}
      </>}
    </div>
  </main>;
}

function Kpi({ label, value, note, alert = false }: { label: string; value: string; note: string; alert?: boolean }) { return <div className="border-b border-[#343a34] p-5 last:border-0 sm:border-r xl:border-b-0"><p className="data-label">{label}</p><p className={`metric-value mt-3 ${alert ? "!text-[#f1f4ec]" : ""}`}>{value}</p><p className="mt-2 text-[11px] text-[#70776f]">{note}</p></div>; }

function RepositoryRow({ record }: { record: RepositoryRecord }) {
  const state = assessment(record.metric);
  const mergeHours = getNumber(record.metric, "responsiveness", "median_pr_merge_hours");
  const commitChange = getNumber(record.metric, "velocity", "commit_change");
  const concentration = record.metric?.bus_factor_risk;
  return <tr className="group border-b border-[#343a34] last:border-0 hover:bg-[#101310]"><td className="px-5 py-4"><Link href={`/repositories/${record.owner}/${record.name}`} className="font-mono text-[13px] font-semibold text-[#f1f4ec] group-hover:text-[#c7ff00]">{record.full_name}</Link><div className="mt-1 flex items-center gap-2 text-[11px] text-[#70776f]"><span>{record.primary_language ?? "Unknown"}</span><span>·</span><span>{compact(record.stars)} stars</span></div></td><td className="px-4 py-4"><StatusBadge status={state.status} tone={state.tone} /></td><td className="px-4 py-4"><ScoreBar value={record.metric?.momentum_score} compact /></td><td className="px-4 py-4"><ScoreBar value={record.metric?.health_score} tone="green" compact /></td><td className="px-4 py-4"><ChangeBadge value={commitChange} /></td><td className="px-4 py-4 font-mono text-xs">{duration(mergeHours)}</td><td className="px-4 py-4"><span className={`font-mono text-xs font-semibold ${(concentration ?? 0) >= 70 ? "text-[#f1f4ec]" : ""}`}>{concentration == null ? "—" : Math.round(concentration)}</span></td><td className="px-4"><ArrowRightIcon className="size-4 text-[#70776f] group-hover:text-[#c7ff00]" /></td></tr>;
}

function median(values: number[]): number { if (!values.length) return 0; const sorted = [...values].sort((a, b) => a - b); const middle = Math.floor(sorted.length / 2); return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2; }

function ledger(records: RepositoryRecord[]): Array<{ tone: "positive" | "warning" | "critical" | "neutral"; title: string; detail: string }> {
  if (!records.length) return [{ tone: "neutral", title: "No observations yet", detail: "Ingest repositories to begin the evidence ledger." }];
  return records.flatMap((record) => {
    const change = getNumber(record.metric, "velocity", "commit_change");
    const topShare = getNumber(record.metric, "concentration", "top_1_share");
    const confidence = getNumber(record.metric, "data_quality", "confidence_score");
    const items: Array<{ tone: "positive" | "warning" | "critical" | "neutral"; title: string; detail: string }> = [];
    if (change != null) {
      const flat = Math.abs(change) < .005;
      items.push({
        tone: flat ? "neutral" : change > 0 ? "positive" : change < -.25 ? "critical" : "warning",
        title: flat
          ? `${record.full_name} commit activity was unchanged`
          : `${record.full_name} commit activity ${change > 0 ? "increased" : "declined"} ${Math.abs(change * 100).toFixed(0)}%`,
        detail: `Human-authored commits versus the preceding equal ${record.metric?.window_days ?? 30}-day period.`,
      });
    }
    if (topShare != null && topShare >= .65) items.push({ tone: "critical", title: `${record.full_name} has concentrated contribution activity`, detail: `One contributor accounts for ${(topShare * 100).toFixed(0)}% of observed human commits in the scoring window.` });
    if ((confidence ?? 0) < 50) items.push({ tone: "neutral", title: `${record.full_name} is building evidence`, detail: "Treat its scores as provisional until more events and historical snapshots are collected." });
    return items;
  });
}
