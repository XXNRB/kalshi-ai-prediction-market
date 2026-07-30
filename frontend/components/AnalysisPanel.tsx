"use client";

import { useState } from "react";
import { analyzeMarket } from "@/lib/api";
import type { MarketAnalysis } from "@/lib/types";

export default function AnalysisPanel({ ticker }: { ticker: string }) {
  const [analysis, setAnalysis] = useState<MarketAnalysis | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAnalyze() {
    setLoading(true);
    setError(null);
    try {
      setAnalysis(await analyzeMarket(ticker));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">AI Research Analysis</h2>
        <button
          onClick={handleAnalyze}
          disabled={loading}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Analyzing…" : "Generate AI Analysis"}
        </button>
      </div>

      {error && (
        <div className="rounded-md border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-300">
          {error}
        </div>
      )}

      {!analysis && !error && !loading && (
        <p className="text-sm text-slate-500">
          Not analyzed yet. This is AI-generated research, not financial advice — every result
          shows its reasoning, confidence, risks, and data sources so you can judge it yourself.
        </p>
      )}

      {analysis && (
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <Stat label="Market Implied" value={`${(analysis.market_implied_probability * 100).toFixed(0)}%`} />
            <Stat label="AI Estimated" value={`${(analysis.ai_estimated_probability * 100).toFixed(0)}%`} />
            <Stat
              label="Edge"
              value={`${analysis.edge >= 0 ? "+" : ""}${(analysis.edge * 100).toFixed(0)}%`}
              accent={analysis.edge >= 0 ? "text-emerald-400" : "text-rose-400"}
            />
            <Stat label="Confidence" value={`${analysis.confidence}/10`} />
          </div>

          <div>
            <h3 className="mb-1 font-medium text-slate-300">Recommendation</h3>
            <p>
              {analysis.recommendation} — suggested allocation {analysis.suggested_allocation_pct}% of
              bankroll
            </p>
          </div>

          <div>
            <h3 className="mb-1 font-medium text-slate-300">Reasoning</h3>
            <ul className="list-inside list-disc space-y-1 text-slate-400">
              {analysis.reasoning.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="mb-1 font-medium text-slate-300">Risks</h3>
            <ul className="list-inside list-disc space-y-1 text-slate-400">
              {analysis.risks.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>

          <div>
            <h3 className="mb-1 font-medium text-slate-300">Data Sources</h3>
            <p className="text-slate-500">{analysis.data_sources.join(", ")}</p>
          </div>
        </div>
      )}
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
