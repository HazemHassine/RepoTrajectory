import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { TopicPicker } from "@/components/topic-picker";
import { DiscoveryCard } from "@/components/discovery-card";
import { api } from "@/lib/api";
import { productApi } from "@/lib/product-api";

export default async function TopicsPage() {
  const [topics, catalog] = await Promise.allSettled([productApi.topics(), api.v2.repositories({ limit: 12, sort: "stars" })]);
  return <main><PageHeader title="Explore topics" action={<Link href="/repositories" className="button-secondary">All repositories ↗</Link>} />
    <div className="mx-auto max-w-[1200px] space-y-8 px-5 py-8">
      {topics.status === "fulfilled" ? <TopicPicker topics={topics.value} /> : <p role="alert" className="panel p-5">Topics are unavailable. <Link className="text-[#ccf200]" href="/topics">Try again</Link></p>}
      <section className="space-y-4"><h2 className="text-lg font-semibold">Popular repositories</h2>
        {catalog.status === "fulfilled" ? <>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{catalog.value.items.map(project => <DiscoveryCard key={project.github_id} project={project} />)}</div>
          {!catalog.value.items.length && <p className="text-sm text-[#9a9a9a]">No repositories yet.</p>}
        </> : <p role="alert" className="text-sm text-[#9a9a9a]">Repositories are temporarily unavailable.</p>}
      </section>
    </div>
  </main>;
}
