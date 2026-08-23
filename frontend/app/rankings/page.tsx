import { RankingWorkspace } from "@/components/ranking-workspace";
import { EmptyState, PageHeader, WindowControl } from "@/components/ui";
import { api, mergeRepositories, type RepositoryRecord } from "@/lib/api";

export default async function Rankings({ searchParams }: { searchParams: Promise<{ window?: string }> }) {
  const requested = Number((await searchParams).window ?? 30);
  const window = [30, 90, 365].includes(requested) ? requested : 30;
  let records: RepositoryRecord[] = [];
  let unavailable = false;
  try { const [repositories, metrics] = await Promise.all([api.repos(), api.rankings("momentum", window)]); records = mergeRepositories(repositories, metrics); } catch { unavailable = true; }
  return <main><PageHeader eyebrow="Cross-repository analysis" title="Rankings" description="Rank by normalized signals rather than popularity. Every placement carries its evidence volume and confidence." action={<WindowControl active={window} />} /><div className="mx-auto max-w-[1440px] px-5 py-6 md:px-8 xl:px-10">{unavailable ? <EmptyState title="The API is not available" /> : records.length ? <RankingWorkspace records={records} /> : <EmptyState />}</div></main>;
}
