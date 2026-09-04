import { Suspense } from "react";

import { IngestionCommand } from "@/components/ingestion-command";
import { RepositoryDirectory } from "@/components/repository-directory";
import { EmptyState, PageHeader } from "@/components/ui";
import { api, type CatalogRepo, type CursorEnvelope, type Facets } from "@/lib/api";

interface SearchParamsProps {
  cursor?: string;
  lang?: string;
  lens?: string;
  sort?: string;
  order?: string;
  q?: string;
}

export default async function Repositories({
  searchParams,
}: {
  searchParams: Promise<SearchParamsProps>;
}) {
  const params = await searchParams;
  const cursor = params.cursor;
  const language = params.lang;
  const lens = params.lens || "developer";
  const sort = params.sort || "stars";
  const order = params.order || "desc";
  const search = params.q;

  let catalogResponse: CursorEnvelope<CatalogRepo> = {
    items: [],
    next_cursor: null,
    total_count: 0,
  };
  let facets: Facets = {
    languages: [],
    categories: [],
    licenses: [],
    evidence_levels: {},
    freshness_counts: {},
  };
  let unavailable = false;

  try {
    const [res, fac] = await Promise.all([
      api.v2.repositories({
        cursor,
        limit: 50,
        language,
        sort,
        order,
        search,
        lens,
      }),
      api.v2.facets(),
    ]);
    catalogResponse = res;
    facets = fac;
  } catch {
    // If v2 fails, try v1 fallback or mark unavailable
    try {
      const v1Repos = await api.repos();
      catalogResponse = {
        items: v1Repos.map((r, idx) => ({
          github_id: idx + 1,
          owner: r.owner,
          name: r.name,
          full_name: r.full_name,
          description: r.description,
          primary_language: r.primary_language,
          license: r.license,
          default_branch: r.default_branch,
          stars: r.stars,
          forks: r.forks,
          watchers: r.watchers,
          open_issues: r.open_issues,
          created_at: r.created_at,
          updated_at: r.updated_at,
          pushed_at: r.pushed_at,
          tier: "directory",
          is_directory: true,
          is_deep: false,
          classification: "general",
          classification_confidence: 0.8,
          topics: [] as string[],
          selection_score: 50,
          promise_score: null,
          scout_eligible: false,
        })),
        next_cursor: null,
        total_count: v1Repos.length,
      };
    } catch {
      unavailable = true;
    }
  }

  return (
    <main>
      <PageHeader
        title="Repositories"
        description="Directory of active open-source software repositories across ecosystems, indexed by technology, activity, and health."
        action={
          <div className="flex items-center gap-2">
            <IngestionCommand />
          </div>
        }
      />
      <div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10">
        {unavailable ? (
          <EmptyState
            title="Directory API unavailable"
            description="Start FastAPI on port 8000 to query the repository directory."
          />
        ) : (
          <Suspense fallback={<div className="panel p-12 text-center font-mono text-xs text-[#9a9a9a]">Loading directory...</div>}>
            <RepositoryDirectory
              records={catalogResponse.items}
              totalCount={catalogResponse.total_count}
              nextCursor={catalogResponse.next_cursor}
              facets={facets}
              currentFilters={params}
            />
          </Suspense>
        )}
      </div>
    </main>
  );
}
