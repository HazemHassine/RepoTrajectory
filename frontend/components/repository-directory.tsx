"use client";

import {
  ArrowLeftIcon,
  ArrowRightIcon,
  MagnifyingGlassIcon,
  XMarkIcon,
} from "@heroicons/react/20/solid";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import React, { useCallback, useMemo, useState, useTransition } from "react";

import { Combobox } from "@/components/combobox";
import { ScoreBar, StatusBadge } from "@/components/ui";
import type { CatalogRepo, Facets } from "@/lib/api";
import { compact, relativeDate } from "@/lib/format";

interface RepositoryDirectoryProps {
  records: CatalogRepo[];
  totalCount: number;
  nextCursor: string | null;
  facets?: Facets;
  currentFilters: {
    cursor?: string;
    lang?: string;
    lens?: string;
    sort?: string;
    order?: string;
    q?: string;
  };
}

const sortOptions = [
  { value: "stars", label: "Stars (Highest)" },
  { value: "promise", label: "Promise Score" },
  { value: "growth", label: "Momentum / Growth" },
  { value: "health", label: "Community Health" },
  { value: "name", label: "Alphabetical (A-Z)" },
];

export function RepositoryDirectory({
  records,
  totalCount,
  nextCursor,
  facets,
  currentFilters,
}: RepositoryDirectoryProps) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();

  const [searchQuery, setSearchQuery] = useState(currentFilters.q || "");

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

  const clearAllFilters = useCallback(() => {
    startTransition(() => {
      router.push(pathname);
      setSearchQuery("");
    });
  }, [router, pathname]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateFilters({ q: searchQuery.trim() || null });
  };

  const activeLens = currentFilters.lens || "developer";
  const activeSort = currentFilters.sort || "stars";
  const activeLang = currentFilters.lang || "";

  // Available languages from facets or distinct records
  const availableLanguages = useMemo(() => {
    if (facets?.languages?.length) {
      return facets.languages.map((l) => l.name);
    }
    return Array.from(
      new Set(
        records.map((r) => r.primary_language).filter(Boolean) as string[]
      )
    ).sort();
  }, [facets, records]);

  const languageOptions = useMemo(() => {
    return [
      { value: "", label: "All Languages" },
      ...availableLanguages.map((l) => ({ value: l, label: l })),
    ];
  }, [availableLanguages]);

  // Active filter chips
  const activeChips: { label: string; onRemove: () => void }[] = [];
  if (currentFilters.q) {
    activeChips.push({
      label: `Search: "${currentFilters.q}"`,
      onRemove: () => {
        setSearchQuery("");
        updateFilters({ q: null });
      },
    });
  }
  if (currentFilters.lang) {
    activeChips.push({
      label: `Language: ${currentFilters.lang}`,
      onRemove: () => updateFilters({ lang: null }),
    });
  }
  if (currentFilters.lens && currentFilters.lens !== "developer") {
    activeChips.push({
      label: `Lens: ${currentFilters.lens}`,
      onRemove: () => updateFilters({ lens: null }),
    });
  }
  if (currentFilters.sort && currentFilters.sort !== "stars") {
    const sortLabel =
      sortOptions.find((s) => s.value === currentFilters.sort)?.label ||
      currentFilters.sort;
    activeChips.push({
      label: `Sort: ${sortLabel}`,
      onRemove: () => updateFilters({ sort: null }),
    });
  }

  return (
    <div className="panel overflow-hidden">
      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-3 border-b border-[#222222] bg-[#0c0c0c] p-4 lg:flex-row lg:items-center lg:justify-between">
        {/* Search */}
        <form
          onSubmit={handleSearchSubmit}
          className="relative flex flex-1 items-center rounded-md border border-[#262626] bg-[#090909] px-3 focus-within:border-[#ccf200]"
        >
          <MagnifyingGlassIcon className="size-4 text-[#646464]" />
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search repositories by name, owner, or topic…"
            className="min-w-0 flex-1 bg-transparent px-2.5 py-2 font-mono text-xs text-[#ffffff] placeholder:text-[#646464] focus:outline-none"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery("");
                updateFilters({ q: null });
              }}
              className="font-mono text-[10px] text-[#646464] hover:text-[#ffffff]"
            >
              CLEAR
            </button>
          )}
        </form>

        <div className="flex flex-wrap items-center gap-3">
          {/* Language Combobox */}
          <div className="w-48">
            <Combobox
              size="sm"
              value={activeLang}
              onChange={(val) => updateFilters({ lang: val || null })}
              options={languageOptions}
              placeholder="All Languages"
              searchPlaceholder="Filter languages…"
            />
          </div>

          {/* Perspective Lens Tabs */}
          <div className="flex items-center rounded-md border border-[#222222] bg-[#090909] p-0.5">
            {(["developer", "maintainer", "investor"] as const).map(
              (lensKey) => (
                <button
                  key={lensKey}
                  type="button"
                  onClick={() =>
                    updateFilters({
                      lens: lensKey === "developer" ? null : lensKey,
                    })
                  }
                  className={`rounded px-2.5 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider transition-colors ${
                    activeLens === lensKey
                      ? "bg-[#ccf200] text-[#050505]"
                      : "text-[#9a9a9a] hover:text-[#ffffff]"
                  }`}
                >
                  {lensKey}
                </button>
              )
            )}
          </div>

          {/* Sort Combobox */}
          <div className="w-44">
            <Combobox
              size="sm"
              value={activeSort}
              onChange={(val) =>
                updateFilters({ sort: val === "stars" ? null : val })
              }
              options={sortOptions}
              placeholder="Sort by"
              searchPlaceholder="Filter sort…"
              clearable={false}
            />
          </div>
        </div>
      </div>

      {/* Active Filter Chips & Summary */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#222222] bg-[#090909] px-5 py-2.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-[10px] text-[#646464]">
            {totalCount
              ? `${totalCount.toLocaleString()} repositories in index`
              : "Loading…"}
          </span>
          {activeChips.length > 0 && (
            <>
              <span className="text-[#222222]">|</span>
              {activeChips.map((chip, idx) => (
                <span
                  key={idx}
                  className="inline-flex items-center gap-1.5 rounded border border-[#ccf200]/40 bg-[#161616] px-2 py-0.5 font-mono text-[10px] text-[#ccf200]"
                >
                  {chip.label}
                  <button
                    type="button"
                    onClick={chip.onRemove}
                    className="text-[#9a9a9a] hover:text-[#ffffff]"
                    aria-label={`Remove filter ${chip.label}`}
                  >
                    <XMarkIcon className="size-3" />
                  </button>
                </span>
              ))}
              <button
                type="button"
                onClick={clearAllFilters}
                className="font-mono text-[10px] text-[#9a9a9a] underline underline-offset-2 hover:text-[#ccf200]"
              >
                Clear all
              </button>
            </>
          )}
        </div>

        <div className="flex items-center gap-3 font-mono text-[10px] text-[#646464]">
          {isPending && (
            <span className="animate-pulse text-[#ccf200]">Updating…</span>
          )}
          <span>Showing {records.length} items</span>
        </div>
      </div>

      {/* Table Content */}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1000px]">
          <thead>
            <tr className="border-b border-[#222222] bg-[#0c0c0c]">
              <th className="table-head px-5 py-3">Repository</th>
              <th className="table-head px-4 py-3">Language</th>
              <th className="table-head px-4 py-3">Stars</th>
              <th className="table-head px-4 py-3">Forks</th>
              {activeLens === "developer" && (
                <>
                  <th className="table-head px-4 py-3">Promise Score</th>
                  <th className="table-head px-4 py-3">Classification</th>
                  <th className="table-head px-4 py-3">License</th>
                </>
              )}
              {activeLens === "maintainer" && (
                <>
                  <th className="table-head px-4 py-3">Health Profile</th>
                  <th className="table-head px-4 py-3">Open Issues</th>
                  <th className="table-head px-4 py-3">Cohort</th>
                </>
              )}
              {activeLens === "investor" && (
                <>
                  <th className="table-head px-4 py-3">Momentum</th>
                  <th className="table-head px-4 py-3">Cohort Tier</th>
                  <th className="table-head px-4 py-3">Selection Score</th>
                </>
              )}
              <th className="table-head px-4 py-3">Activity</th>
            </tr>
          </thead>
          <tbody>
            {records.map((record, index) => {
              const promiseVal =
                record.promise_score ??
                (record.scout?.promise_score ?? null);
              return (
                <tr
                  key={record.full_name}
                  className="group border-b border-[#222222] transition-colors last:border-0 hover:bg-[#111111]"
                >
                  {/* Repository Identity */}
                  <td className="max-w-[340px] px-5 py-3.5">
                    <div className="flex items-start gap-3">
                      <span className="font-mono text-[10px] text-[#646464]">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <Link
                            href={`/repositories/${record.owner}/${record.name}`}
                            className="font-mono text-xs font-bold text-[#ffffff] hover:text-[#ccf200]"
                          >
                            {record.full_name}
                          </Link>
                          {record.is_deep && (
                            <span className="rounded border border-[#ccf200]/40 px-1.5 py-0.5 font-mono text-[8px] font-bold uppercase text-[#ccf200]">
                              Deep Analysis
                            </span>
                          )}
                        </div>
                        <p className="mt-1 truncate text-xs text-[#9a9a9a]">
                          {record.description || "No description provided"}
                        </p>
                      </div>
                    </div>
                  </td>

                  {/* Primary Language */}
                  <td className="px-4">
                    <span className="font-mono text-xs font-medium text-[#ffffff]">
                      {record.primary_language || "—"}
                    </span>
                  </td>

                  {/* Stars */}
                  <td className="px-4">
                    <b className="font-mono text-xs text-[#ffffff]">
                      {compact(record.stars)}
                    </b>
                  </td>

                  {/* Forks */}
                  <td className="px-4">
                    <span className="font-mono text-xs text-[#9a9a9a]">
                      {compact(record.forks)}
                    </span>
                  </td>

                  {/* Lens-specific columns */}
                  {activeLens === "developer" && (
                    <>
                      <td className="px-4">
                        {promiseVal != null ? (
                          <div className="flex items-center gap-1.5 font-mono text-xs">
                            <span className="font-bold text-[#ccf200]">
                              {promiseVal}
                            </span>
                            <span className="text-[#646464]">/100</span>
                          </div>
                        ) : (
                          <span className="font-mono text-xs text-[#646464]">
                            —
                          </span>
                        )}
                      </td>
                      <td className="px-4">
                        <span className="rounded border border-[#222222] bg-[#111111] px-2 py-0.5 font-mono text-[10px] text-[#9a9a9a]">
                          {record.classification || "General"}
                        </span>
                      </td>
                      <td className="px-4 font-mono text-xs text-[#9a9a9a]">
                        {record.license || "None"}
                      </td>
                    </>
                  )}

                  {activeLens === "maintainer" && (
                    <>
                      <td className="px-4">
                        <StatusBadge
                          status={record.is_deep ? "Comprehensive" : "Catalog Tier"}
                          tone={record.is_deep ? "positive" : "neutral"}
                        />
                      </td>
                      <td className="px-4 font-mono text-xs text-[#9a9a9a]">
                        {compact(record.open_issues)}
                      </td>
                      <td className="px-4 font-mono text-xs uppercase text-[#646464]">
                        {record.tier}
                      </td>
                    </>
                  )}

                  {activeLens === "investor" && (
                    <>
                      <td className="px-4">
                        <ScoreBar compact value={record.promise_score ?? 50} />
                      </td>
                      <td className="px-4">
                        <span className="font-mono text-xs font-semibold text-[#ccf200]">
                          {record.is_deep ? "Deep" : "Catalog"}
                        </span>
                      </td>
                      <td className="px-4 font-mono text-xs text-[#9a9a9a]">
                        {record.selection_score?.toFixed(1) ?? "—"}
                      </td>
                    </>
                  )}

                  {/* Freshness */}
                  <td className="px-4 font-mono text-xs text-[#9a9a9a]">
                    {relativeDate(record.pushed_at || record.updated_at)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {records.length === 0 && (
          <div className="p-12 text-center">
            <p className="font-mono text-xs text-[#9a9a9a]">
              No repositories match current filters.
            </p>
            <button
              type="button"
              onClick={clearAllFilters}
              className="mt-3 rounded-md border border-[#262626] bg-[#0c0c0c] px-4 py-2 font-mono text-xs text-[#ccf200] hover:bg-[#141414]"
            >
              Reset all filters
            </button>
          </div>
        )}
      </div>

      {/* Pagination Footer */}
      <div className="flex items-center justify-between border-t border-[#222222] bg-[#0c0c0c] px-5 py-3.5">
        <div className="font-mono text-xs text-[#646464]">
          {currentFilters.cursor ? (
            <button
              type="button"
              onClick={() => updateFilters({ cursor: null })}
              className="inline-flex items-center gap-1.5 text-[#ccf200] hover:underline"
            >
              <ArrowLeftIcon className="size-3" /> Back to first page
            </button>
          ) : (
            <span>Page 1</span>
          )}
        </div>

        <div className="flex items-center gap-3">
          {nextCursor ? (
            <button
              type="button"
              onClick={() => updateFilters({ cursor: nextCursor })}
              disabled={isPending}
              className="button-primary"
            >
              <span>Next 50 Repositories</span>
              <ArrowRightIcon className="size-3.5" />
            </button>
          ) : (
            <span className="font-mono text-xs text-[#646464]">
              End of results
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
