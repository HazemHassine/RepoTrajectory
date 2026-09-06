import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { TopicPicker } from "@/components/topic-picker";
import { DiscoveryCard } from "@/components/discovery-card";
import { api } from "@/lib/api";
import { productApi } from "@/lib/product-api";

export default async function Home() {
  const [catalog, topics] = await Promise.allSettled([
    api.v2.repositories({ limit: 12, sort: "stars" }), productApi.topics(),
  ]);
  return <main><PageHeader title="Find your next tool."
    action={<Link className="button-secondary" href="/watchlist">Your watchlist →</Link>} />
    <div className="mx-auto max-w-[1200px] space-y-8 px-5 py-8">
      <form action="/repositories" className="flex gap-3 rounded-xl border border-[#333] bg-[#0c0c0c] p-3">
        <input name="q" aria-label="Search repositories" placeholder="Search repositories, languages, ideas…" className="min-w-0 flex-1 rounded-md bg-transparent px-3 py-2 text-sm" required />
        <button className="button-primary" type="submit">Search</button>
      </form>
      {topics.status === "fulfilled" ? <TopicPicker topics={topics.value} /> : <p role="alert" className="text-sm text-[#9a9a9a]">Topics are temporarily unavailable. <Link href="/topics" className="text-[#ccf200]">Try again</Link></p>}
      <section className="space-y-4"><div className="flex items-center justify-between gap-4"><h2 className="text-xl font-semibold">Popular repositories</h2><Link href="/repositories" className="text-sm text-[#ccf200]">Browse all →</Link></div>
        {catalog.status === "fulfilled" ? <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{catalog.value.items.map(project => <DiscoveryCard key={project.github_id} project={project} />)}</div>
          {!catalog.value.items.length && <p className="panel p-5 text-sm text-[#9a9a9a]">No repositories yet.</p>}
        </> : <p role="alert" className="text-sm text-[#9a9a9a]">Repositories are temporarily unavailable. <Link href="/" className="text-[#ccf200]">Try again</Link></p>}
      </section>
    </div>
  </main>;
}
