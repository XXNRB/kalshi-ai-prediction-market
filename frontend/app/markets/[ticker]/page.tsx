import Link from "next/link";
import AnalysisPanel from "@/components/AnalysisPanel";
import PriceChart from "@/components/PriceChart";
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

      <div>
        <h1 className="text-2xl font-semibold">{market.title}</h1>
        <p className="text-sm text-slate-500">
          {market.ticker} · {market.category ?? "Uncategorized"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
        <Stat label="YES" value={`${(market.yes_price * 100).toFixed(0)}¢`} />
        <Stat label="NO" value={`${(market.no_price * 100).toFixed(0)}¢`} />
        <Stat label="Volume" value={market.volume.toLocaleString()} />
        <Stat label="Open Interest" value={market.open_interest.toLocaleString()} />
        <Stat
          label="Expires"
          value={market.expiration_date ? new Date(market.expiration_date).toLocaleDateString() : "—"}
        />
      </div>

      <div className="rounded-lg border border-slate-800 p-5">
        <h2 className="mb-3 text-lg font-semibold">Price History</h2>
        <PriceChart history={history} />
      </div>

      <AnalysisPanel ticker={market.ticker} />
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-lg font-semibold">{value}</div>
    </div>
  );
}
