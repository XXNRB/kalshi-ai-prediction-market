"use client";

import { useEffect, useState } from "react";
import { getExitLog } from "@/lib/api";
import type { ExitDecisionLogEntry } from "@/lib/types";

const REFRESH_MS = 15000;

function plColor(n: number): string {
  return n > 0 ? "text-emerald-400" : n < 0 ? "text-rose-400" : "text-slate-400";
}

export default function ExitDecisionLog() {
  const [entries, setEntries] = useState<ExitDecisionLogEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    try {
      setEntries(await getExitLog(50));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load exit log.");
    }
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, REFRESH_MS);
    return () => clearInterval(id);
  }, []);

  return (
    <div>
      <h2 className="mb-1 text-lg font-semibold">Exit Decision Log</h2>
      <p className="mb-3 text-xs text-slate-500">
        Every exit-engine evaluation, whether or not it resulted in a sell — the audit trail behind
        both Recommend Only and Auto-Execute.
      </p>
      {error && <p className="mb-3 text-xs text-rose-400">{error}</p>}
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">No exit evaluations logged yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-xs">
            <thead className="bg-slate-900 text-left uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-3 py-2">Market</th>
                <th className="px-3 py-2">Time</th>
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2 text-right">Price</th>
                <th className="px-3 py-2 text-right">P&L</th>
                <th className="px-3 py-2">Mode</th>
                <th className="px-3 py-2">Result</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {entries.map((e) => {
                const pl = e.executed ? e.realized_profit_loss ?? 0 : e.unrealized_profit_loss;
                return (
                  <tr key={e.id}>
                    <td className="px-3 py-2">{e.ticker}</td>
                    <td className="px-3 py-2 text-slate-500">{new Date(e.timestamp).toLocaleTimeString()}</td>
                    <td className="px-3 py-2" title={e.summary}>
                      {e.action} · {e.confidence}% · {e.urgency}
                    </td>
                    <td className="px-3 py-2 text-right tabular-nums">
                      {(e.current_price * 100).toFixed(0)}¢
                    </td>
                    <td className={`px-3 py-2 text-right tabular-nums ${plColor(pl)}`}>
                      {pl >= 0 ? "+" : ""}${pl.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 text-slate-500">
                      {e.mode === "auto_execute" ? "Auto-Execute" : "Recommend Only"}
                    </td>
                    <td className="px-3 py-2">
                      {e.executed ? (
                        <span className="text-emerald-400">Executed @ {((e.execution_price ?? 0) * 100).toFixed(0)}¢</span>
                      ) : (
                        <span className="text-slate-500">Flagged</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
