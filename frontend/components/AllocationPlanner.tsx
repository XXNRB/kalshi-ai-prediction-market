"use client";

import { useState } from "react";
import { buyPosition, runAllocation } from "@/lib/api";
import type { AllocationItem, AllocationResponse, BuyPosition } from "@/lib/types";

function parseTickers(raw: string): string[] {
  return Array.from(
    new Set(
      raw
        .split(/[\n,]/)
        .map((t) => t.trim())
        .filter(Boolean)
    )
  );
}

export default function AllocationPlanner({
  cashBalance,
  onTraded,
}: {
  cashBalance: number | null;
  onTraded: () => void;
}) {
  const [tickerInput, setTickerInput] = useState("");
  const [result, setResult] = useState<AllocationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buyingTicker, setBuyingTicker] = useState<string | null>(null);

  async function handleAnalyze() {
    const tickers = parseTickers(tickerInput);
    if (tickers.length === 0) {
      setError("Enter at least one ticker.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setResult(await runAllocation(tickers));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Allocation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleBuy(item: AllocationItem) {
    if (cashBalance === null) return;
    const position: BuyPosition = item.analysis.edge >= 0 ? "YES" : "NO";
    const amount = Math.round((item.final_allocation_pct / 100) * cashBalance * 100) / 100;
    if (amount <= 0) return;
    setBuyingTicker(item.ticker);
    setError(null);
    try {
      await buyPosition(item.ticker, position, amount);
      onTraded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Buy failed.");
    } finally {
      setBuyingTicker(null);
    }
  }

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <h2 className="mb-1 text-lg font-semibold">Allocation Planner</h2>
      <p className="mb-3 text-xs text-slate-500">
        Analyzes a batch of candidate markets together: markets below the conviction threshold
        (weak edge or low confidence) are skipped entirely, and their stake flows to the stronger
        picks instead of being spread evenly.
      </p>

      <textarea
        value={tickerInput}
        onChange={(e) => setTickerInput(e.target.value)}
        placeholder="Paste tickers, one per line or comma-separated"
        rows={3}
        className="mb-3 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm"
      />

      <button
        onClick={handleAnalyze}
        disabled={loading}
        className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {loading ? "Analyzing…" : result ? "Re-analyze & Allocate" : "Analyze & Allocate"}
      </button>

      {error && (
        <div className="mt-3 rounded-md border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}

      {result && result.errors.length > 0 && (
        <div className="mt-3 rounded-md border border-amber-800 bg-amber-950/30 px-3 py-2 text-xs text-amber-300">
          {result.errors.join(" · ")}
        </div>
      )}

      {result && result.items.length > 0 && (
        <div className="mt-4 overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-xs">
            <thead className="bg-slate-900 text-left uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Market</th>
                <th className="px-3 py-2">Recommendation</th>
                <th className="px-3 py-2 text-right">Edge</th>
                <th className="px-3 py-2 text-right">Confidence</th>
                <th className="px-3 py-2 text-right">Raw %</th>
                <th className="px-3 py-2 text-right">Final %</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {result.items.map((item) => (
                <tr key={item.ticker} className={item.skipped ? "opacity-50" : undefined}>
                  <td className="px-3 py-2">{item.market_title}</td>
                  <td className="px-3 py-2 text-slate-400">
                    {item.skipped ? item.skip_reason : item.analysis.recommendation}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{(item.analysis.edge * 100).toFixed(0)}pt</td>
                  <td className="px-3 py-2 text-right tabular-nums">{item.analysis.confidence}/10</td>
                  <td className="px-3 py-2 text-right tabular-nums">{item.raw_allocation_pct.toFixed(1)}%</td>
                  <td className="px-3 py-2 text-right tabular-nums font-medium">
                    {item.final_allocation_pct.toFixed(1)}%
                  </td>
                  <td className="px-3 py-2 text-right">
                    {!item.skipped && (
                      <button
                        onClick={() => handleBuy(item)}
                        disabled={buyingTicker === item.ticker || cashBalance === null}
                        className="rounded-md border border-slate-700 px-2 py-1 text-xs hover:border-slate-500 disabled:opacity-50"
                      >
                        {buyingTicker === item.ticker
                          ? "Buying…"
                          : cashBalance !== null
                            ? `Buy $${((item.final_allocation_pct / 100) * cashBalance).toFixed(0)}`
                            : "Buy"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
