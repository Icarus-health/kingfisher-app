import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type PersonDigestItem, type PersonDigestResult } from "./api";
import { ProfileSource } from "./ProfileSource";
import "./PersonDigest.css";

function digestDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("de-DE", {day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false}).format(date);
}

function periodDate(value: string) {
  const parts = value.split("-").map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return value;
  return new Intl.DateTimeFormat("de-DE", {day: "2-digit", month: "2-digit", year: "numeric", timeZone: "UTC"})
    .format(new Date(Date.UTC(parts[0], parts[1] - 1, parts[2])));
}
const sourceStatus = {observed: "Beobachtet", confirmed: "Bestätigt", historical: "Früherer Stand"} as const;

function DigestItems({items, empty, onSourceChange}: {items: PersonDigestItem[]; empty: string; onSourceChange: () => void}) {
  if (!items.length) return <p className="person-digest-empty">{empty}</p>;
  return <div className="person-digest-items">{items.map((item, index) => <article key={`${index}:${item.text}`}>
    <p>{item.text}</p>
    {item.citations.length ? <details><summary>{item.citations.length === 1 ? "1 Quelle ansehen" : `${item.citations.length} Quellen ansehen`}</summary>
      <div className="person-digest-sources">{item.citations.map((citation, citationIndex) => <section key={`${citation.source_id}:${citationIndex}`}>
        <strong>{citation.title || "Quelle"}</strong><small>{sourceStatus[citation.status]} · {citation.occurred_at ? digestDate(citation.occurred_at) : "Ereigniszeit nicht angegeben"}</small>
        <blockquote>{citation.quote}</blockquote>
        {citation.episode_ids.map(episodeId => <ProfileSource key={episodeId} kind="episode" id={episodeId} label="Originalquelle öffnen" allowIgnore={false} onChange={onSourceChange} />)}
      </section>)}</div>
    </details> : <small>Keine einzelne Quelle verknüpft.</small>}
  </article>)}</div>;
}

function errorText(error: unknown) {
  if (error instanceof ApiError && error.status === 409) return "Die Quellen haben sich gerade geändert oder der Überblick wird bereits erstellt. Lade den aktuellen Stand und versuche es dann erneut.";
  if (error instanceof ApiError && error.status === 503) return "Das lokale KI-Modell ist gerade nicht erreichbar oder konnte keine gültige Antwort erstellen.";
  if (error instanceof ApiError && error.status === 404) return "Diese Personenakte ist nicht mehr verfügbar.";
  return "Der KI-Überblick konnte nicht geladen werden. Bitte versuche es erneut.";
}

export function PersonDigest({personId}: {personId: string}) {
  const [result, setResult] = useState<PersonDigestResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const requestVersion = useRef(0);
  const generatingRef = useRef(false);
  const load = useCallback(async (quiet = false) => {
    if (generatingRef.current) return;
    const version = ++requestVersion.current;
    if (!quiet) setLoading(true);
    setError("");
    try { const next = await api.personDigest(personId); if (version === requestVersion.current) setResult(next); }
    catch (cause) { if (version === requestVersion.current) { setResult(null); setError(errorText(cause)); } }
    finally { if (version === requestVersion.current) setLoading(false); }
  }, [personId]);
  useEffect(() => {
    generatingRef.current = false;
    setResult(null); setError(""); setGenerating(false); setLoading(true); void load();
    const revalidate = () => { if (document.visibilityState === "visible" && !generatingRef.current) void load(true); };
    const onFocus = () => { revalidate(); };
    const interval = window.setInterval(revalidate, 60_000);
    window.addEventListener("focus", onFocus);
    return () => {
      requestVersion.current += 1;
      generatingRef.current = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", onFocus);
    };
  }, [load]);
  async function generate() {
    if (generatingRef.current) return;
    generatingRef.current = true;
    const version = ++requestVersion.current;
    setResult(null); setGenerating(true); setError("");
    try { const next = await api.refreshPersonDigest(personId); if (version === requestVersion.current) setResult(next); }
    catch (cause) { if (version === requestVersion.current) setError(errorText(cause)); }
    finally {
      if (version === requestVersion.current) {
        generatingRef.current = false;
        setGenerating(false);
      }
    }
  }
  const digest = result?.digest;
  return <section className="profile-card profile-wide person-digest" aria-labelledby={`person-digest-${personId}`}>
    <div className="person-digest-heading"><div><p className="person-digest-kicker">LOKALE KI-AUSWERTUNG</p><h2 id={`person-digest-${personId}`}>KI-Überblick</h2></div>
      {result?.status !== "no_sources" ? <button type="button" disabled={loading || generating} onClick={() => void generate()}>{generating ? <><span className="person-digest-spinner" aria-hidden="true" />Wird lokal erstellt …</> : digest ? "Neu erstellen" : "KI-Überblick erstellen"}</button> : null}
    </div>
    <p className="person-digest-note">Eine Interpretation des lokalen KI-Modells. Sie wird nicht als bestätigtes Wissen gespeichert.</p>
    {loading && !result ? <p className="person-digest-state" role="status">Vorhandener Überblick wird geprüft …</p> : null}
    {generating ? <p className="sr-only" role="status">Der KI-Überblick wird mit dem lokalen Modell erstellt.</p> : null}
    {error ? <p className="person-digest-error" role="alert">{error}</p> : null}
    {!loading && !error && result?.status === "missing" ? <p className="person-digest-state">Noch kein KI-Überblick vorhanden. Du kannst ihn mit dem lokalen Modell erstellen.</p> : null}
    {!loading && !error && result?.status === "no_sources" ? <p className="person-digest-state">Für diese Person gibt es noch keine geeigneten Quellen für einen KI-Überblick.</p> : null}
    {!loading && !error && result?.status === "unavailable" ? <p className="person-digest-error" role="status">Kein lokales Modell verbunden.</p> : null}
    {result?.status === "stale" ? <p className="person-digest-stale" role="status">Die Quellen oder das lokale Modell haben sich seit diesem Überblick geändert. Erstelle ihn neu, um den aktuellen Stand zu sehen.</p> : null}
    {digest ? <><p className="person-digest-meta">Lokales Modell: {digest.model || result?.model || "—"} · Erstellt {digestDate(digest.generated_at)}</p>
      {result ? <p className="person-digest-coverage">Berücksichtigt: {result.source_count} von {result.total_source_count} Quellen{result.truncated ? " · teilweise als Auszüge" : ""}.</p> : null}
      {digest.source_period ? <p className="person-digest-coverage">Zeitraum datierter Quellen: {periodDate(digest.source_period.from)} bis {periodDate(digest.source_period.to)}.</p> : null}
      {(digest.discarded_items ?? 0) > 0 ? <p className="person-digest-coverage">{digest.discarded_items} {digest.discarded_items === 1 ? "Aussage des Modells wurde" : "Aussagen des Modells wurden"} ausgelassen, weil ihre Quellen nicht geprüft werden konnten.</p> : null}
      <section><h3>Überblick</h3><DigestItems items={digest.points} empty="Keine Punkte genannt." onSourceChange={() => void load(true)} /></section>
      <section><h3>Offene Fragen</h3><DigestItems items={digest.questions} empty="Keine offenen Fragen genannt." onSourceChange={() => void load(true)} /></section>
      <section><h3>Mögliche Widersprüche</h3><DigestItems items={digest.conflicts} empty="Keine möglichen Widersprüche genannt." onSourceChange={() => void load(true)} /></section></> : null}
  </section>;
}
