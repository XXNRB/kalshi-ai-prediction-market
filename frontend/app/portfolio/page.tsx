import PortfolioLive from "@/components/PortfolioLive";
import { getPortfolio } from "@/lib/api";

export default async function PortfolioPage() {
  let initialSummary;
  let error: string | null = null;
  try {
    initialSummary = await getPortfolio();
  } catch (e) {
    error = e instanceof Error ? e.message : "Failed to load portfolio.";
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Paper Trading Portfolio</h1>
        <p className="text-sm text-slate-500">
          Simulated positions only — no real money moves here.
        </p>
      </div>

      {error || !initialSummary ? (
        <div className="rounded-lg border border-rose-800 bg-rose-950/40 px-4 py-3 text-sm text-rose-300">
          Couldn&apos;t reach the backend API ({error}).
        </div>
      ) : (
        <PortfolioLive initialSummary={initialSummary} />
      )}
    </div>
  );
}
