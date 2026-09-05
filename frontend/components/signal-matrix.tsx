"use client";

import { ArrowRightIcon, LockClosedIcon } from "@heroicons/react/20/solid";
import { AnimatePresence, motion } from "motion/react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { StatusBadge } from "@/components/ui";
import type { RepositoryRecord } from "@/lib/api";
import { assessment, compact, getNumber } from "@/lib/format";

type Filter = "all" | "advancing" | "watch" | "under-radar";
type Point = RepositoryRecord & { x: number; y: number; size: number };

const filters: Array<{ key: Filter; label: string }> = [
  { key: "all", label: "All" },
  { key: "advancing", label: "Advancing" },
  { key: "watch", label: "Needs review" },
  { key: "under-radar", label: "Under radar" },
];

const ticks = [0, 25, 50, 75, 100];

function matchesFilter(point: Point, filter: Filter, medianStars: number) {
  if (filter === "advancing") return point.x >= 60 && point.y >= 60;
  if (filter === "watch") return point.x < 50 || point.y < 40;
  if (filter === "under-radar") return point.stars <= medianStars && point.x + point.y >= 120;
  return true;
}

export function SignalMatrix({ records }: { records: RepositoryRecord[] }) {
  const points = useMemo<Point[]>(() => records
    .filter((record) => record.metric?.momentum_score != null && record.metric?.health_score != null)
    .map((record) => ({
      ...record,
      x: Math.max(1, Math.min(99, record.metric!.health_score!)),
      y: Math.max(1, Math.min(99, record.metric!.momentum_score!)),
      size: Math.max(11, Math.min(28, 8 + Math.log10(record.stars + 10) * 3.3)),
    }))
    .sort((a, b) => a.stars - b.stars), [records]);

  const medianStars = useMemo(() => {
    const sorted = points.map((point) => point.stars).sort((a, b) => a - b);
    return sorted[Math.floor(sorted.length / 2)] ?? 0;
  }, [points]);

  const [filter, setFilter] = useState<Filter>("all");
  const [hovered, setHovered] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);

  const visible = points.filter((point) => matchesFilter(point, filter, medianStars));
  const activeName = hovered ?? pinned;
  const active = visible.find((point) => point.full_name === activeName)
    ?? [...visible].sort((a, b) => b.x + b.y - (a.x + a.y))[0];

  if (!points.length) return <div className="grid h-[360px] place-items-center font-mono text-[10px] uppercase text-[#9a9a9a]">No scored repositories yet</div>;

  return <div>
    <div className="grid border-b border-[#222222] lg:grid-cols-[1fr_auto]">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2 px-5 py-3 font-mono text-[9px] uppercase tracking-[.08em] text-[#9a9a9a]">
        <span className="inline-flex items-center gap-2"><span className="size-2 rotate-45 border border-[#ffffff] bg-[#ccf200]" />Repository</span>
        <span className="inline-flex items-end gap-1.5"><span className="size-2 rotate-45 border border-[#343434]" /><span className="size-3 rotate-45 border border-[#343434]" /><span className="size-4 rotate-45 border border-[#343434]" /><span className="ml-1">Marker size = stars</span></span>
        <span className="inline-flex items-center gap-2"><span className="w-5 border-t border-dashed border-[#343434]" />50-point threshold</span>
      </div>
      <div className="flex overflow-x-auto border-t border-[#222222] lg:border-l lg:border-t-0">
        {filters.map((item) => {
          const count = points.filter((point) => matchesFilter(point, item.key, medianStars)).length;
          return <motion.button key={item.key} whileTap={{ scale: .96 }} onClick={() => { setFilter(item.key); setHovered(null); setPinned(null); }} className={`whitespace-nowrap border-r border-[#222222] px-3 py-3 font-mono text-[9px] font-bold uppercase tracking-[.06em] last:border-0 ${filter === item.key ? "bg-[#ccf200] text-[#050505]" : "bg-[#0c0c0c] text-[#9a9a9a] hover:text-[#ccf200]"}`}>{item.label} <span className="ml-1 opacity-60">{count}</span></motion.button>;
        })}
      </div>
    </div>

    <div className="grid lg:grid-cols-[minmax(0,1fr)_260px]">
      <div className="relative min-h-[420px] border-b border-[#222222] bg-[#050505] lg:border-b-0 lg:border-r">
        <div className="absolute bottom-[54px] left-[58px] right-[20px] top-[22px]">
          <div className="absolute inset-0 overflow-hidden border border-[#222222] bg-[#090909]">
            <div className="absolute left-1/2 top-0 h-1/2 w-1/2 bg-[repeating-linear-gradient(135deg,rgba(204,242,0,.04)_0,rgba(204,242,0,.04)_1px,transparent_1px,transparent_10px)]" />
            <div className="absolute bottom-0 left-0 h-1/2 w-1/2 bg-[repeating-linear-gradient(135deg,rgba(255,255,255,.02)_0,rgba(255,255,255,.02)_1px,transparent_1px,transparent_10px)]" />

            {ticks.map((tick) => <div key={`x-${tick}`} className={`absolute bottom-0 top-0 border-l ${tick === 50 ? "border-dashed border-[#343434]" : "border-[#222222]"}`} style={{ left: `${tick}%` }} />)}
            {ticks.map((tick) => <div key={`y-${tick}`} className={`absolute left-0 right-0 border-t ${tick === 50 ? "border-dashed border-[#343434]" : "border-[#222222]"}`} style={{ bottom: `${tick}%` }} />)}

            <Quadrant className="left-3 top-3" code="Q2" title="Momentum / fragile" detail="Acceleration with weaker health" />
            <Quadrant className="right-3 top-3 text-right" code="Q1" title="Advancing" detail="Strong momentum and health" accent />
            <Quadrant className="bottom-3 left-3" code="Q3" title="Intervention" detail="Low momentum and health" />
            <Quadrant className="bottom-3 right-3 text-right" code="Q4" title="Healthy / steady" detail="Resilient, lower acceleration" />

            {active && <><motion.div className="pointer-events-none absolute bottom-0 top-0 z-[2] border-l border-[#ccf200]/50" animate={{ left: `${active.x}%` }} /><motion.div className="pointer-events-none absolute left-0 right-0 z-[2] border-t border-[#ccf200]/50" animate={{ bottom: `${active.y}%` }} /></>}

            <AnimatePresence initial={false}>
              {visible.map((point, index) => {
                const selected = active?.full_name === point.full_name;
                const tooltipRight = point.x > 70;
                const tooltipBelow = point.y > 72;
                return <motion.div
                  key={point.full_name}
                  className="absolute z-10"
                  style={{ left: `${point.x}%`, bottom: `${point.y}%`, x: "-50%", y: "50%" }}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0, scale: .4 }}
                  transition={{ delay: Math.min(index * .012, .35) }}
                >
                  <motion.button
                    type="button"
                    aria-label={`${point.full_name}: momentum ${Math.round(point.y)}, community health ${Math.round(point.x)}`}
                    aria-pressed={pinned === point.full_name}
                    onMouseEnter={() => setHovered(point.full_name)}
                    onMouseLeave={() => setHovered(null)}
                    onFocus={() => setHovered(point.full_name)}
                    onBlur={() => setHovered(null)}
                    onClick={() => setPinned((current) => current === point.full_name ? null : point.full_name)}
                    className={`block rotate-45 border-2 outline-none ${selected ? "border-[#ffffff] bg-[#ccf200]" : "border-[#646464] bg-[#161616] hover:border-[#ccf200]"}`}
                    style={{ width: point.size, height: point.size }}
                    initial={{ scale: 0, rotate: 45 }}
                    animate={{ scale: 1, rotate: 45, boxShadow: selected ? "0 0 0 4px rgba(204,242,0,.16)" : "none" }}
                    transition={{ delay: Math.min(index * .012, .35), type: "spring", stiffness: 310, damping: 18 }}
                    whileHover={{ scale: 1.45, rotate: 45 }}
                    whileFocus={{ scale: 1.35, rotate: 45 }}
                  />
                  <AnimatePresence>
                    {hovered === point.full_name && <motion.div initial={{ opacity: 0, y: tooltipBelow ? -4 : 4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className={`pointer-events-none absolute z-30 min-w-[170px] rounded border border-[#222222] bg-[#0c0c0c] p-2.5 shadow-xl ${tooltipRight ? "right-full mr-3" : "left-full ml-3"} ${tooltipBelow ? "bottom-full mb-2" : "top-full mt-2"}`}>
                      <p className="font-mono text-[10px] font-bold text-[#ffffff]">{point.full_name}</p>
                      <p className="mt-1 font-mono text-[9px] text-[#9a9a9a]">MOM {Math.round(point.y)} / HEALTH {Math.round(point.x)} / ★ {compact(point.stars)}</p>
                    </motion.div>}
                  </AnimatePresence>
                </motion.div>;
              })}
            </AnimatePresence>
          </div>

          {ticks.map((tick) => <span key={`x-label-${tick}`} className="absolute top-full mt-2 -translate-x-1/2 font-mono text-[8px] text-[#646464]" style={{ left: `${tick}%` }}>{tick}</span>)}
          {ticks.map((tick) => <span key={`y-label-${tick}`} className="absolute right-full mr-2 translate-y-1/2 font-mono text-[8px] text-[#646464]" style={{ bottom: `${tick}%` }}>{tick}</span>)}
        </div>
        <span className="absolute bottom-3 left-[58px] right-5 text-center font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#9a9a9a]">Community health →</span>
        <span className="absolute bottom-[54px] left-3 top-[22px] grid place-items-center"><span className="-rotate-90 whitespace-nowrap font-mono text-[9px] font-bold uppercase tracking-[.1em] text-[#9a9a9a]">Momentum →</span></span>
      </div>

      <SignalReadout active={active} visible={visible.length} total={points.length} pinned={pinned === active?.full_name} />
    </div>
  </div>;
}

