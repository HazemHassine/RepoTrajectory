import {
  ArrowDownRightIcon,
  ArrowUpRightIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  MinusIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import React from "react";

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="border-b border-[#222222] bg-[#080808]">
      <div className="mx-auto flex max-w-[1600px] flex-col justify-between gap-6 px-5 py-8 md:flex-row md:items-end md:px-8 xl:px-10">
        <div className="max-w-4xl">
          {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
          <h1 className="text-3xl font-bold tracking-tight text-[#ffffff] sm:text-4xl md:text-5xl">
            {title}
          </h1>
          {description && (
            <p className="mt-2.5 text-sm leading-relaxed text-[#9a9a9a]">
              {description}
            </p>
          )}
        </div>
        {action && (
          <div className="shrink-0 flex items-center">{action}</div>
        )}
      </div>
    </div>
  );
}

export function SectionHeader({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#222222] bg-[#0c0c0c] px-5 py-3.5">
      <div>
        <h2 className="section-title">{title}</h2>
        {description && (
          <p className="mt-0.5 font-mono text-[11px] leading-4 text-[#9a9a9a]">
            {description}
          </p>
        )}
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}

const toneStyles: Record<string, string> = {
  positive: "border-[#ccf200]/40 bg-[#ccf200]/10 text-[#ccf200]",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  critical: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  neutral: "border-[#2a2a2a] bg-[#141414] text-[#9a9a9a]",
};

export function StatusBadge({
  status,
  tone = "neutral",
}: {
  status: string;
  tone?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 font-mono text-[9px] font-semibold uppercase tracking-wider ${
        toneStyles[tone] ?? toneStyles.neutral
      }`}
    >
      <span className="size-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}

export function ChangeBadge({
  value,
  inverse = false,
}: {
  value: number | null | undefined;
  inverse?: boolean;
}) {
  if (value == null) {
    return (
      <span className="font-mono text-[10px] text-[#646464]">
        Baseline pending
      </span>
    );
  }
  const up = value > 0.005;
  const down = value < -0.005;
  const favorable = inverse ? down : up;
  const Icon = up ? ArrowUpRightIcon : down ? ArrowDownRightIcon : MinusIcon;
  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[10px] font-bold ${
        favorable
          ? "text-[#ccf200]"
          : down || up
          ? "text-[#ffffff]"
          : "text-[#9a9a9a]"
      }`}
    >
      <Icon className="size-3.5" />
      {up ? "+" : ""}
      {(value * 100).toFixed(Math.abs(value) >= 0.1 ? 0 : 1)}%
    </span>
  );
}

export function ScoreBar({
  value,
  compact = false,
}: {
  value: number | null | undefined;
  tone?: "blue" | "green" | "amber" | "red";
  compact?: boolean;
}) {
  const roundedVal = value == null ? null : Math.round(value);
  return (
    <div className={compact ? "w-24" : "w-full"}>
      <div className="flex items-baseline justify-between gap-2">
        <span
          className={`font-mono font-bold tracking-tight text-[#ffffff] ${
            compact ? "text-sm" : "text-2xl"
          }`}
        >
          {roundedVal == null ? "—" : roundedVal}
        </span>
        {!compact && (
          <span className="font-mono text-[9px] uppercase tracking-wider text-[#646464]">
            Index / 100
          </span>
        )}
      </div>
      <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[#1c1c1c]">
        <div
          className="h-full rounded-full bg-[#ccf200] transition-all duration-300"
          style={{ width: `${Math.max(0, Math.min(100, value ?? 0))}%` }}
        />
      </div>
    </div>
  );
}

export function EvidenceItem({
  tone,
  title,
  detail,
}: {
  tone: "positive" | "warning" | "critical" | "neutral";
  title: string;
  detail: string;
}) {
  const Icon =
    tone === "positive"
      ? CheckIcon
      : tone === "neutral"
      ? InformationCircleIcon
      : ExclamationTriangleIcon;
  return (
    <div className="grid grid-cols-[24px_1fr] gap-3 border-b border-[#1c1c1c] py-3.5 last:border-0">
      <div
        className={`grid size-5 place-items-center rounded ${
          tone === "positive"
            ? "bg-[#ccf200]/10 text-[#ccf200]"
            : "bg-[#141414] text-[#9a9a9a]"
        }`}
      >
        <Icon className="size-3.5" />
      </div>
      <div>
        <p className="text-xs font-semibold text-[#ffffff]">{title}</p>
        <p className="mt-1 font-mono text-[11px] leading-relaxed text-[#9a9a9a]">
          {detail}
        </p>
      </div>
    </div>
  );
}

export function EmptyState({
  title = "No repositories found",
  description = "No repositories currently match your criteria.",
}: {
  title?: string;
  description?: string;
}) {
  return (
    <div className="panel mx-auto max-w-xl p-8 text-center md:p-12">
      <div className="mx-auto grid size-10 place-items-center rounded-full border border-[#262626] bg-[#141414] text-[#9a9a9a]">
        <InformationCircleIcon className="size-5 text-[#ccf200]" />
      </div>
      <h2 className="mt-4 text-xl font-bold text-[#ffffff]">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-xs leading-relaxed text-[#9a9a9a]">
        {description}
      </p>
    </div>
  );
}

export function WindowControl({ active = 30 }: { active?: number }) {
  return (
    <div className="inline-flex rounded-md border border-[#262626] bg-[#0c0c0c] p-0.5">
      {[30, 90, 365].map((days) => (
        <Link
          key={days}
          href={`?window=${days}`}
          className={`rounded px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider transition-colors ${
            active === days
              ? "bg-[#ccf200] text-[#050505]"
              : "text-[#9a9a9a] hover:text-[#ffffff]"
          }`}
        >
          {days === 365 ? "1y" : `${days}d`}
        </Link>
      ))}
    </div>
  );
}
