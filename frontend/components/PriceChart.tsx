"use client";

import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { getMarketHistory } from "@/lib/api";
import type { PricePoint } from "@/lib/types";

const REFRESH_MS = 15000;

export default function PriceChart({
  ticker,
  initialHistory,
}: {
  ticker: string;
  initialHistory: PricePoint[];
}) {
  const [history, setHistory] = useState(initialHistory);

  useEffect(() => {
    setHistory(initialHistory);
  }, [ticker, initialHistory]);

  useEffect(() => {
    let cancelled = false;

    const poll = async () => {
      try {
        const latest = await getMarketHistory(ticker);
        if (!cancelled) setHistory(latest);
      } catch {
        // transient fetch failure — keep showing the last known chart
      }
    };

    const id = setInterval(poll, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [ticker]);

  if (history.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No price history yet — this market may be too new for Kalshi to have candlestick data.
      </p>
    );
  }

  const showTime = history.length < 2 ||
    new Date(history[history.length - 1].timestamp).getTime() -
      new Date(history[0].timestamp).getTime() <
      36 * 3600 * 1000;

  const data = history.map((p) => ({
    time: showTime
      ? new Date(p.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
      : new Date(p.timestamp).toLocaleDateString(undefined, { month: "short", day: "numeric" }),
    YES: Math.round(p.yes_price * 100),
    NO: Math.round(p.no_price * 100),
  }));

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
        <YAxis stroke="#64748b" fontSize={12} unit="¢" domain={[0, 100]} />
        <Tooltip
          contentStyle={{ background: "#0f172a", border: "1px solid #1e293b", fontSize: 12 }}
        />
        <Line type="monotone" dataKey="YES" stroke="#34d399" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="NO" stroke="#f87171" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
