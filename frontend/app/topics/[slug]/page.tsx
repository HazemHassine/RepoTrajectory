import Link from "next/link";
import { PageHeader } from "@/components/ui";
import { ChangeList } from "@/components/project-brief";
import { productApi } from "@/lib/product-api";
export default async function TopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  let detail;
  try { detail = await productApi.topic(slug); } catch {
    return <main><PageHeader title="Topic unavailable" description="This topic was not found or the API is unavailable. Return to Topics or reload." /></main>;
  }
  return <main><PageHeader title={detail.topic.name} description={detail.topic.description} />
    <div className="mx-auto max-w-[1200px] space-y-6 px-5 py-8">
      <p className="text-sm text-[#9a9a9a]">Up to {detail.limit} matching projects, ordered by recent push. Membership indicates relevance, not a maturity or quality judgment.</p>
      <section className="panel p-5"><h2 className="mb-4 text-lg font-semibold">Recent changes in this collection</h2><ChangeList items={detail.changes} /></section>
      <div className="grid gap-4 md:grid-cols-2">{detail.projects.map(project => <article className="panel space-y-3 p-5" key={project.github_id}>
        <Link className="font-semibold text-[#ccf200]" href={`/repositories/${project.full_name}`}>{project.full_name} →</Link>
        <p className="text-sm">{project.description ?? "Description unavailable."}</p>
        <p className="text-xs text-[#9a9a9a]">{project.primary_language ?? "Language unknown"} · matched: {project.matched_terms.join(", ")}</p>
        <Link className="text-sm underline" href={`/compare?a=${encodeURIComponent(project.full_name)}`}>Compare alternatives</Link>
      </article>)}</div>
      {!detail.projects.length && <p>No collected projects match these rules yet. Collection grows as the background worker runs.</p>}
      <details className="panel p-4"><summary>Collection rules</summary><p className="mt-3 text-sm">{detail.topic.terms.join(", ")}</p></details>
    </div></main>;
}
