import OpportunityStars from "@/components/OpportunityStars";
import type { OpportunityScore } from "@/lib/types";

export default function OpportunityBreakdown({ opportunity }: { opportunity: OpportunityScore | null }) {
  if (!opportunity) return null;

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Opportunity Score</h2>
        <OpportunityStars opportunity={opportunity} showLabel />
      </div>
      <p className="mb-4 text-xs text-slate-500">
        {opportunity.total.toFixed(0)}/100 · Liquidity + Time Advantage + Probability Edge +
        Information Advantage − Risk
      </p>

      {!opportunity.researched && (
        <div className="mb-4 rounded-md border border-slate-700 bg-slate-900/60 px-3 py-2 text-xs text-slate-400">
          Probability Edge and Information Advantage are 0 until you generate an AI analysis for
          this market — this score only reflects what&apos;s free to compute right now.
        </div>
      )}

      <div className="space-y-3 text-sm">
        {opportunity.components.map((c) => (
          <div key={c.label} className="flex items-start justify-between gap-4">
            <div>
              <div className="font-medium text-slate-300">{c.label}</div>
              <div className="text-xs text-slate-500">{c.explanation}</div>
            </div>
            <div
              className={`shrink-0 tabular-nums font-medium ${c.score < 0 ? "text-rose-400" : "text-slate-300"}`}
            >
              {c.score >= 0 ? "+" : ""}
              {c.score.toFixed(1)}/{c.max_score.toFixed(0)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
