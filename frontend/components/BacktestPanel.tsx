"use client";

import { useState } from "react";
import { runBacktest } from "@/lib/api";
import type { BacktestResult, StrategyResult } from "@/lib/types";

function plColor(n: number): string {
  return n > 0 ? "text-emerald-400" : n < 0 ? "text-rose-400" : "text-slate-400";
}

export default function BacktestPanel({ ticker }: { ticker: string }) {
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRun() {
    setLoading(true);
    setError(null);
    try {
      setResult(await runBacktest(ticker));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backtest failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Backtest</h2>
        <button
          onClick={handleRun}
          disabled={loading}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Running…" : result ? "Re-run Backtest" : "Run Backtest"}
        </button>
      </div>

      {!result && !error && !loading && (
        <p className="text-sm text-slate-500">
          Replays our rule-based entry/exit signal against this market&apos;s real historical
          prices, and compares it to simply buying and holding — &quot;would following our own
          signal have actually worked here?&quot; We can&apos;t backtest the AI analysis itself
          (it reflects research run today, not what was knowable at each past moment), only
          price-pattern strategies.
        </p>
      )}

      {error && (
        <div className="rounded-md border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-5 text-sm">
          <p className="text-xs text-slate-500">
            {result.candle_count} data points from {new Date(result.period_start).toLocaleDateString()}{" "}
            to {new Date(result.period_end).toLocaleDateString()}. Sharpe ratio below is
            unannualized (per data point in this market&apos;s history) — not comparable across
            markets with different candle resolutions.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <StrategyCard strategy={result.signal_strategy} />
            <StrategyCard strategy={result.buy_hold_strategy} />
          </div>

          {result.signal_strategy.trades.length > 0 && (
            <div>
              <h3 className="mb-2 font-medium text-slate-300">Signal-Based Trade Log</h3>
              <div className="overflow-x-auto rounded-lg border border-slate-800">
                <table className="w-full text-xs">
                  <thead className="bg-slate-900 text-left uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-3 py-2">Entry</th>
                      <th className="px-3 py-2">Exit</th>
                      <th className="px-3 py-2 text-right">P&L</th>
                      <th className="px-3 py-2">Reason</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {result.signal_strategy.trades.map((t, i) => (
                      <tr key={i}>
                        <td className="px-3 py-2 tabular-nums">
                          {(t.entry_price * 100).toFixed(0)}¢ ({new Date(t.entry_time).toLocaleDateString()})
                        </td>
                        <td className="px-3 py-2 tabular-nums">
                          {(t.exit_price * 100).toFixed(0)}¢ ({new Date(t.exit_time).toLocaleDateString()})
                        </td>
                        <td className={`px-3 py-2 text-right tabular-nums ${plColor(t.profit_loss)}`}>
                          {t.profit_loss >= 0 ? "+" : ""}${t.profit_loss.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-slate-500">
                          {t.exit_reason === "exit_signal" ? "Exit signal" : "End of window"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function StrategyCard({ strategy }: { strategy: StrategyResult }) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <h3 className="mb-3 font-medium">{strategy.strategy}</h3>
      <div className="grid grid-cols-2 gap-3">
        <Stat
          label="Total Return"
          value={`${strategy.total_return_pct >= 0 ? "+" : ""}${strategy.total_return_pct.toFixed(1)}%`}
          accent={plColor(strategy.total_return_pct)}
        />
        <Stat
          label="Win Rate"
          value={strategy.win_rate_pct === null ? "—" : `${strategy.win_rate_pct.toFixed(0)}%`}
        />
        <Stat label="Max Drawdown" value={`${strategy.max_drawdown_pct.toFixed(1)}%`} />
        <Stat label="Sharpe (unann.)" value={strategy.sharpe_ratio.toFixed(2)} />
      </div>
      <p className="mt-3 text-xs text-slate-500">
        {strategy.trade_count} trade{strategy.trade_count === 1 ? "" : "s"} · ${strategy.starting_balance.toFixed(0)} →{" "}
        ${strategy.ending_balance.toFixed(2)}
      </p>
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`font-semibold ${accent ?? ""}`}>{value}</div>
    </div>
  );
}
