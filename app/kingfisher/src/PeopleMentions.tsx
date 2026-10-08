import { useCallback, useEffect, useState } from "react";

import { ProfileSource } from "./ProfileSource";

type PersonMention = {
  name: string;
  quote: string;
  role: "sender" | "mentioned";
  episode_id: string;
  title: string;
  occurred_at: string | null;
  recorded_at: string;
  source_type: string;
};

type PersonMentionsResult = {
  items: PersonMention[];
  total_in_scanned_sources: number;
  scanned_sources: number;
  scan_limit: number;
  limited: boolean;
};

function dateLabel(item: PersonMention) {
  const value = item.occurred_at || item.recorded_at;
  const date = new Date(value);
  if(Number.isNaN(date.getTime())) return "Quelldatum ungeklärt";
  return item.occurred_at ? `Quelldatum ${date.toLocaleDateString("de-DE")}` : `Quelldatum ungeklärt · erfasst am ${date.toLocaleDateString("de-DE")}`;
}

export function PeopleMentions() {
  const [data, setData] = useState<PersonMentionsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(false);
    setData(null);
    try {
      const response = await fetch("/api/v1/memory/people/mentions?limit=100", { signal });
      if (!response.ok) throw new Error("Request failed");
      const next=await response.json() as PersonMentionsResult;
      if(!signal?.aborted) setData(next);
    } catch {
      if (!signal?.aborted) setError(true);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => controller.abort();
  }, [refresh]);

  return <section className="people-review-group" aria-label="Erwähnte Menschen · Quellenhinweise">
    <h3>Erwähnte Menschen · Quellenhinweise</h3>
    <p>Diese Namen wurden in aktuellen Quellen erkannt. Sie sind ungeprüfte Hinweise und werden keiner Personenakte zugeordnet.</p>
    {loading && !data ? <p role="status">Quellenhinweise werden geladen …</p> : null}
    {error ? <p className="people-review-error" role="alert">Die Quellenhinweise konnten nicht geladen werden. <button type="button" onClick={() => void refresh()}>Erneut versuchen</button></p> : null}
    {data?.items.length ? <ul className="people-mentions-list">
      {data.items.map((item, index) => <li key={`${item.episode_id}:${item.name}:${index}`}>
        <strong>{item.name}</strong><small>{item.role === "sender" ? "Absenderhinweis" : "Im Text erwähnt"} · {dateLabel(item)}</small>
        <blockquote>{item.quote}</blockquote>
        <ProfileSource kind="episode" id={item.episode_id} label="Originalquelle öffnen" readOnly allowIgnore={false} />
      </li>)}
    </ul> : data && !loading ? <p>Keine aktuellen Personennamen aus Quellenhinweisen gefunden.</p> : null}
    {data ? <small className="people-mentions-limit">
      {data.scanned_sources} aktuelle Quellen geprüft (höchstens {data.scan_limit}); {data.total_in_scanned_sources} Hinweise in diesem Ausschnitt.
      {data.limited ? " Die Liste ist begrenzt; Aktualisieren zeigt den neuesten Stand." : ""}
    </small> : null}
    {!loading && data ? <button className="people-review-secondary" type="button" onClick={() => void refresh()}>Quellenhinweise aktualisieren</button> : null}
  </section>;
}
