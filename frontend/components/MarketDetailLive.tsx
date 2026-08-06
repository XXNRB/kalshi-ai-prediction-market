"use client";

import { useCallback, useEffect, useState } from "react";
import AnalysisPanel from "@/components/AnalysisPanel";
import OpportunityBreakdown from "@/components/OpportunityBreakdown";
import PriceChart from "@/components/PriceChart";
import SignalCallout from "@/components/SignalBadge";
import TradePanel from "@/components/TradePanel";
import YourPosition from "@/components/YourPosition";
import { getPortfolio } from "@/lib/api";
import { useLiveMarket } from "@/lib/useLiveMarket";
import type { Market, MarketAnalysis, PortfolioSummary, PricePoint } from "@/lib/types";

export default function MarketDetailLive({
  ticker,
  initialMarket,
  initialHistory,
  initialAnalysis,
}: {
  ticker: string;
  initialMarket: Market;
  initialHistory: PricePoint[];
  initialAnalysis: MarketAnalysis | null;
}) {
  const market = useLiveMarket(ticker, initialMarket);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);

  const refreshPortfolio = useCallback(() => {
    getPortfolio()
      .then(setPortfolio)
      .catch(() => {
        // portfolio is a bonus panel here — a failed fetch shouldn't break the page
      });
  }, []);

  useEffect(() => {
    refreshPortfolio();
  }, [refreshPortfolio]);

  const myOpenPositions = portfolio?.open_positions.filter((t) => t.ticker === ticker) ?? [];

  return (
    <div className="space-y-6">
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

      <OpportunityBreakdown opportunity={market.opportunity} />

      <SignalCallout signal={market.signal} />

      <YourPosition trades={myOpenPositions} onSold={refreshPortfolio} />

      <div className="rounded-lg border border-slate-800 p-5">
        <h2 className="mb-3 text-lg font-semibold">Price History</h2>
        <PriceChart ticker={ticker} initialHistory={initialHistory} />
      </div>

      <TradePanel
        market={market}
        cashBalance={portfolio?.cash_balance ?? null}
        onTraded={refreshPortfolio}
      />

      <AnalysisPanel
        ticker={ticker}
        currentYesPrice={market.yes_price}
        initialAnalysis={initialAnalysis}
      />
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
