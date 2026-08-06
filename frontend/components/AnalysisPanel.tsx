"use client";

import { useEffect, useRef, useState } from "react";
import { analyzeMarket } from "@/lib/api";
import type { MarketAnalysis } from "@/lib/types";

const AUTO_REFRESH_THRESHOLD = 0.03; // 3 percentage points
const MIN_REFRESH_INTERVAL_MS = 60000; // don't auto re-run more than once a minute

export default function AnalysisPanel({
  ticker,
  currentYesPrice,
  initialAnalysis,
}: {
  ticker: string;
  currentYesPrice: number;
  initialAnalysis: MarketAnalysis | null;
}) {
  const initialAtPrice = initialAnalysis?.market_implied_probability ?? null;
  const initialAt = initialAnalysis?.analyzed_at ? new Date(initialAnalysis.analyzed_at) : null;

  const [analysis, setAnalysis] = useState<MarketAnalysis | null>(initialAnalysis);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyzedAtPrice, setAnalyzedAtPrice] = useState<number | null>(initialAtPrice);
  const [analyzedAt, setAnalyzedAt] = useState<Date | null>(initialAt);
  const [autoNote, setAutoNote] = useState<string | null>(null);

  const analyzedAtPriceRef = useRef<number | null>(initialAtPrice);
  const lastRunAtRef = useRef(initialAt ? initialAt.getTime() : 0);
  const loadingRef = useRef(false);

  async function runAnalysis(auto: boolean) {
    if (loadingRef.current) return;
    loadingRef.current = true;
    setLoading(true);
    setError(null);
    const priceBefore = analyzedAtPriceRef.current;

    try {
      const result = await analyzeMarket(ticker);
      const now = new Date();
      setAnalysis(result);
      setAnalyzedAtPrice(currentYesPrice);
      setAnalyzedAt(now);
      analyzedAtPriceRef.current = currentYesPrice;
      lastRunAtRef.current = now.getTime();
      setAutoNote(
        auto && priceBefore !== null
          ? `Updated automatically at ${now.toLocaleTimeString()} — price moved from ${(priceBefore * 100).toFixed(0)}% to ${(currentYesPrice * 100).toFixed(0)}%`
          : null
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed.");
    } finally {
      loadingRef.current = false;
      setLoading(false);
    }
  }

  useEffect(() => {
    if (analyzedAtPriceRef.current === null) return; // no analysis yet — nothing to auto-refresh
    const moved = Math.abs(currentYesPrice - analyzedAtPriceRef.current) >= AUTO_REFRESH_THRESHOLD;
    const cooledDown = Date.now() - lastRunAtRef.current >= MIN_REFRESH_INTERVAL_MS;
    if (moved && cooledDown && !loadingRef.current) {
      runAnalysis(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentYesPrice]);

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <div className="mb-1 flex items-center justify-between">
        <h2 className="text-lg font-semibold">AI Research Analysis</h2>
        <button
          onClick={() => runAnalysis(false)}
          disabled={loading}
          className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Analyzing…" : analysis ? "Refresh Analysis" : "Generate AI Analysis"}
        </button>
      </div>

      {analyzedAt && (
        <p className="mb-4 text-xs text-slate-500">
          Last analyzed {analyzedAt.toLocaleTimeString()} at{" "}
          {analyzedAtPrice !== null ? (analyzedAtPrice * 100).toFixed(0) : "—"}% YES · live price now{" "}
          {(currentYesPrice * 100).toFixed(0)}%. Auto-refreshes when price moves ≥3 points.
        </p>
      )}

      {autoNote && (
        <div className="mb-4 rounded-md border border-emerald-800 bg-emerald-950/30 px-3 py-2 text-xs text-emerald-300">
          {autoNote}
        </div>
      )}

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
