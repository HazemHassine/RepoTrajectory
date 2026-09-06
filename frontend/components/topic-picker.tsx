"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronRightIcon, MagnifyingGlassIcon, Squares2X2Icon } from "@heroicons/react/24/outline";
import type { Topic } from "@/lib/product-api";

const count = (value?: number) => value == null ? null : value.toLocaleString("en-GB");

export function TopicPicker({ topics, selected }: { topics: Topic[]; selected?: string }) {
  const [query, setQuery] = useState("");
  const current = topics.find(topic => topic.slug === selected);
  // Older APIs return a flat AI-only taxonomy. Keep those links usable during rollout.
  const legacy = topics.length > 0 && topics.every(topic => topic.parent_slug === undefined);
  const roots = legacy ? [{ slug: "legacy-ai", name: "AI & Machine Learning" }] : topics.filter(topic => !topic.parent_slug);
  const activeRoot = legacy ? "legacy-ai" : current?.parent_slug ?? current?.slug;
  const needle = query.trim().toLocaleLowerCase();
  const matches = (topic: { name: string }) => topic.name.toLocaleLowerCase().includes(needle);
  const children = legacy ? topics : topics.filter(topic => topic.parent_slug === activeRoot);
  const results = needle ? topics.filter(matches) : children;

  return <section aria-label="Browse topics" className="overflow-hidden rounded-xl border border-[#262626] bg-[#0c0c0c]">
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#222] px-5 py-4">
      <h2 className="flex items-center gap-2 text-sm font-semibold"><Squares2X2Icon className="size-4 text-[#ccf200]" />Browse topics</h2>
      <label className="flex w-full items-center gap-2 rounded-md border border-[#262626] bg-[#090909] px-3 focus-within:border-[#ccf200] sm:w-64">
        <MagnifyingGlassIcon className="size-4 shrink-0 text-[#9a9a9a]" />
        <input aria-label="Find a topic" value={query} onChange={event => setQuery(event.target.value)} placeholder="Find a topic…" className="min-w-0 w-full bg-transparent py-2 text-sm outline-none" />
      </label>
    </div>
    <div className="grid md:grid-cols-[240px_1fr]">
      <nav aria-label="Categories" className="flex gap-1 overflow-x-auto border-b border-[#222] bg-[#090909] p-3 md:flex-col md:border-b-0 md:border-r">
        <Link href="/repositories" className="flex shrink-0 items-center gap-2 rounded-md px-3 py-3 text-sm text-[#9a9a9a] hover:bg-[#171717] hover:text-white">All repositories <span aria-hidden="true">↗</span></Link>
        {roots.map(root => <Link key={root.slug} href={legacy ? "/topics" : `/topics/${encodeURIComponent(root.slug)}`} prefetch={false}
          aria-current={activeRoot === root.slug ? "true" : undefined}
          className={`flex shrink-0 items-center justify-between gap-3 rounded-md px-3 py-3 text-sm transition-colors ${activeRoot === root.slug ? "bg-[#ccf200]/10 text-[#ccf200]" : "text-[#bbb] hover:bg-[#171717] hover:text-white"}`}>
          {root.name}<ChevronRightIcon className="size-3.5 shrink-0" />
        </Link>)}
      </nav>
      <div className="min-w-0 p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h3 className="text-sm text-[#9a9a9a]">{needle ? "Matching topics" : activeRoot ? "Subtopics" : "Explore a category"}</h3>
          {activeRoot && !legacy && !needle && <Link href={`/topics/${encodeURIComponent(activeRoot)}`} aria-current={selected === activeRoot ? "page" : undefined} className="text-xs text-[#ccf200]">All in {roots.find(root => root.slug === activeRoot)?.name} →</Link>}
        </div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(needle || activeRoot ? results : topics.filter(topic => !topic.parent_slug)).map(topic => <Link key={topic.slug} href={`/topics/${encodeURIComponent(topic.slug)}`} prefetch={false}
            aria-current={selected === topic.slug ? "page" : undefined}
            className={`group flex min-h-20 items-center justify-between gap-3 rounded-lg border px-4 py-3 transition-colors ${selected === topic.slug ? "border-[#ccf200]/50 bg-[#ccf200]/5" : "border-[#262626] bg-[#101010] hover:border-[#ccf200]/40 hover:bg-[#151515]"}`}>
            <span><span className="block text-sm font-medium group-hover:text-[#ccf200]">{topic.name}</span>
              {count(topic.repository_count) !== null && <span className="mt-1 block font-mono text-xs text-[#9a9a9a]">{count(topic.repository_count)} repositories</span>}</span>
            <ChevronRightIcon className="size-4 shrink-0 text-[#646464] group-hover:text-[#ccf200]" />
          </Link>)}
        </div>
        {!results.length && needle && <p role="status" className="py-8 text-sm text-[#9a9a9a]">No topics match “{query}”. <button onClick={() => setQuery("")} className="text-[#ccf200]">Clear search</button></p>}
        {!topics.length && <p className="py-4 text-sm text-[#9a9a9a]">Topics are unavailable. <Link href="/repositories" className="text-[#ccf200]">Browse repositories →</Link></p>}
      </div>
    </div>
  </section>;
}
