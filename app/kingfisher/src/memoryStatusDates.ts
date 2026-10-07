export type TimelineBasis = "source" | "recorded";

export function newestSourceMonth(latest: string | null | undefined): string | null {
  if (!latest) return null;
  const date = new Date(latest);
  if (Number.isNaN(date.getTime())) return null;
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function timelineDateValues(item: {occurred_at: string | null; recorded_at: string}, basis: TimelineBasis) {
  return basis === "source"
    ? {main: item.occurred_at, secondary: item.recorded_at}
    : {main: item.recorded_at, secondary: item.occurred_at};
}
