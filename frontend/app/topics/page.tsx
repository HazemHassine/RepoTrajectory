import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { productApi } from "@/lib/product-api";
export default async function TopicsPage() {
  let topics;
  try { topics = await productApi.topics(); } catch {
    return <main><PageHeader title="Technology topics" description="Topic data is unavailable. Please reload to try again." /></main>;
  }
  return <main><PageHeader title="Technology radar" description="Explore tools for your next system. Collections follow project topics and descriptions, with explicit matching rules." />
    <div className="mx-auto grid max-w-[1200px] gap-4 px-5 py-8 md:grid-cols-2">
      {topics.map(topic => <Link href={`/topics/${topic.slug}`} key={topic.slug} className="panel space-y-3 p-6 hover:border-[#ccf200]">
        <h2 className="text-xl font-semibold">{topic.name} →</h2><p className="text-sm text-[#9a9a9a]">{topic.description}</p>
      </Link>)}
      {!topics.length && <p>No topic rules configured.</p>}
    </div></main>;
}
