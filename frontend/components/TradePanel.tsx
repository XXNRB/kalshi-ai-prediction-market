"use client";

import { useState } from "react";
import Link from "next/link";
import { buyPosition } from "@/lib/api";
import type { BuyPosition, Market } from "@/lib/types";

export default function TradePanel({
  market,
  cashBalance,
  onTraded,
}: {
  market: Market;
  cashBalance: number | null;
  onTraded: () => void;
}) {
  const [amount, setAmount] = useState("10");
  const [loading, setLoading] = useState<BuyPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const amountNum = Number(amount);
  const amountValid = Number.isFinite(amountNum) && amountNum > 0;
  const overBudget = cashBalance !== null && amountValid && amountNum > cashBalance;

  async function handleBuy(position: BuyPosition) {
    setError(null);
    setSuccess(null);
    if (!amountValid) {
      setError("Enter an amount greater than $0.");
      return;
    }
    const price = position === "YES" ? market.yes_price : market.no_price;
    if (price <= 0) {
      setError(`No market price available for ${position} right now.`);
      return;
    }
    setLoading(position);
    try {
      const trade = await buyPosition(market.ticker, position, amountNum);
      setSuccess(
        `Bought ${trade.contracts.toFixed(2)} ${position} contracts at ${(trade.entry_price * 100).toFixed(0)}¢ for $${trade.amount.toFixed(2)}.`
      );
      onTraded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Trade failed.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Paper Trade</h2>
        <Link href="/portfolio" className="text-xs text-slate-500 hover:text-slate-300">
          View portfolio →
        </Link>
      </div>

      <p className="mb-3 text-xs text-slate-500">
        Simulated money only — this is a research tool, not investment advice.
        {cashBalance !== null && <> Available cash: ${cashBalance.toFixed(2)}.</>}
      </p>

      <div className="mb-3 flex items-center gap-2">
        <span className="text-sm text-slate-400">$</span>
        <input
          type="number"
          min="0"
          step="1"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          className="w-28 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm"
        />
      </div>

      {overBudget && (
        <p className="mb-3 text-xs text-rose-400">Exceeds your available cash.</p>
      )}

      <div className="flex gap-3">
        <button
          onClick={() => handleBuy("YES")}
          disabled={loading !== null || !amountValid || overBudget || market.yes_price <= 0}
          className="flex-1 rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading === "YES" ? "Buying…" : `Buy YES (${(market.yes_price * 100).toFixed(0)}¢)`}
        </button>
        <button
          onClick={() => handleBuy("NO")}
          disabled={loading !== null || !amountValid || overBudget || market.no_price <= 0}
          className="flex-1 rounded-md bg-rose-700 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading === "NO" ? "Buying…" : `Buy NO (${(market.no_price * 100).toFixed(0)}¢)`}
        </button>
      </div>

      {error && (
        <div className="mt-3 rounded-md border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}
      {success && (
        <div className="mt-3 rounded-md border border-emerald-800 bg-emerald-950/30 px-3 py-2 text-sm text-emerald-300">
          {success}
        </div>
      )}
    </div>
  );
}
