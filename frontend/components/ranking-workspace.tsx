"use client";

import { ArrowsRightLeftIcon } from "@heroicons/react/20/solid";
import { motion } from "motion/react";
import Link from "next/link";
import React, { useMemo, useState } from "react";

import { ChangeBadge, ScoreBar, StatusBadge } from "@/components/ui";
import type { RepositoryRecord } from "@/lib/api";
import { assessment, compact, duration, getNumber } from "@/lib/format";

type Ranking =
  | "momentum"
  | "health"
  | "delivery"
  | "resilience"
  | "responsiveness";

const tabs: Array<{ key: Ranking; label: string; description: string }> = [
  {
    key: "momentum",
    label: "Momentum",
    description: "Normalized activity acceleration and growth trajectory",
  },
  {
    key: "health",
    label: "Community Health",
    description: "Responsiveness, maintainers, delivery cadence, and activity",
  },
  {
    key: "delivery",
    label: "Delivery Velocity",
    description: "Human commit volume across observation period",
  },
  {
    key: "resilience",
    label: "Resilience",
    description: "Lower contributor concentration and higher distribution",
  },
  {
    key: "responsiveness",
    label: "Merge Cycle",
    description: "Median time to merge resolved pull requests",
  },
];

export function RankingWorkspace({
  records,
}: {
  records: RepositoryRecord[];
}) {
  const [active, setActive] = useState<Ranking>("momentum");
  const [selected, setSelected] = useState<string[]>([]);

  const ordered = useMemo(
    () =>
      [...records].sort(
        (a, b) => rankingSortValue(b, active) - rankingSortValue(a, active)
      ),
    [records, active]
  );

  const toggle = (name: string) =>
    setSelected((current) =>
      current.includes(name)
        ? current.filter((item) => item !== name)
        : current.length < 2
        ? [...current, name]
        : [current[1], name]
    );

  const compareHref =
    selected.length === 2
      ? `/compare?a=${encodeURIComponent(selected[0])}&b=${encodeURIComponent(
          selected[1]
        )}`
      : "#";

  const activeTabInfo = tabs.find((tab) => tab.key === active);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        {/* Metric selection tabs */}
        <div className="flex max-w-full gap-1 overflow-x-auto rounded-md border border-[#222222] bg-[#0c0c0c] p-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActive(tab.key)}
              className={`whitespace-nowrap rounded px-3 py-1.5 font-mono text-xs font-semibold transition-colors ${
                active === tab.key
                  ? "bg-[#ccf200] text-[#050505]"
                  : "text-[#9a9a9a] hover:bg-[#161616] hover:text-[#ffffff]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <Link
          aria-disabled={selected.length !== 2}
          href={compareHref}
          className={`button-secondary ${
            selected.length !== 2 ? "pointer-events-none opacity-40" : ""
          }`}
        >
          <ArrowsRightLeftIcon className="size-4" />
          <span>Compare Selected ({selected.length}/2)</span>
        </Link>
      </div>

      <div className="panel overflow-hidden">
        <div className="flex items-center justify-between border-b border-[#222222] bg-[#0c0c0c] px-5 py-3">
          <p className="font-mono text-xs text-[#9a9a9a]">
            {activeTabInfo?.description}
          </p>
          <p className="font-mono text-[11px] text-[#646464]">
            Cohort: {records.length} repositories
          </p>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px]">
            <thead>
              <tr className="border-b border-[#222222] bg-[#0c0c0c]">
                <th className="w-12 px-5" />
                <th className="table-head px-2 py-3">Rank</th>
                <th className="table-head px-4 py-3">Repository</th>
                <th className="table-head px-4 py-3">Assessment</th>
                <th className="table-head px-4 py-3">Ranked Value</th>
                <th className="table-head px-4 py-3">Period Change</th>
                <th className="table-head px-4 py-3">Evidence</th>
                <th className="table-head px-4 py-3">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((record, index) => {
                const state = assessment(record.metric);
                const value = rankingDisplayValue(record, active);
                return (
                  <motion.tr
                    layout
                    transition={{ type: "spring", stiffness: 320, damping: 30 }}
                    key={record.full_name}
                    className="border-b border-[#222222] transition-colors last:border-0 hover:bg-[#0c0c0c]"
                  >
                    <td className="px-5">
                      <input
                        aria-label={`Select ${record.full_name}`}
                        type="checkbox"
                        checked={selected.includes(record.full_name)}
                        onChange={() => toggle(record.full_name)}
                        className="size-4 rounded accent-[#ccf200]"
                      />
                    </td>
                    <td className="px-2 font-mono text-xs text-[#646464]">
                      {String(index + 1).padStart(2, "0")}
                    </td>
                    <td className="px-4 py-3.5">
                      <Link
                        href={`/repositories/${record.owner}/${record.name}`}
                        className="font-mono text-xs font-bold text-[#ffffff] hover:text-[#ccf200]"
                      >
                        {record.full_name}
                      </Link>
                      <span className="mt-0.5 block font-mono text-[11px] text-[#9a9a9a]">
                        {record.primary_language ?? "Unknown"} ·{" "}
                        {compact(record.stars)} stars
                      </span>
                    </td>
                    <td className="px-4">
                      <StatusBadge status={state.status} tone={state.tone} />
                    </td>
                    <td className="min-w-[130px] px-4">
                      {active === "responsiveness" ? (
                        <span className="font-mono text-xs font-semibold">
                          {duration(value)}
                        </span>
                      ) : (
                        <ScoreBar
                          compact
                          value={value}
                          tone={
                            active === "resilience" || active === "health"
                              ? "green"
                              : "blue"
                          }
                        />
                      )}
                    </td>
                    <td className="px-4">
                      <ChangeBadge
                        value={getNumber(
                          record.metric,
                          "velocity",
                          active === "delivery"
                            ? "commit_change"
                            : "pr_change"
                        )}
                      />
                    </td>
                    <td className="px-4 font-mono text-xs text-[#9a9a9a]">
                      {compact(
                        getNumber(record.metric, "data_quality", "event_count")
                      )}{" "}
                      events
                    </td>
                    <td className="px-4 font-mono text-xs text-[#9a9a9a]">
                      {Math.round(
                        getNumber(
                          record.metric,
                          "data_quality",
                          "confidence_score"
                        ) ?? 0
                      )}
                      %
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function rankingDisplayValue(
  record: RepositoryRecord,
  ranking: Ranking
): number | null {
  if (ranking === "momentum") return record.metric?.momentum_score ?? null;
  if (ranking === "health") return record.metric?.health_score ?? null;
  if (ranking === "delivery")
    return getNumber(record.metric, "velocity", "commits");
  if (ranking === "resilience")
    return getNumber(record.metric, "community", "resilience_score");
  const hours = getNumber(
    record.metric,
    "responsiveness",
    "median_pr_merge_hours"
  );
  return hours;
}

function rankingSortValue(
  record: RepositoryRecord,
  ranking: Ranking
): number {
  const value = rankingDisplayValue(record, ranking);
  return value == null
    ? -Infinity
    : ranking === "responsiveness"
    ? -value
    : value;
}
