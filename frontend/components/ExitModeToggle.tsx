"use client";

import { useEffect, useState } from "react";
import { getExitSettings, updateExitSettings } from "@/lib/api";
import type { ExitMode } from "@/lib/types";

export default function ExitModeToggle() {
  const [mode, setMode] = useState<ExitMode | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getExitSettings()
      .then((s) => setMode(s.mode))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load exit settings."));
  }, []);

  async function handleChange(next: ExitMode) {
    if (next === mode) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await updateExitSettings(next);
      setMode(updated.mode);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update exit settings.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-slate-800 p-5">
      <h2 className="mb-1 text-lg font-semibold">Exit Mode</h2>
      <div className="mb-2 inline-flex rounded-md border border-slate-700 text-sm">
        <button
          onClick={() => handleChange("recommend_only")}
          disabled={loading || mode === null}
          className={`rounded-l-md px-3 py-1.5 transition-colors ${
            mode === "recommend_only" ? "bg-emerald-600 text-white" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Recommend Only
        </button>
        <button
          onClick={() => handleChange("auto_execute")}
          disabled={loading || mode === null}
          className={`rounded-r-md px-3 py-1.5 transition-colors ${
            mode === "auto_execute" ? "bg-amber-600 text-white" : "text-slate-400 hover:text-slate-200"
          }`}
        >
          Auto-Execute
        </button>
      </div>
      <p className="text-xs text-slate-500">
        {mode === "auto_execute"
          ? "Auto-Execute runs on the server and stays active even if this page is closed."
          : "Positions show a recommendation and reasoning — you decide whether to sell."}
      </p>
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </div>
  );
}
