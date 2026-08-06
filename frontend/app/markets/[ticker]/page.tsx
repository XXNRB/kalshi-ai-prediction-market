import Link from "next/link";
import MarketDetailLive from "@/components/MarketDetailLive";
import { getCachedAnalysis, getMarket, getMarketHistory } from "@/lib/api";

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const [market, history, analysis] = await Promise.all([
    getMarket(ticker),
    getMarketHistory(ticker),
    getCachedAnalysis(ticker),
  ]);

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
        ← Back to dashboard
      </Link>
      <MarketDetailLive
        ticker={ticker}
        initialMarket={market}
        initialHistory={history}
        initialAnalysis={analysis}
      />
    </div>
  );
}
