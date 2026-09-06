import { CompareExplorer } from "@/components/compare-explorer";
import { PageHeader } from "@/components/ui";
import { api, type CatalogRepo } from "@/lib/api";
export default async function Compare({ searchParams }: { searchParams: Promise<{ a?: string; b?: string }> }) {
  const query = await searchParams;
  let repos: CatalogRepo[] = [];
  let unavailable = false;
  try { repos = (await api.v2.repositories({ limit: 100 })).items; }
  catch { unavailable = true; }
  return <main><PageHeader title="Compare repositories" />
    <div className="mx-auto max-w-[1200px] space-y-4 px-5 py-8">
      {unavailable && <p role="alert">Catalog suggestions are unavailable. You can enter owner/repository and retry.</p>}
      <CompareExplorer repositories={repos} initialA={query.a} initialB={query.b} />
    </div></main>;
}
