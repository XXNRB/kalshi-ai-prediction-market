"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { PricePoint } from "@/lib/types";

export default function PriceChart({ history }: { history: PricePoint[] }) {
  if (history.length === 0) {
    return (
      <p className="text-sm text-slate-500">
        No price history yet — the ingestion service records a point whenever the price moves.
      </p>
    );
  }

  const data = history.map((p) => ({
    time: new Date(p.timestamp).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }),
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
