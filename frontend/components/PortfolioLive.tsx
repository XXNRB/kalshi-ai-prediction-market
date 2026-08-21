"use client";

import { Fragment, useEffect, useState } from "react";
import Link from "next/link";
import { getPortfolio, sellPosition } from "@/lib/api";
import AllocationPlanner from "@/components/AllocationPlanner";
import ExitDecisionLog from "@/components/ExitDecisionLog";
import ExitModeToggle from "@/components/ExitModeToggle";
import PositionStatsRow from "@/components/PositionStatsRow";
import type { PortfolioSummary, Trade } from "@/lib/types";

const REFRESH_MS = 15000;

function fmtMoney(n: number): string {
  return `${n < 0 ? "-" : ""}$${Math.abs(n).toFixed(2)}`;
}

function plColor(n: number): string {
  return n > 0 ? "text-emerald-400" : n < 0 ? "text-rose-400" : "text-slate-400";
}

export default function PortfolioLive({ initialSummary }: { initialSummary: PortfolioSummary }) {
  const [summary, setSummary] = useState(initialSummary);
  const [sellingId, setSellingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setSummary(await getPortfolio());
    } catch {
      // transient fetch failure — keep showing the last known summary
    }
  }

  useEffect(() => {
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  async function handleSell(trade: Trade) {
    setSellingId(trade.id);
    setError(null);
    try {
      await sellPosition(trade.id);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sell failed.");
    } finally {
      setSellingId(null);
    }
  }

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 rounded-lg border border-slate-800 p-5 sm:grid-cols-5">
        <Stat label="Starting" value={fmtMoney(summary.starting_balance)} />
        <Stat
          label="Current Value"
          value={fmtMoney(summary.portfolio_value)}
          accent={plColor(summary.total_pl)}
        />
        <Stat
          label="Total P&L"
          value={`${summary.total_pl >= 0 ? "+" : ""}${fmtMoney(summary.total_pl)}`}
          accent={plColor(summary.total_pl)}
        />
        <Stat
          label="ROI"
          value={`${summary.roi_pct >= 0 ? "+" : ""}${summary.roi_pct.toFixed(1)}%`}
          accent={plColor(summary.roi_pct)}
        />
        <Stat
          label="Win Rate"
          value={summary.win_rate_pct === null ? "—" : `${summary.win_rate_pct.toFixed(0)}%`}
        />
      </div>

      {error && (
        <div className="rounded-md border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}

      <ExitModeToggle />

      <AllocationPlanner cashBalance={summary.cash_balance} onTraded={refresh} />

      <div>
        <h2 className="mb-3 text-lg font-semibold">Open Positions</h2>
        {summary.open_positions.length === 0 ? (
          <p className="text-sm text-slate-500">
            No open positions. Buy YES or NO on a market&apos;s page to get started.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Market</th>
                  <th className="px-4 py-3">Side</th>
                  <th className="px-4 py-3 text-right">Entry</th>
                  <th className="px-4 py-3 text-right">Current</th>
                  <th className="px-4 py-3 text-right">Cost</th>
                  <th className="px-4 py-3 text-right">Unrealized P&L</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {summary.open_positions.map((t) => (
                  <Fragment key={t.id}>
                    <tr className="hover:bg-slate-900/60">
                      <td className="px-4 py-3">
                        <Link href={`/markets/${t.ticker}`} className="font-medium hover:text-emerald-400">
                          {t.market_title}
                        </Link>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{t.position}</td>
                      <td className="px-4 py-3 text-right tabular-nums">{(t.entry_price * 100).toFixed(0)}¢</td>
                      <td className="px-4 py-3 text-right tabular-nums">
                        {t.current_price !== null ? `${(t.current_price * 100).toFixed(0)}¢` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right tabular-nums">{fmtMoney(t.amount)}</td>
                      <td className={`px-4 py-3 text-right tabular-nums ${plColor(t.profit_loss ?? 0)}`}>
                        {t.profit_loss !== null
                          ? `${t.profit_loss >= 0 ? "+" : ""}${fmtMoney(t.profit_loss)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={() => handleSell(t)}
                          disabled={sellingId === t.id}
                          className="rounded-md border border-slate-700 px-3 py-1 text-xs hover:border-slate-500 disabled:opacity-50"
                        >
                          {sellingId === t.id ? "Selling…" : "Sell"}
                        </button>
                      </td>
                    </tr>
                    {t.metrics && (
                      <tr className="bg-slate-950/40">
                        <td colSpan={7} className="px-4 pb-3">
                          <PositionStatsRow metrics={t.metrics} decision={t.exit_decision} game={t.mlb_game_state} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-lg font-semibold">Closed Trades</h2>
        {summary.closed_trades.length === 0 ? (
          <p className="text-sm text-slate-500">No closed trades yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-4 py-3">Market</th>
                  <th className="px-4 py-3">Side</th>
                  <th className="px-4 py-3 text-right">Entry → Exit</th>
                  <th className="px-4 py-3 text-right">P&L</th>
                  <th className="px-4 py-3 text-right">Closed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {summary.closed_trades.map((t) => (
                  <tr key={t.id}>
                    <td className="px-4 py-3">
                      <Link href={`/markets/${t.ticker}`} className="font-medium hover:text-emerald-400">
                        {t.market_title}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-slate-400">{t.position}</td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {(t.entry_price * 100).toFixed(0)}¢ → {t.exit_price !== null ? `${(t.exit_price * 100).toFixed(0)}¢` : "—"}
                    </td>
                    <td className={`px-4 py-3 text-right tabular-nums ${plColor(t.profit_loss ?? 0)}`}>
                      {t.profit_loss !== null
                        ? `${t.profit_loss >= 0 ? "+" : ""}${fmtMoney(t.profit_loss)}`
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-right text-slate-500">
                      {t.exit_timestamp ? new Date(t.exit_timestamp).toLocaleString() : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ExitDecisionLog />
    </div>
  );
}

function Stat({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`text-lg font-semibold ${accent ?? ""}`}>{value}</div>
    </div>
  );
}
