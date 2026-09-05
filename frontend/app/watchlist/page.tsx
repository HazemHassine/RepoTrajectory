import { PageHeader } from "@/components/ui";
import { WatchlistWorkspace } from "@/components/watchlist-workspace";
export default function WatchlistPage() {
  return <main><PageHeader title="Your technology watchlist" description="Revisit why you were interested, what held you back, and what changed. Stored only in this browser." />
    <div className="mx-auto max-w-[1100px] px-5 py-8"><WatchlistWorkspace /></div></main>;
}
