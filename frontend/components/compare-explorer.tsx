"use client";

import {
  ArrowPathIcon,
  ArrowsRightLeftIcon,
  LinkIcon,
} from "@heroicons/react/20/solid";
import { motion } from "motion/react";
import React, { useEffect, useMemo, useState } from "react";

import { ComparisonActivityChart } from "@/components/charts";
import { Combobox } from "@/components/combobox";
import { ScoreBar, StatusBadge } from "@/components/ui";
import { API, type Activity, type Metric, type Repo } from "@/lib/api";
import {
  assessment,
  compact,
  duration,
  getNumber,
  percent,
} from "@/lib/format";

type ComparisonData = { metric: Metric; activity: Activity[] };

async function loadComparison(repository: string): Promise<ComparisonData> {
  const [owner, name] = repository.split("/");
  const [metricsResponse, activityResponse] = await Promise.all([
    fetch(`${API}/api/v1/repositories/${owner}/${name}/metrics`),
    fetch(`${API}/api/v1/repositories/${owner}/${name}/activity?weeks=12`),
  ]);
  if (!metricsResponse.ok || !activityResponse.ok) {
    throw new Error(`Could not load analytics for ${repository}`);
  }
  return {
    metric: await metricsResponse.json(),
    activity: await activityResponse.json(),
  };
}

