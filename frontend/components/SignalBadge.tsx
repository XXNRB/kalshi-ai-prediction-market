import type { Signal } from "@/lib/types";

const STYLES: Record<string, string> = {
  entry: "border-emerald-700 bg-emerald-500/10 text-emerald-400",
  exit: "border-amber-700 bg-amber-500/10 text-amber-400",
};

export function SignalPill({ signal }: { signal: Signal | null }) {
  if (!signal || signal.type === "none" || !signal.label) return null;
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 text-xs whitespace-nowrap ${STYLES[signal.type]}`}
    >
      {signal.type === "entry" ? "Low entry" : "Consider selling"}
    </span>
  );
}

export default function SignalCallout({ signal }: { signal: Signal | null }) {
  if (!signal || signal.type === "none" || !signal.label) return null;
  return (
    <div className={`rounded-lg border p-4 text-sm ${STYLES[signal.type]}`}>
      <p className="font-medium">{signal.label}</p>
      {signal.explanation && <p className="mt-1 text-slate-300">{signal.explanation}</p>}
      <p className="mt-2 text-xs text-slate-500">
        Pattern-based on recent price movement only — not a guarantee prices continue this way.
      </p>
    </div>
  );
}
