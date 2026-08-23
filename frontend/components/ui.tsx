import {
  ArrowDownRightIcon,
  ArrowUpRightIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  MinusIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";

export function PageHeader({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: React.ReactNode }) {
  return <div className="relative overflow-hidden border-b border-[#697168] bg-[#080a08]">
    <div aria-hidden className="display-face pointer-events-none absolute -bottom-7 right-3 hidden select-none whitespace-nowrap text-[clamp(76px,11vw,180px)] leading-none text-[#101310] lg:block">{title}</div>
    <div className="relative mx-auto grid max-w-[1600px] md:grid-cols-[72px_minmax(0,1fr)_auto]">
      <div className="hidden border-r border-[#343a34] py-7 text-center font-mono text-[9px] tracking-[.14em] text-[#c7ff00] md:block">/RT</div>
      <div className="px-5 py-7 md:px-8 md:py-9 xl:px-10">
        {eyebrow && <p className="eyebrow mb-3">[ {eyebrow} ]</p>}
        <h1 className="display-face max-w-5xl text-[clamp(40px,5.5vw,86px)] leading-[.86] tracking-[-.025em] text-[#f1f4ec]">{title}</h1>
        {description && <p className="mt-5 max-w-3xl border-l border-[#c7ff00] pl-4 text-[13px] leading-6 text-[#9ba399]">{description}</p>}
      </div>
      {action && <div className="relative z-10 flex items-end border-t border-[#343a34] px-5 py-6 md:min-w-[230px] md:border-l md:border-t-0 md:px-6">{action}</div>}
    </div>
    <div className="absolute bottom-0 left-0 h-[3px] w-20 bg-[#c7ff00]" />
  </div>;
}

export function SectionHeader({ title, description, action }: { title: string; description?: string; action?: React.ReactNode }) {
  return <div className="relative flex flex-wrap items-start justify-between gap-3 border-b border-[#343a34] bg-[#101310] px-5 py-4 before:absolute before:left-0 before:top-0 before:h-full before:w-[3px] before:bg-[#c7ff00]">
    <div><h2 className="section-title">{title}</h2>{description && <p className="mt-1.5 max-w-2xl font-mono text-[10px] leading-4 text-[#9ba399]">{description}</p>}</div>{action}
  </div>;
}

const toneStyles: Record<string, string> = {
  positive: "border-[#c7ff00] bg-[#c7ff00] text-[#080a08]",
  warning: "border-[#c7ff00] bg-[#101310] text-[#c7ff00]",
  critical: "border-[#f1f4ec] bg-[#f1f4ec] text-[#f1f4ec]",
  neutral: "border-[#697168] bg-[#101310] text-[#9ba399]",
};

export function StatusBadge({ status, tone = "neutral" }: { status: string; tone?: string }) {
  return <span className={`inline-flex items-center gap-2 whitespace-nowrap border px-2 py-1 font-mono text-[9px] font-black uppercase tracking-[.08em] ${toneStyles[tone] ?? toneStyles.neutral}`}><span className="size-1.5 bg-current" />{status}</span>;
}

export function ChangeBadge({ value, inverse = false }: { value: number | null | undefined; inverse?: boolean }) {
  if (value == null) return <span className="font-mono text-[10px] uppercase text-[#70776f]">Baseline pending</span>;
  const up = value > .005;
  const down = value < -.005;
  const favorable = inverse ? down : up;
  const Icon = up ? ArrowUpRightIcon : down ? ArrowDownRightIcon : MinusIcon;
  return <span className={`inline-flex items-center gap-1 font-mono text-[10px] font-black ${favorable ? "text-[#c7ff00]" : down || up ? "text-[#f1f4ec]" : "text-[#9ba399]"}`}><Icon className="size-3.5" />{up ? "+" : ""}{(value * 100).toFixed(Math.abs(value) >= .1 ? 0 : 1)}%</span>;
}

export function ScoreBar({ value, compact = false }: { value: number | null | undefined; tone?: "blue" | "green" | "amber" | "red"; compact?: boolean }) {
  return <div className={compact ? "w-24" : "w-full"}>
    <div className="flex items-end justify-between gap-3"><span className={`${compact ? "text-sm" : "text-[30px]"} font-mono font-black tracking-[-0.06em]`}>{value == null ? "—" : Math.round(value)}</span>{!compact && <span className="font-mono text-[8px] uppercase tracking-[.12em] text-[#70776f]">Index / 100</span>}</div>
    <div className="mt-2 h-2 overflow-hidden border border-[#343a34] bg-[repeating-linear-gradient(90deg,#171b17_0,#171b17_8px,#080a08_8px,#080a08_10px)]"><div className="h-full origin-left bg-[#c7ff00] motion-safe:animate-[score-grow_.7s_cubic-bezier(.22,1,.36,1)]" style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }} /></div>
  </div>;
}

export function EvidenceItem({ tone, title, detail }: { tone: "positive" | "warning" | "critical" | "neutral"; title: string; detail: string }) {
  const Icon = tone === "positive" ? CheckIcon : tone === "neutral" ? InformationCircleIcon : ExclamationTriangleIcon;
  return <div className="group relative grid grid-cols-[30px_1fr] gap-3 border-b border-[#343a34] py-4 last:border-0">
    <div className={`grid size-6 place-items-center border font-mono text-[9px] ${tone === "positive" ? "border-[#c7ff00] bg-[#c7ff00] text-[#080a08]" : "border-[#697168] text-[#f1f4ec]"}`}><Icon className="size-3.5" /></div>
    <div><p className="text-[13px] font-bold text-[#f1f4ec] group-hover:text-[#c7ff00]">{title}</p><p className="mt-1 font-mono text-[10px] leading-5 text-[#9ba399]">{detail}</p></div>
  </div>;
}

export function EmptyState({ title = "No repositories yet", description = "Ingest a repository to begin building an evidence base." }: { title?: string; description?: string }) {
  return <div className="panel hairline-grid mx-auto max-w-2xl p-8 text-center md:p-12"><div className="mx-auto grid size-12 place-items-center border border-[#c7ff00] bg-[#c7ff00] font-mono text-xs font-black text-[#080a08]">00</div><h2 className="display-face mt-6 text-3xl">{title}</h2><p className="mx-auto mt-3 max-w-md text-sm leading-6 text-[#9ba399]">{description}</p><code className="mt-6 inline-block border border-[#697168] bg-[#080a08] px-4 py-3 font-mono text-[10px] text-[#c7ff00]">python -m app.cli ingest owner/repo</code></div>;
}

export function WindowControl({ active = 30 }: { active?: number }) {
  return <div className="inline-flex border border-[#697168] bg-[#080a08]">{[30, 90, 365].map((days) => <Link key={days} href={`?window=${days}`} className={`border-r border-[#343a34] px-3 py-2 font-mono text-[9px] font-black uppercase tracking-[.08em] last:border-0 ${active === days ? "bg-[#c7ff00] text-[#080a08]" : "text-[#9ba399] hover:text-[#c7ff00]"}`}>{days === 365 ? "1y" : `${days}d`}</Link>)}</div>;
}
