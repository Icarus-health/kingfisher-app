export type TaskTemporalFilter = "all" | "recent" | "review";
export type TaggedTaskPage = {offset: number; temporal: TaskTemporalFilter; total: number; items: unknown[]};

export function isVisibleTaskPage(page: TaggedTaskPage | null, offset: number, temporal: TaskTemporalFilter,
  loading: boolean, error: boolean): page is TaggedTaskPage {
  return Boolean(page && !loading && !error && page.offset === offset && page.temporal === temporal);
}

export function generationForTaskPage(offset: number, generation: string | undefined): string | undefined {
  return offset > 0 ? generation : undefined;
}
