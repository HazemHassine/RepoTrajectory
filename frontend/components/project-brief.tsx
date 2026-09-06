import Link from "next/link";
import type { Brief, Change, Evidence, Fact } from "@/lib/product-api";
import { safeSourceUrl } from "@/lib/watchlist";
import { WatchButton } from "./watch-button";

export function SourceAnchor({ url, children }: { url: string | null; children: React.ReactNode }) {
  const safe = safeSourceUrl(url);
  return safe ? <a className="text-[#ccf200] underline underline-offset-4" href={safe} target="_blank" rel="noreferrer">{children} ↗</a> : <span>{children}</span>;
}

export function FactValue({ fact }: { fact: Fact }) {
  return <div className="space-y-1">
    <p className="text-xs text-[#9a9a9a]">{fact.label}</p>
    <p>{fact.value ?? "Unknown"}</p>
    {fact.source_url && <p className="text-xs"><SourceAnchor url={fact.source_url}>{fact.basis} evidence</SourceAnchor>
      {fact.observed_at && <span className="text-[#9a9a9a]"> · observed {new Date(fact.observed_at).toLocaleDateString("en-GB")}</span>}</p>}
  </div>;
}

export function ChangeList({ items }: { items: Change[] }) {
  return <div className="space-y-3">{items.length ? items.map(item => <article key={item.id} className="border-l border-[#333] pl-3">
    <SourceAnchor url={item.source_url}>{item.title}</SourceAnchor>
    <p className="mt-1 text-xs text-[#9a9a9a]">{item.kind.replaceAll("_", " ").toLowerCase()} · {new Date(item.occurred_at).toLocaleDateString("en-GB")}</p>
  </article>) : <p className="text-sm text-[#9a9a9a]">No changes recorded in this window. Source coverage may be incomplete.</p>}</div>;
}

export function EvidenceList({ items }: { items: Evidence[] }) {
  return <div className="space-y-4">{items.length ? items.map(item => <article key={item.id} className="border-l border-[#333] pl-3">
    <p className="text-xs text-[#9a9a9a]">{item.source} · {item.kind} · {item.author ?? "Source record"} · {item.published_at ? new Date(item.published_at).toLocaleDateString("en-GB") : "Publication date unknown"}</p>
    <SourceAnchor url={item.url}>{item.title}</SourceAnchor>
    {item.excerpt && <p className="mt-1 text-sm text-[#bbb]">{item.excerpt}</p>}
    {item.source === "hacker_news" && <p className="text-xs text-[#9a9a9a]">Attributed submission; claims have not been independently verified.</p>}
    {item.kind === "vulnerability" && <p className="text-xs text-[#9a9a9a]">
      Checked: {String(item.details.package ?? "Unknown")} {String(item.details.version ?? "")}.
      Advisory fixed versions: {Array.isArray(item.details.fixed_versions) && item.details.fixed_versions.length ? item.details.fixed_versions.join(", ") : "Unknown"}.
    </p>}
    <p className="text-xs text-[#646464]">Observed {new Date(item.observed_at).toLocaleDateString("en-GB")}</p>
  </article>) : <p className="text-sm text-[#9a9a9a]">No sources collected yet.</p>}</div>;
}

export function ProjectBrief({ brief }: { brief: Brief }) {
  return <section className="space-y-6" aria-label="Developer project brief">
    <div className="flex flex-wrap items-start justify-between gap-4">
      <h2 className="text-2xl font-bold">Overview</h2>
      <WatchButton githubId={brief.github_id} fullName={brief.full_name} />
    </div>
    <div className="grid gap-4 lg:grid-cols-2">
      <article className="panel space-y-4 p-5"><h3 className="text-lg font-semibold">About</h3>
        <FactValue fact={brief.description} />
        {brief.readme_excerpt.value && <details><summary className="cursor-pointer text-sm text-[#ccf200]">README</summary>
          <div className="mt-3 whitespace-pre-wrap text-sm"><FactValue fact={brief.readme_excerpt} /></div></details>}
      </article>
      <article className="panel space-y-4 p-5"><h3 className="text-lg font-semibold">Get started</h3>
        <SourceAnchor url={`https://github.com/${brief.full_name}#readme`}>Project getting-started documentation</SourceAnchor>
        {brief.external_sources.links.map(link => <p key={link.source + link.external_id}>
          <SourceAnchor url={link.canonical_url}>{link.source}: {link.external_id}</SourceAnchor>
          <span className="block text-xs text-[#9a9a9a]">{link.verification} via package repository identity</span></p>)}
        <Link className="button-secondary" href={`/compare?a=${encodeURIComponent(brief.full_name)}`}>Compare</Link>
      </article>
    </div>
    <div className="panel grid gap-5 p-5 sm:grid-cols-2 lg:grid-cols-3">
      {brief.facts.map((fact, i) => <FactValue key={i} fact={fact} />)}
    </div>
    <div className="grid gap-4 lg:grid-cols-2">
      <article className="panel p-5"><h3 className="mb-4 text-lg font-semibold">What changed</h3><ChangeList items={brief.changes} /></article>
      <article className="panel p-5"><h3 className="mb-4 text-lg font-semibold">Unknowns</h3>
        <ul className="space-y-3 text-sm text-[#bbb]">{brief.missing.map((item, i) => <li key={i}>{item}</li>)}</ul></article>
    </div>
    <details className="panel p-5"><summary className="cursor-pointer text-lg font-semibold">Sources ({brief.evidence.length})</summary>
      <div className="mt-5"><EvidenceList items={brief.evidence} /></div></details>
    <details className="panel p-5"><summary className="cursor-pointer text-sm">Source details</summary>
      <div className="mt-4 space-y-3 text-sm">{brief.external_sources.sources.length ? brief.external_sources.sources.map(source => <div key={source.source + source.external_id}>
        <b>{source.source} · {source.external_id} · {source.status}</b>
        <p className="text-[#9a9a9a]">Last success: {source.last_success_at ? new Date(source.last_success_at).toLocaleString("en-GB") : "Never collected"}{source.last_error ? ` · ${source.last_error}` : ""}</p>
      </div>) : <p>Additional sources haven’t been collected yet.</p>}</div>
    </details>
  </section>;
}
