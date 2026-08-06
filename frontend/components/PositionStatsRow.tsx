import type { PositionStats } from "@/lib/types";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-slate-500">{label}</span> {value}
    </span>
  );
}

export default function PositionStatsRow({ stats }: { stats: PositionStats }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-300">
      <Stat label="ROI" value={`${stats.roi_pct >= 0 ? "+" : ""}${stats.roi_pct.toFixed(1)}%`} />
      <Stat
        label="Prob. change"
        value={`${stats.probability_change_pts >= 0 ? "+" : ""}${stats.probability_change_pts.toFixed(1)}pt`}
      />
      <Stat
        label="EV"
        value={stats.expected_value_pct === null ? "not yet researched" : `${stats.expected_value_pct >= 0 ? "+" : ""}${stats.expected_value_pct.toFixed(1)}%`}
      />
      <Stat
        label="Momentum"
        value={`${stats.momentum_pts_per_step >= 0 ? "+" : ""}${stats.momentum_pts_per_step.toFixed(2)}pt/step`}
      />
      <Stat label="Risk" value={`${stats.risk_score.toFixed(0)}/25`} />
      {stats.action === "consider_profit" && (
        <span
          className="rounded-full border border-amber-700 bg-amber-500/10 px-2 py-0.5 text-amber-400"
          title={stats.reason}
        >
          Consider taking profit
        </span>
      )}
    </div>
  );
}
