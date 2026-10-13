/** Restore only the memory list's supported navigation state, never an arbitrary URL. */
export function memoryReturnPath(search: string, kind: "person" | "project" = "person"): string {
  const fallbackTab = kind === "project" ? "projects" : "people";
  const fallback = `/memory?tab=${fallbackTab}`;
  const targets = new URLSearchParams(search).getAll("return_to");
  if (targets.length !== 1) return fallback;
  const target = targets[0];
  if (!/^\/memory(?:\?|$)/.test(target) || /[\\#\u0000-\u001f\u007f]/.test(target)) return fallback;
  const query = new URLSearchParams(target.slice("/memory".length));
  if (["tab", "q", "page", "people", "view", "area"].some(key => query.getAll(key).length > 1)) return fallback;
  const area = query.get("area");
  if (area !== null && !["work", "personal", "health", "finance", "other"].includes(area)) return fallback;
  const tab = query.get("tab") ?? (area ? "areas" : fallbackTab);
  if (!["search", "areas", "people", "projects", "topics", "topic-files", "organizations", "places", "decisions", "documents"].includes(tab)) return fallback;
  const page = query.get("page");
  if (page !== null && (!/^[1-9]\d*$/.test(page) || !Number.isSafeInteger(Number(page)))) return fallback;
  const q = query.get("q");
  if (q !== null && (q.length > 500 || /[\u0000-\u001f\u007f]/.test(q))) return fallback;
  const people = query.get("people");
  if (people !== null && !["people", "automated", "review", "all"].includes(people)) return fallback;
  const view = query.get("view");
  if (view !== null && view !== "status" && view !== "support") return fallback;
  const safe = new URLSearchParams({tab});
  if (q !== null) safe.set("q", q);
  if (page !== null) safe.set("page", page);
  if (people !== null) safe.set("people", people);
  if (view !== null) safe.set("view", view);
  if (area !== null) safe.set("area", area);
  return `/memory?${safe}`;
}