export function CompareExplorer({
  repositories,
  initialA,
  initialB,
}: {
  repositories: Repo[];
  initialA?: string;
  initialB?: string;
}) {
  const valid = (value: string | undefined, fallback: string) =>
    repositories.some((repo) => repo.full_name === value) ? value! : fallback;

  const [first, setFirst] = useState(
    valid(initialA, repositories[0]?.full_name ?? "")
  );
  const [second, setSecond] = useState(
    valid(initialB, repositories[1]?.full_name ?? "")
  );
  const [data, setData] = useState<Record<string, ComparisonData>>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!first || !second || first === second) return;
    let active = true;
    setLoading(true);
    setError("");
    window.history.replaceState(
      null,
      "",
      `/compare?a=${encodeURIComponent(first)}&b=${encodeURIComponent(second)}`
    );
    Promise.all([loadComparison(first), loadComparison(second)])
      .then(([left, right]) => {
        if (active) setData({ [first]: left, [second]: right });
      })
      .catch((reason: Error) => {
        if (active) setError(reason.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [first, second]);

  if (repositories.length < 2) {
    return (
      <div className="panel p-8 text-center text-sm text-[#9a9a9a]">
        Ingest at least two repositories to enable comparison.
      </div>
    );
  }

  const left = data[first]?.metric;
  const right = data[second]?.metric;
  const copyLink = () => navigator.clipboard.writeText(window.location.href);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <section className="panel p-5">
        <div className="grid items-end gap-3 md:grid-cols-[1fr_auto_1fr_auto]">
          <RepositorySelect
            label="Repository A"
            value={first}
            onChange={setFirst}
            repositories={repositories}
          />
          <button
            onClick={() => {
              setFirst(second);
              setSecond(first);
            }}
            className="button-secondary !h-10 !w-10 !px-0"
            title="Swap repositories"
          >
            <ArrowsRightLeftIcon className="size-4" />
          </button>
          <RepositorySelect
            label="Repository B"
            value={second}
            onChange={setSecond}
            repositories={repositories}
          />
          <button onClick={copyLink} className="button-secondary !h-10">
            <LinkIcon className="size-4" />
            <span>Copy Link</span>
          </button>
        </div>

        {first === second && (
          <p className="mt-4 rounded-md bg-[#141414] p-3 font-mono text-xs text-[#ffffff]">
            Please choose two different repositories to compare.
          </p>
        )}
        {loading && (
          <p className="mt-4 inline-flex items-center gap-2 font-mono text-xs text-[#9a9a9a]">
            <ArrowPathIcon className="size-3.5 animate-spin text-[#ccf200]" />
            Loading repository evidence…
          </p>
        )}
        {error && (
          <p className="mt-4 rounded-md bg-[#1f1717] p-3 font-mono text-xs text-rose-400">
            {error}
          </p>
        )}
      </section>

      {left && right && first !== second && (
        <>
          <section className="grid gap-4 lg:grid-cols-2">
            <Summary repository={first} metric={left} opponent={right} />
            <Summary repository={second} metric={right} opponent={left} />
          </section>

          <section className="panel overflow-hidden">
            <div className="grid grid-cols-[1.4fr_1fr_1fr] border-b border-[#222222] bg-[#090909] px-5 py-3.5 text-xs font-semibold text-[#ffffff]">
              <span>Measure</span>
              <span className="font-mono text-xs">{first}</span>
              <span className="font-mono text-xs">{second}</span>
            </div>
            <Group title="Strategic signals" />
            <ComparisonRow
              label="Momentum score"
              left={left.momentum_score}
              right={right.momentum_score}
              format="score"
              higher
            />
            <ComparisonRow
              label="Community health"
              left={left.health_score}
              right={right.health_score}
              format="score"
              higher
            />
            <ComparisonRow
              label="Contribution resilience"
              left={100 - (left.bus_factor_risk ?? 100)}
              right={100 - (right.bus_factor_risk ?? 100)}
              format="score"
              higher
            />

            <Group title="Delivery" />
            <ComparisonRow
              label="Human commits"
              left={getNumber(left, "velocity", "commits")}
              right={getNumber(right, "velocity", "commits")}
              higher
            />
            <ComparisonRow
              label="Commit change"
              left={getNumber(left, "velocity", "commit_change")}
              right={getNumber(right, "velocity", "commit_change")}
              format="percent"
              higher
            />
            <ComparisonRow
              label="Pull requests opened"
              left={getNumber(left, "velocity", "pull_requests")}
              right={getNumber(right, "velocity", "pull_requests")}
              higher
            />
            <ComparisonRow
              label="Pull requests merged"
              left={getNumber(left, "velocity", "merged_pull_requests")}
              right={getNumber(right, "velocity", "merged_pull_requests")}
              higher
            />
            <ComparisonRow
              label="Median PR merge cycle"
              left={getNumber(left, "responsiveness", "median_pr_merge_hours")}
              right={getNumber(right, "responsiveness", "median_pr_merge_hours")}
              format="duration"
            />
            <ComparisonRow
              label="Issue net flow (closed − opened)"
              left={getNumber(left, "velocity", "net_issue_flow")}
              right={getNumber(right, "velocity", "net_issue_flow")}
              higher
            />

            <Group title="Community & evidence" />
            <ComparisonRow
              label="Active human contributors"
              left={getNumber(left, "community", "active_contributors")}
              right={getNumber(right, "community", "active_contributors")}
              higher
            />
            <ComparisonRow
              label="Effective contributors (1 / HHI)"
              left={getNumber(left, "concentration", "effective_contributors")}
              right={getNumber(right, "concentration", "effective_contributors")}
              higher
            />
            <ComparisonRow
              label="Top contributor share"
              left={getNumber(left, "concentration", "top_1_share")}
              right={getNumber(right, "concentration", "top_1_share")}
              format="percent"
            />
            <ComparisonRow
              label="Automation share"
              left={getNumber(left, "velocity", "automation_share")}
              right={getNumber(right, "velocity", "automation_share")}
              format="percent"
            />
            <ComparisonRow
              label="Evidence confidence"
              left={getNumber(left, "data_quality", "confidence_score")}
              right={getNumber(right, "data_quality", "confidence_score")}
              format="score"
              higher
            />
          </section>

          <section className="panel p-5">
            <h2 className="section-title">Human commit activity</h2>
            <p className="mb-5 mt-1 font-mono text-xs text-[#9a9a9a]">
              Aligned by UTC date across the last 12 weekly buckets.
            </p>
            <ComparisonActivityChart
              leftName={first}
              rightName={second}
              left={data[first].activity}
              right={data[second].activity}
            />
          </section>
        </>
      )}
    </motion.div>
  );
}

