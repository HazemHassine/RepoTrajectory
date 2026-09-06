import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { TopicPicker } from "@/components/topic-picker";
import { DiscoveryCard } from "@/components/discovery-card";
import { productApi } from "@/lib/product-api";
import { normalizeTopicQuery, topicHref } from "@/lib/topic-navigation";

export default async function TopicPage({ params, searchParams }: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const filters = normalizeTopicQuery(await searchParams);
  const [result, taxonomy] = await Promise.allSettled([productApi.topic(slug, filters), productApi.topics()]);
  if (result.status === "rejected") return <main>
    <PageHeader title="Topic unavailable" />
    <div className="mx-auto max-w-[1200px] space-y-4 px-5 py-8">
      <p role="alert" className="text-sm text-[#9a9a9a]">We couldn’t load this topic.</p>
      <Link href={topicHref(slug)} className="button-secondary">Try again</Link>{" "}<Link href="/topics" className="button-secondary">All topics</Link>
    </div>
  </main>;
  const detail = result.value;
  const paginated = detail.total_count !== undefined;
  const activeFilters = Boolean(filters.q || filters.language || filters.sort !== "relevance");
  return <main>
    <PageHeader title={detail.topic.name} action={<Link href="/repositories" className="button-secondary">All repositories ↗</Link>} />
    <div className="mx-auto max-w-[1200px] space-y-7 px-5 py-8">
      {taxonomy.status === "fulfilled" ? <TopicPicker key={slug} topics={taxonomy.value} selected={slug} /> : <Link href="/topics" className="text-sm text-[#ccf200]">All topics →</Link>}
      <section aria-label="Topic repositories" className="space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Repositories <span className="ml-2 font-mono text-sm font-normal text-[#9a9a9a]">{paginated ? detail.total_count!.toLocaleString("en-GB") : `${detail.projects.length} shown`}</span></h2>
          {activeFilters && paginated && <Link className="text-xs text-[#ccf200]" href={topicHref(slug)}>Clear filters ×</Link>}
        </div>
        {paginated && <form action={topicHref(slug)} className="grid items-end gap-3 rounded-lg border border-[#262626] bg-[#0c0c0c] p-4 sm:grid-cols-2 lg:grid-cols-[1fr_180px_180px_auto]">
          <label className="text-xs text-[#9a9a9a]">Search repositories
            <input name="q" type="search" maxLength={200} defaultValue={filters.q ?? ""} key={`q-${filters.q}`} placeholder="Name, description, keyword…" className="brutal-input mt-1.5 w-full px-3 py-2.5 text-sm" />
          </label>
          <label className="text-xs text-[#9a9a9a]">Language
            <select name="language" defaultValue={filters.language ?? ""} key={`language-${filters.language}`} className="brutal-input mt-1.5 w-full px-3 py-2.5 text-sm">
              <option value="">All languages</option>
              {filters.language && !detail.languages?.some(item => item.value === filters.language) && <option value={filters.language}>{filters.language}</option>}
              {detail.languages?.map(item => <option key={item.value} value={item.value}>{item.value} ({item.count.toLocaleString("en-GB")})</option>)}
            </select>
          </label>
          <label className="text-xs text-[#9a9a9a]">Sort by
            <select name="sort" defaultValue={filters.sort} key={`sort-${filters.sort}`} className="brutal-input mt-1.5 w-full px-3 py-2.5 text-sm">
              <option value="relevance">Relevance</option><option value="stars">Most stars</option><option value="updated">Recently updated</option>
            </select>
          </label>
          <button className="button-primary mb-0.5" type="submit">Apply</button>
        </form>}
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{detail.projects.map(project => <DiscoveryCard key={project.github_id} project={project} />)}</div>
        {!detail.projects.length && <div className="panel space-y-3 p-8 text-center">
          <h3 className="text-lg">No repositories found</h3>
          <Link className="text-sm text-[#ccf200]" href={activeFilters ? topicHref(slug) : "/repositories"}>{activeFilters ? "Clear filters" : "Browse all repositories"} →</Link>
        </div>}
        {paginated && <nav aria-label="Repository pages" className="flex items-center justify-between border-t border-[#222] pt-5">
          <span className="text-xs text-[#9a9a9a]">{detail.projects.length} on this page</span>
          <div className="flex gap-3">
            {filters.cursor && <Link className="button-secondary" href={topicHref(slug, { ...filters, cursor: undefined })}>First page</Link>}
            {detail.next_cursor && <Link className="button-primary" href={topicHref(slug, { ...filters, cursor: detail.next_cursor })}>Next page →</Link>}
          </div>
        </nav>}
      </section>
    </div>
  </main>;
}
