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
  let retrievalMode: string | null = null;

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
    if (search) {
      const result = await api.v2.search(search, { language }, cursor, 50);
      catalogResponse = { items: result.items, total_count: result.total_count, next_cursor: result.next_cursor };
      retrievalMode = result.result_rationale;
    }
  } catch {
    unavailable = true;
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
        {retrievalMode && <p className="mb-4 text-xs text-[#9a9a9a]">{retrievalMode}</p>}
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
