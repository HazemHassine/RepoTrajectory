import { Suspense } from "react";

import { ScoutFeed } from "@/components/scout-feed";
import { EmptyState, PageHeader } from "@/components/ui";
import { api, type CursorEnvelope, type Facets, type ScoutFeedItem } from "@/lib/api";

interface ScoutPageProps {
  searchParams: Promise<{
    cursor?: string;
    lang?: string;
    min_score?: string;
    category?: string;
  }>;
}

export default async function ScoutPage({ searchParams }: ScoutPageProps) {
  const params = await searchParams;
  const cursor = params.cursor;
  const language = params.lang;
  const minScore = params.min_score ? Number(params.min_score) : 60;

  let scoutResponse: CursorEnvelope<ScoutFeedItem> = {
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
      api.v2.scout({
        cursor,
        limit: 50,
        language,
        min_promise_score: minScore,
      }),
      api.v2.facets(),
    ]);
    scoutResponse = res;
    facets = fac;
  } catch {
    unavailable = true;
  }

  return (
    <main>
      <PageHeader
        title="Scout Feed"
        description="Identification of promising repositories based on activity velocity, commit cadence, and maintainer engagement."
      />
      <div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10">
        {unavailable ? (
          <EmptyState
            title="Scout feed unavailable"
            description="Start FastAPI on port 8000 to stream AI Scout evaluations."
          />
        ) : (
          <Suspense fallback={<div className="panel p-12 text-center font-mono text-xs text-[#9a9a9a]">Loading Scout feed...</div>}>
            <ScoutFeed
              items={scoutResponse.items}
              totalCount={scoutResponse.total_count}
              nextCursor={scoutResponse.next_cursor}
              facets={facets}
              currentFilters={{
                cursor,
                lang: language,
                min_score: String(minScore),
              }}
            />
          </Suspense>
        )}
      </div>
    </main>
  );
}
