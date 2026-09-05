"use client";

import {
  ArrowRightIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  SparklesIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import React, { useCallback, useMemo, useTransition } from "react";

import { Combobox } from "@/components/combobox";
import { StatusBadge } from "@/components/ui";
import type { Facets, ScoutFeedItem } from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";
import { coverage } from "@/lib/watchlist";

interface ScoutFeedProps {
  items: ScoutFeedItem[];
  totalCount: number;
  nextCursor: string | null;
  facets?: Facets;
  currentFilters: {
    cursor?: string;
    lang?: string;
    min_score?: string;
  };
}

const minScoreOptions = [
  { value: "50", label: "≥ 50 Promise Score" },
  { value: "60", label: "≥ 60 Standard Tier" },
  { value: "75", label: "≥ 75 Top Tier" },
  { value: "85", label: "≥ 85 Exceptional" },
];

export function ScoutFeed({
  items,
  totalCount,
  nextCursor,
  facets,
  currentFilters,
}: ScoutFeedProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const updateFilters = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      if (!("cursor" in updates)) {
        params.delete("cursor");
      }
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === undefined || value === "") {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      }
      startTransition(() => {
        router.push(`${pathname}?${params.toString()}`);
      });
    },
    [router, pathname, searchParams]
  );

  const availableLanguages = useMemo(() => {
    if (facets?.languages?.length) {
      return facets.languages.map((l) => l.name);
    }
    return Array.from(
      new Set(items.map((i) => i.primary_language).filter(Boolean) as string[])
    ).sort();
  }, [facets, items]);

  const languageOptions = useMemo(() => {
    return [
      { value: "", label: "All Languages" },
      ...availableLanguages.map((l) => ({ value: l, label: l })),
    ];
  }, [availableLanguages]);

  return (
    <div className="space-y-6">
      {/* Control bar */}
      <div className="panel flex flex-wrap items-center justify-between gap-4 p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <SparklesIcon className="size-4 text-[#ccf200]" />
            <span className="font-mono text-xs font-semibold text-[#ffffff]">
              {totalCount.toLocaleString()} Evaluated Candidates
            </span>
          </div>

          <div className="hidden h-4 w-px bg-[#222222] sm:block" />

          {/* Language filter combobox */}
          <div className="w-48">
            <Combobox
              size="sm"
              value={currentFilters.lang || ""}
              onChange={(val) => updateFilters({ lang: val || null })}
              options={languageOptions}
              placeholder="All Languages"
              searchPlaceholder="Search language…"
            />
          </div>

          {/* Min score filter combobox */}
          <div className="w-48">
            <Combobox
              size="sm"
              value={currentFilters.min_score || "60"}
              onChange={(val) => updateFilters({ min_score: val })}
              options={minScoreOptions}
              placeholder="Min Promise Score"
              searchPlaceholder="Filter score threshold…"
              clearable={false}
            />
          </div>
        </div>

        <div className="flex items-center gap-3 font-mono text-[10px] text-[#646464]">
          {isPending && (
            <span className="animate-pulse text-[#ccf200]">Updating…</span>
          )}
          <span>Showing {items.length} discoveries</span>
        </div>
      </div>

      {/* Cards Feed */}
      <div className="space-y-4">
        {items.map((item) => (
          <article
            key={item.github_id}
            className="panel border border-[#222222] bg-[#0c0c0c] p-6 transition-colors hover:border-[#333333]"
          >
            <div className="grid gap-6 lg:grid-cols-[1fr_280px]">
              {/* Left Column: Repository Info & Assessment */}
              <div className="space-y-4">
                <div className="flex flex-wrap items-center gap-3">
                  <Link
                    href={`/repositories/${item.owner}/${item.name}`}
                    className="font-mono text-base font-bold text-[#ffffff] hover:text-[#ccf200]"
                  >
                    {item.full_name}
                  </Link>
                  {item.primary_language && (
                    <span className="rounded border border-[#222222] bg-[#161616] px-2 py-0.5 font-mono text-[10px] font-semibold text-[#ccf200]">
                      {item.primary_language}
                    </span>
                  )}
                  {item.license && (
                    <span className="rounded border border-[#222222] bg-[#161616] px-2 py-0.5 font-mono text-[10px] text-[#9a9a9a]">
                      {item.license}
                    </span>
                  )}
                  <span className="font-mono text-[10px] text-[#646464]">
                    Updated {relativeDate(item.pushed_at)}
                  </span>
                </div>

                <p className="text-xs leading-relaxed text-[#9a9a9a]">
                  {item.description || "No project description provided."}
                </p>

                {/* Why it surfaced */}
                <div className="rounded-md border-l-2 border-[#ccf200] bg-[#090909] p-3.5">
                  <p className="font-mono text-[10px] font-bold uppercase tracking-wider text-[#ccf200]">
                    Why investigate
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-[#ffffff]">
                    {item.why_it_surfaced ||
                      "Insufficient evidence to explain this selection."}
                  </p>
                </div>

                {/* Supporting Facts Checklist */}
                {item.supporting_facts && item.supporting_facts.length > 0 && (
                  <div>
                    <p className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#646464]">
                      Supporting Evidence
                    </p>
                    <ul className="mt-2 grid gap-1.5 sm:grid-cols-2">
                      {item.supporting_facts.map((fact, idx) => (
                        <li
                          key={idx}
                          className="flex items-start gap-2 text-xs text-[#9a9a9a]"
                        >
                          <CheckCircleIcon className="mt-0.5 size-3.5 shrink-0 text-[#ccf200]" />
                          <span>{fact}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Risk Flags */}
                <div className="flex flex-wrap items-center gap-4 pt-1">
                  {item.risk_flags && item.risk_flags.length > 0 ? (
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[10px] text-amber-400">
                        Observed Factors:
                      </span>
                      {item.risk_flags.map((risk, idx) => (
                        <span
                          key={idx}
                          className="inline-flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 font-mono text-[10px] text-amber-300"
                        >
                          <ExclamationTriangleIcon className="size-3" />
                          {risk}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 font-mono text-[10px] text-[#646464]">
                      <CheckCircleIcon className="size-3.5 text-[#ccf200]" />
                      No elevated risk flags observed
                    </span>
                  )}

                  {item.uncertainty && (
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] text-[#646464]">
                      <InformationCircleIcon className="size-3" />
                      {item.uncertainty}
                    </span>
                  )}
                </div>
              </div>

              {/* Right Column: Score Breakdown */}
              <div className="flex flex-col justify-between border-t border-[#222222] pt-4 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
                <div className="space-y-4">
                  <div className="panel border border-[#222222] bg-[#090909] p-4 text-center">
                    <span className="font-mono text-[10px] font-semibold uppercase tracking-wider text-[#646464]">
                      Ranking heuristic
                    </span>
                    <div className="mt-1 flex items-baseline justify-center gap-1">
                      <span className="font-mono text-3xl font-bold text-[#ccf200]">
                        {item.promise_score}
                      </span>
                      <span className="font-mono text-xs text-[#646464]">
                        /100
                      </span>
                    </div>
                    <div className="mt-2 text-center">
                      <StatusBadge
                        status={
                          "Investigate fit"
                        }
                        tone={
                          item.promise_score >= 80 ? "positive" : "warning"
                        }
                      />
                    </div>
                  </div>

                  {/* Score Breakdown */}
                  <div className="space-y-1.5 font-mono text-[10px]">
                    <div className="flex justify-between text-[#9a9a9a]">
                      <span>Quantitative:</span>
                      <span className="font-bold text-[#ffffff]">
                        {item.score_components?.quantitative_score?.toFixed(
                          1
                        ) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between text-[#9a9a9a]">
                      <span>AI Assessment:</span>
                      <span className="font-bold text-[#ffffff]">
                        {item.score_components?.ai_score?.toFixed(1) ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between text-[#9a9a9a]">
                      <span>Evidence coverage:</span>
                      <span className="font-bold text-[#ccf200]">
                        {coverage(item.confidence)}
                      </span>
                    </div>
                  </div>

                  {/* Scale Stats */}
                  <div className="grid grid-cols-2 gap-2 border-t border-[#222222] pt-3 font-mono text-center">
                    <div>
                      <span className="block text-[9px] uppercase text-[#646464]">
                        Stars
                      </span>
                      <b className="text-xs text-[#ffffff]">
                        {compact(item.stars)}
                      </b>
                    </div>
                    <div>
                      <span className="block text-[9px] uppercase text-[#646464]">
                        Forks
                      </span>
                      <b className="text-xs text-[#ffffff]">
                        {compact(item.forks)}
                      </b>
                    </div>
                  </div>
                </div>

                <div className="pt-4">
                  <Link
                    href={`/repositories/${item.owner}/${item.name}`}
                    className="button-secondary w-full"
                  >
                    <span>Inspect Repository</span>
                    <ArrowRightIcon className="size-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          </article>
        ))}

        {items.length === 0 && (
          <div className="panel p-12 text-center font-mono text-xs text-[#9a9a9a]">
            No Scout discoveries meet the current filter criteria.
          </div>
        )}
      </div>

      {/* Pagination */}
      {nextCursor && (
        <div className="flex justify-center pt-4">
          <button
            type="button"
            onClick={() => updateFilters({ cursor: nextCursor })}
            disabled={isPending}
            className="button-primary"
          >
            Load More Discoveries
          </button>
        </div>
      )}
    </div>
  );
}