function RepositorySelect({
  label,
  value,
  onChange,
  repositories,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  repositories: Repo[];
}) {
  const options = useMemo(
    () =>
      repositories.map((repo) => ({
        value: repo.full_name,
        label: repo.full_name,
        description: repo.primary_language
          ? `${repo.primary_language} · ★ ${compact(repo.stars)}`
          : `★ ${compact(repo.stars)}`,
      })),
    [repositories]
  );

  return (
    <div className="w-full">
      <Combobox
        label={label}
        value={value}
        onChange={onChange}
        options={options}
        placeholder="Type or select repository…"
        searchPlaceholder="Filter repositories by name or tech…"
        allowCustomValue={true}
      />
    </div>
  );
}

function Summary({
  repository,
  metric,
  opponent,
}: {
  repository: string;
  metric: Metric;
  opponent: Metric;
}) {
  const state = assessment(metric);
  const advantages = [
    {
      label: "Momentum",
      value: metric.momentum_score ?? 0,
      other: opponent.momentum_score ?? 0,
    },
    {
      label: "Health",
      value: metric.health_score ?? 0,
      other: opponent.health_score ?? 0,
    },
    {
      label: "Resilience",
      value: 100 - (metric.bus_factor_risk ?? 100),
      other: 100 - (opponent.bus_factor_risk ?? 100),
    },
  ]
    .filter((item) => item.value - item.other >= 5)
    .map((item) => item.label);

  return (
    <article className="panel p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-mono text-sm font-semibold">{repository}</h2>
        <StatusBadge status={state.status} tone={state.tone} />
      </div>
      <div className="mt-5 grid grid-cols-3 gap-4">
        <MiniScore label="Momentum" value={metric.momentum_score} />
        <MiniScore label="Health" value={metric.health_score} />
        <MiniScore
          label="Resilience"
          value={100 - (metric.bus_factor_risk ?? 100)}
        />
      </div>
      <p className="mt-5 border-t border-[#222222] pt-3 font-mono text-xs text-[#9a9a9a]">
        {advantages.length
          ? `Material advantage in ${advantages.join(" and ").toLowerCase()}.`
          : "No material composite-score advantage; inspect the operating measures below."}
      </p>
    </article>
  );
}

function MiniScore({
  label,
  value,
}: {
  label: string;
  value: number | null;
}) {
  return (
    <div>
      <p className="font-mono text-[10px] uppercase text-[#9a9a9a]">{label}</p>
      <div className="mt-2">
        <ScoreBar compact value={value} />
      </div>
    </div>
  );
}

function Group({ title }: { title: string }) {
  return (
    <div className="border-b border-[#222222] bg-[#111111] px-5 py-2 font-mono text-[10px] font-bold uppercase tracking-wider text-[#9a9a9a]">
      {title}
    </div>
  );
}

function ComparisonRow({
  label,
  left,
  right,
  format = "number",
  higher = false,
}: {
  label: string;
  left: number | null;
  right: number | null;
  format?: "number" | "score" | "percent" | "duration";
  higher?: boolean;
}) {
  const difference =
    left != null && right != null ? Math.abs(left - right) : 0;
  const material =
    format === "percent" ? difference >= 0.05 : difference >= 5;
  const leftWins =
    material && left != null && right != null && (higher ? left > right : left < right);
  const rightWins =
    material && left != null && right != null && (higher ? right > left : right < left);

  const display = (value: number | null) =>
    format === "percent"
      ? percent(value, true)
      : format === "duration"
      ? duration(value)
      : format === "score"
      ? value == null
        ? "—"
        : Math.round(value).toString()
      : compact(value);

  return (
    <div className="grid grid-cols-[1.4fr_1fr_1fr] items-center border-b border-[#222222] px-5 py-3 text-xs last:border-0 hover:bg-[#141414]/40">
      <span className="text-[#9a9a9a]">{label}</span>
      <b className={`font-mono ${leftWins ? "text-[#ccf200]" : "text-[#ffffff]"}`}>
        {display(left)}
      </b>
      <b className={`font-mono ${rightWins ? "text-[#ccf200]" : "text-[#ffffff]"}`}>
        {display(right)}
      </b>
    </div>
  );
}
