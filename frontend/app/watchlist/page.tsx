import { PageHeader } from "@/components/ui";
import { WatchlistWorkspace } from "@/components/watchlist-workspace";
export default function WatchlistPage() {
  return <main><PageHeader title="Your watchlist" description="Saved in this browser." />
    <div className="mx-auto max-w-[1100px] px-5 py-8"><WatchlistWorkspace /></div></main>;
}
