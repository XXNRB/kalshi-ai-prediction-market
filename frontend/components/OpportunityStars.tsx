import type { OpportunityScore } from "@/lib/types";

export default function OpportunityStars({
  opportunity,
  showLabel = false,
}: {
  opportunity: OpportunityScore | null;
  showLabel?: boolean;
}) {
  if (!opportunity) return <span className="text-slate-600">—</span>;

  const stars = "★".repeat(opportunity.stars) + "☆".repeat(5 - opportunity.stars);

  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      <span className="tracking-tight text-amber-400">{stars}</span>
      {showLabel && <span className="text-xs text-slate-500">{opportunity.tier_label}</span>}
    </span>
  );
}
