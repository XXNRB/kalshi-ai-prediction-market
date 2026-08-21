"use client";

import { useState } from "react";
import { sellPosition } from "@/lib/api";
import PositionStatsRow from "@/components/PositionStatsRow";
import type { Trade } from "@/lib/types";

export default function YourPosition({
  trades,
  onSold,
}: {
  trades: Trade[];
  onSold: () => void;
}) {
  const [sellingId, setSellingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (trades.length === 0) return null;

  async function handleSell(tradeId: number) {
    setSellingId(tradeId);
    setError(null);
    try {
      await sellPosition(tradeId);
      onSold();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sell failed.");
    } finally {
      setSellingId(null);
    }
  }

  return (
    <div className="rounded-lg border border-emerald-800 bg-emerald-950/20 p-5">
      <h2 className="mb-3 text-lg font-semibold">Your Position{trades.length > 1 ? "s" : ""}</h2>
      <div className="space-y-3">
        {trades.map((t) => {
          const pl = t.profit_loss ?? 0;
          const metrics = t.metrics;
          return (
            <div key={t.id} className="space-y-1.5">
              <div className="flex items-center justify-between text-sm">
                <div>
                  <span className="font-medium">{t.position}</span> · {t.contracts.toFixed(2)} contracts
                  @ {(t.entry_price * 100).toFixed(0)}¢ (${t.amount.toFixed(2)} cost)
                  {t.current_price !== null && (
                    <span className="text-slate-400"> · now {(t.current_price * 100).toFixed(0)}¢</span>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  <span className={pl > 0 ? "text-emerald-400" : pl < 0 ? "text-rose-400" : "text-slate-400"}>
                    {pl >= 0 ? "+" : ""}${pl.toFixed(2)}
                  </span>
                  <button
                    onClick={() => handleSell(t.id)}
                    disabled={sellingId === t.id}
                    className="rounded-md border border-slate-700 px-3 py-1 text-xs hover:border-slate-500 disabled:opacity-50"
                  >
                    {sellingId === t.id ? "Selling…" : "Sell"}
                  </button>
                </div>
              </div>
              {metrics && <PositionStatsRow metrics={metrics} decision={t.exit_decision} game={t.mlb_game_state} />}
            </div>
          );
        })}
      </div>
      {error && <p className="mt-3 text-xs text-rose-400">{error}</p>}
    </div>
  );
}
