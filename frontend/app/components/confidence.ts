export function confidenceTone(value: number | null | undefined): "high" | "medium" | "low" {
  if (value === null || value === undefined) return "medium";
  if (value >= 0.85) return "high";
  if (value >= 0.6) return "medium";
  return "low";
}
