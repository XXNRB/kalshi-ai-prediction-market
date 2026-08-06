import Link from "next/link";
import MarketDetailLive from "@/components/MarketDetailLive";
import { getMarket, getMarketHistory } from "@/lib/api";

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ ticker: string }>;
}) {
  const { ticker } = await params;
  const [market, history] = await Promise.all([getMarket(ticker), getMarketHistory(ticker)]);

  return (
    <div className="space-y-6">
      <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
        ← Back to dashboard
      </Link>
      <MarketDetailLive ticker={ticker} initialMarket={market} initialHistory={history} />
    </div>
  );
}