function Quadrant({ className, code, title, detail, accent = false }: { className: string; code: string; title: string; detail: string; accent?: boolean }) {
  return <div className={`pointer-events-none absolute z-[1] ${className}`}><p className={`font-mono text-[8px] font-bold uppercase tracking-[.1em] ${accent ? "text-[#ccf200]" : "text-[#646464]"}`}>{code} / {title}</p><p className="mt-1 hidden font-mono text-[8px] text-[#646464] xl:block">{detail}</p></div>;
}

function SignalReadout({ active, visible, total, pinned }: { active?: Point; visible: number; total: number; pinned: boolean }) {
  if (!active) return <div className="grid min-h-[220px] place-items-center p-5 font-mono text-[10px] uppercase text-[#646464]">No signals match this view</div>;
  const state = assessment(active.metric);
  const confidence = getNumber(active.metric, "data_quality", "confidence_score");
  const concentration = active.metric?.bus_factor_risk;

  return <motion.aside key={active.full_name} initial={{ opacity: 0, x: 8 }} animate={{ opacity: 1, x: 0 }} className="flex min-h-[260px] flex-col bg-[#0c0c0c]">
    <div className="flex items-center justify-between border-b border-[#222222] px-4 py-3 font-mono text-[8px] uppercase tracking-[.12em] text-[#646464]"><span>Signal readout</span><span>{visible} / {total}</span></div>
    <div className="p-4">
      <div className="flex items-start justify-between gap-3"><span className="font-mono text-[8px] text-[#ccf200]">{pinned ? "PINNED" : "LIVE HOVER"}</span>{pinned && <LockClosedIcon className="size-3 text-[#ccf200]" />}</div>
      <h3 className="mt-3 break-all font-mono text-[13px] font-bold leading-5 text-[#ffffff]">{active.full_name}</h3>
      <div className="mt-3"><StatusBadge status={state.status} tone={state.tone} /></div>
      <div className="mt-5 grid grid-cols-2 gap-px border border-[#222222] bg-[#222222]">
        <ReadoutMetric label="Momentum" value={Math.round(active.y).toString()} />
        <ReadoutMetric label="Health" value={Math.round(active.x).toString()} />
        <ReadoutMetric label="Stars" value={compact(active.stars)} />
        <ReadoutMetric label="Evidence coverage" value={confidence == null ? "Unknown" : `${Math.round(confidence)}%`} />
      </div>
      <div className="mt-4 border-l border-[#ccf200] pl-3"><p className="font-mono text-[9px] uppercase text-[#9a9a9a]">Contribution concentration</p><p className="mt-1 font-mono text-sm font-bold">{concentration == null ? "—" : Math.round(concentration)}<span className="ml-1 text-[8px] font-normal text-[#646464]">/ 100 RISK</span></p></div>
    </div>
    <Link href={`/repositories/${active.owner}/${active.name}`} className="group mt-auto flex items-center justify-between border-t border-[#222222] px-4 py-3 font-mono text-[9px] font-bold uppercase tracking-[.08em] text-[#ccf200] hover:bg-[#ccf200] hover:text-[#050505]">Open dossier <ArrowRightIcon className="size-3.5 transition-transform group-hover:translate-x-1" /></Link>
  </motion.aside>;
}

function ReadoutMetric({ label, value }: { label: string; value: string }) {
  return <div className="bg-[#0c0c0c] p-3"><p className="font-mono text-[8px] uppercase tracking-[.08em] text-[#646464]">{label}</p><p className="mt-1.5 font-mono text-lg font-bold tracking-[-.05em]">{value}</p></div>;
}
