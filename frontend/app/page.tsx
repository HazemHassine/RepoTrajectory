import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";
import { productApi } from "@/lib/product-api";
export default async function Home() {
  const [catalog, topics] = await Promise.allSettled([
    api.v2.repositories({ limit: 8, sort: "pushed" }), productApi.topics(),
  ]);
  return <main><PageHeader eyebrow="Discover → Understand → Compare → Decide → Watch"
    title="What should you investigate today?"
    description="Find useful open-source tools, check whether they fit your project, and come back when the evidence changes."
    action={<Link className="button-primary" href="/watchlist">Revisit my watchlist →</Link>} />
    <div className="mx-auto max-w-[1200px] space-y-8 px-5 py-8">
      <form action="/repositories" className="panel flex gap-3 p-4">
        <input name="q" aria-label="Find tools by purpose" placeholder="Search tools by name, topic or purpose…" className="input min-w-0 flex-1 bg-[#111]" required />
        <button className="button-primary">Discover tools</button>
      </form>
      <section><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-semibold">Start with what you are building</h2><Link href="/topics" className="text-sm text-[#ccf200]">All topics →</Link></div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{topics.status === "fulfilled" ? topics.value.map(topic => <Link href={`/topics/${topic.slug}`} key={topic.slug} className="panel space-y-2 p-4 hover:border-[#ccf200]">
          <h3 className="font-semibold">{topic.name}</h3><p className="text-xs text-[#9a9a9a]">{topic.description}</p>
        </Link>) : <p role="alert">Topics are temporarily unavailable.</p>}</div>
      </section>
      <section><div className="mb-4 flex items-center justify-between"><h2 className="text-xl font-semibold">Recently active tools to investigate</h2><Link href="/scout" className="text-sm text-[#ccf200]">Explore Scout →</Link></div>
        <p className="mb-4 text-sm text-[#9a9a9a]">A recent push is an investigation prompt. Open the brief to check releases, packages, source freshness and missing evidence.</p>
        <div className="grid gap-4 md:grid-cols-2">{catalog.status === "fulfilled" ? catalog.value.items.map(repo => <article key={repo.github_id} className="panel space-y-3 p-5">
          <Link className="font-semibold text-[#ccf200]" href={`/repositories/${repo.full_name}`}>{repo.full_name} →</Link>
          <p className="text-sm">{repo.description ?? "No project description collected."}</p>
          <p className="text-xs text-[#9a9a9a]">{repo.primary_language ?? "Language unknown"} · {repo.license ?? "License unknown"}</p>
          <Link className="text-sm underline" href={`/compare?a=${encodeURIComponent(repo.full_name)}`}>Compare for my project</Link>
        </article>) : <p role="alert">The catalog is unavailable. Reload to retry.</p>}</div>
        {catalog.status === "fulfilled" && !catalog.value.items.length && <p className="panel p-5">The catalog is waiting for collection. The operator can add a project from Admin.</p>}
      </section>
      <p className="text-sm text-[#9a9a9a]">No global quality score. Attention, package downloads, maintenance and discussion answer different questions. <Link className="underline" href="/methodology">Inspect the methodology.</Link></p>
    </div></main>;
}
