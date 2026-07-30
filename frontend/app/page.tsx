import MarketTable from "@/components/MarketTable";
import { listMarkets } from "@/lib/api";
import type { MarketSort } from "@/lib/types";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ sort_by?: string }>;
}) {
  const { sort_by } = await searchParams;
  const sortBy = (sort_by as MarketSort) ?? "volume";

  let markets: Awaited<ReturnType<typeof listMarkets>> = [];
  let error: string | null = null;
  try {
    markets = await listMarkets(sortBy);
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load markets from the backend.";
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold">Market Dashboard</h1>
      <p className="mb-6 text-sm text-slate-500">
        Live Kalshi markets ingested by the backend. Select a market to view price history and
        generate an AI research analysis.
      </p>

      {error ? (
        <div className="rounded-lg border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-300">
          Couldn&apos;t reach the backend API ({error}). Make sure the FastAPI server is running
          at the URL configured in <code>NEXT_PUBLIC_API_URL</code>.
        </div>
      ) : (
        <MarketTable markets={markets} activeSort={sortBy} />
      )}
    </div>
  );
}
