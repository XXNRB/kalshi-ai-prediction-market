import type { ExitDecision, GameState, PositionMetrics } from "@/lib/types";

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-slate-500">{label}</span> {value}
    </span>
  );
}

const ORDINALS: Record<number, string> = {
  1: "1st", 2: "2nd", 3: "3rd", 4: "4th", 5: "5th",
  6: "6th", 7: "7th", 8: "8th", 9: "9th",
};

function ordinalInning(inning: number): string {
  return ORDINALS[inning] ?? `${inning}th`;
}

/** Informational only — deliberately separate from the exit-engine action
 * badge above. Never implies a recommendation; omitted entirely rather
 * than shown as a placeholder when no game state is available yet. */
function GameLine({ game }: { game: GameState }) {
  if (game.status === "scheduled") {
    return (
      <div className="mt-1 text-xs text-slate-500">
        ⚾ {game.away_team} @ {game.home_team} · scheduled
      </div>
    );
  }

  const runners = [
    game.runner_on_first && "1st",
    game.runner_on_second && "2nd",
    game.runner_on_third && "3rd",
  ].filter(Boolean) as string[];

  if (game.status === "final") {
    return (
      <div className="mt-1 text-xs text-slate-500">
        ⚾ {game.away_team} {game.away_score} – {game.home_team} {game.home_score} · Final
      </div>
    );
  }

  const half = game.inning_half && game.inning ? `${game.inning_half} ${ordinalInning(game.inning)}` : null;

  return (
    <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-slate-500">
      <span className="whitespace-nowrap">
        ⚾ {game.away_team} {game.away_score} – {game.home_team} {game.home_score}
      </span>
      {half && (
        <span className="whitespace-nowrap">
          {half}
          {game.outs !== null ? `, ${game.outs} out${game.outs === 1 ? "" : "s"}` : ""}
        </span>
      )}
      {runners.length > 0 && <span className="whitespace-nowrap">runners: {runners.join(", ")}</span>}
      {game.status === "delayed" && <span className="whitespace-nowrap text-amber-500">delayed</span>}
      {game.status === "suspended" && <span className="whitespace-nowrap text-amber-500">suspended</span>}
    </div>
  );
}

const URGENCY_STYLES: Record<string, string> = {
  LOW: "border-slate-700 bg-slate-500/10 text-slate-300",
  MEDIUM: "border-amber-700 bg-amber-500/10 text-amber-400",
  HIGH: "border-orange-700 bg-orange-500/10 text-orange-400",
  CRITICAL: "border-rose-700 bg-rose-500/10 text-rose-400",
};

const ACTION_LABELS: Record<string, string> = {
  HOLD: "Hold",
  SELL_PARTIAL: "Sell partial",
  SELL_ALL: "Sell all",
};

function ActionBadge({ decision }: { decision: ExitDecision }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 ${URGENCY_STYLES[decision.urgency]}`}
      title={decision.summary}
    >
      {ACTION_LABELS[decision.action]} · {decision.confidence}% confidence
    </span>
  );
}

export default function PositionStatsRow({
  metrics,
  decision,
  game,
}: {
  metrics: PositionMetrics;
  decision: ExitDecision | null;
  game?: GameState | null;
}) {
  return (
    <div>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-300">
        <Stat label="ROI" value={`${metrics.roi_pct >= 0 ? "+" : ""}${metrics.roi_pct.toFixed(1)}%`} />
        <Stat
          label="Prob. change"
          value={`${metrics.probability_change_pts >= 0 ? "+" : ""}${metrics.probability_change_pts.toFixed(1)}pt`}
        />
        <Stat
          label="EV"
          value={
            metrics.expected_value_pct === null
              ? "not yet researched"
              : `${metrics.expected_value_pct >= 0 ? "+" : ""}${metrics.expected_value_pct.toFixed(1)}%`
          }
        />
        <Stat
          label="Momentum"
          value={`${metrics.momentum_pts_per_step >= 0 ? "+" : ""}${metrics.momentum_pts_per_step.toFixed(2)}pt/step`}
        />
        <Stat label="Risk" value={`${metrics.risk_score.toFixed(0)}/25`} />
        <Stat label="Peak price" value={`${(metrics.peak_price * 100).toFixed(0)}¢`} />
        <Stat
          label="Peak P&L"
          value={`${metrics.peak_profit_loss >= 0 ? "+" : ""}$${metrics.peak_profit_loss.toFixed(2)}`}
        />
        {decision && <ActionBadge decision={decision} />}
      </div>
      {game && <GameLine game={game} />}
    </div>
  );
}
