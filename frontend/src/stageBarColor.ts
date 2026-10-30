const POSITIVE_STAGE_NAMES = ["fee paid", "enrolled", "payment received"];
const NEGATIVE_STAGE_NAMES = ["dropped"];

// Pastel green/red for the stages the outcome is already known for
// (fee paid/enrolled/payment received vs. dropped), independent of the
// is_won/is_lost flags — those only ever mark a single stage per
// outcome, not every stage a tenant considers a good or bad sign.
export function stageBarColor(stageName: string, isWon: boolean | undefined): string {
  const lower = stageName.toLowerCase();
  if (isWon || POSITIVE_STAGE_NAMES.some((name) => lower.includes(name))) {
    return "var(--chart-bar-positive)";
  }
  if (NEGATIVE_STAGE_NAMES.some((name) => lower.includes(name))) {
    return "var(--chart-bar-negative)";
  }
  if (lower.includes("demo scheduled")) {
    return "var(--chart-bar-demo-scheduled)";
  }
  if (lower.includes("contacted")) {
    return "var(--chart-bar-contacted)";
  }
  return "var(--chart-bar)";
}
