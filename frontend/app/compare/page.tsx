import { CompareExplorer } from "@/components/compare-explorer";
import { PageHeader } from "@/components/ui";
import { api } from "@/lib/api";

export default async function Compare({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const query = await searchParams;
  let repos: any[] = [];
  try {
    const v2Res = await api.v2.repositories({ limit: 100 });
    if (v2Res.items && v2Res.items.length > 0) {
      repos = v2Res.items;
    } else {
      repos = await api.repos();
    }
  } catch {
    try {
      repos = await api.repos();
    } catch {}
  }

  return (
    <main>
      <PageHeader
        title="Repository Comparison"
        description="Side-by-side comparative analysis of activity velocity, commit resilience, and community health."
      />
      <div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10">
        <CompareExplorer
          repositories={repos}
          initialA={query.a}
          initialB={query.b}
        />
      </div>
    </main>
  );
}
