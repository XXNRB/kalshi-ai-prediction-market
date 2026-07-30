import Link from "next/link";
import type { Market, MarketSort } from "@/lib/types";

const SORT_OPTIONS: { value: MarketSort; label: string }[] = [
  { value: "volume", label: "Highest Volume" },
  { value: "movers", label: "Biggest Movers" },
  { value: "expiration", label: "Closest Expiration" },
  { value: "prob_change", label: "Largest Probability Change" },
];

function formatExpiration(date: string | null): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export default function MarketTable({
  markets,
  activeSort,
}: {
  markets: Market[];
  activeSort: MarketSort;
}) {
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        {SORT_OPTIONS.map((opt) => (
          <Link
            key={opt.value}
            href={`/?sort_by=${opt.value}`}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              activeSort === opt.value
                ? "border-emerald-500 bg-emerald-500/10 text-emerald-400"
                : "border-slate-700 text-slate-400 hover:border-slate-500"
            }`}
          >
            {opt.label}
          </Link>
        ))}
      </div>

      {markets.length === 0 ? (
        <p className="text-sm text-slate-500">
          No markets ingested yet. The backend polls Kalshi on startup — refresh in a moment.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900 text-left text-xs uppercase tracking-wide text-slate-500">
              <tr>
                <th className="px-4 py-3">Market</th>
                <th className="px-4 py-3">Category</th>
                <th className="px-4 py-3 text-right">YES</th>
                <th className="px-4 py-3 text-right">NO</th>
                <th className="px-4 py-3 text-right">24h Δ</th>
                <th className="px-4 py-3 text-right">Volume</th>
                <th className="px-4 py-3 text-right">Open Interest</th>
                <th className="px-4 py-3 text-right">Expires</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {markets.map((m) => (
                <tr key={m.ticker} className="hover:bg-slate-900/60">
                  <td className="px-4 py-3">
                    <Link href={`/markets/${m.ticker}`} className="font-medium hover:text-emerald-400">
                      {m.title}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{m.category ?? "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{(m.yes_price * 100).toFixed(0)}¢</td>
                  <td className="px-4 py-3 text-right tabular-nums">{(m.no_price * 100).toFixed(0)}¢</td>
                  <td
                    className={`px-4 py-3 text-right tabular-nums ${
                      m.price_change_24h > 0
                        ? "text-emerald-400"
                        : m.price_change_24h < 0
                          ? "text-rose-400"
                          : "text-slate-500"
                    }`}
                  >
                    {m.price_change_24h >= 0 ? "+" : ""}
                    {(m.price_change_24h * 100).toFixed(1)}¢
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums">{m.volume.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right tabular-nums">{m.open_interest.toLocaleString()}</td>
                  <td className="px-4 py-3 text-right text-slate-400">{formatExpiration(m.expiration_date)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
