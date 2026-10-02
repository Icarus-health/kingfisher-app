import { useEffect, useRef, useState } from "react";

import { ApiError, api, type SupportReassessmentPreview, type SupportReviewPage } from "./api";
import { ProfileSource } from "./ProfileSource";
import "./SelfModelSupportReview.css";

function date(value: string) {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString("de-DE", {dateStyle: "medium", timeStyle: "short"});
}

function currencyLabel(value: string) {
  if (value === "current") return "Aktuell";
  if (value === "stale") return "Möglicherweise veraltet";
  if (value === "outdated") return "Nicht mehr aktuell";
  if (value === "disputed") return "Strittig";
  return value;
}

function supportLabel(value: string) {
  if (value === "supported") return "Belege nutzbar";
  if (value === "review_required") return "Belege erneut prüfen";
  if (value === "unavailable") return "Belege nicht nutzbar";
  return value;
}

function kindLabel(value: string) {
  const labels: Record<string, string> = {
    identity: "Identität", preference: "Vorliebe", state: "Zustand",
    episode: "Ereignis", goal: "Ziel", relationship: "Beziehung",
    skill: "Fähigkeit", constraint: "Grenze", decision: "Entscheidung",
  };
  return labels[value] ?? value;
}

export function SelfModelSupportReview({onSubmittingChange}: {onSubmittingChange?: (submitting: boolean) => void}) {
  const [cursors, setCursors] = useState<Array<string | null>>([null]);
  const [pageIndex, setPageIndex] = useState(0);
  const [revision, setRevision] = useState(0);
  const [page, setPage] = useState<SupportReviewPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [preview, setPreview] = useState<SupportReassessmentPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [warning, setWarning] = useState("");
  const operation = useRef(0);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; operation.current += 1; };
  }, []);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setListError(false);
    api.supportReview(cursors[pageIndex]).then(result => {
      if (active) setPage(result);
    }).catch(() => {
      if (active) { setPage(null); setListError(true); }
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [cursors, pageIndex, revision]);

  function clearPreview() {
    operation.current += 1;
    setSelectedId(null);
    setPreview(null);
    setBusy(false);
    setMessage("");
    setWarning("");
  }

  function refresh() {
    if (busy) return;
    clearPreview();
    setCursors([null]);
    setPageIndex(0);
    setRevision(value => value + 1);
  }

  async function showPreview(id: string) {
    if (busy) return;
    const current = ++operation.current;
    setSelectedId(id);
    setPreview(null);
    setBusy(true);
    setMessage("");
    setWarning("");
    try {
      const result = await api.previewSupportReassessment(id);
      if (result.item.id !== id) throw new Error("Vorschau gehört nicht zur ausgewählten Aussage.");
      if (mounted.current && current === operation.current) setPreview(result);
    } catch (failure) {
      if (mounted.current && current === operation.current) {
        setMessage(failure instanceof ApiError && failure.status === 409
          ? "Die Aussage oder ihre Belege haben sich geändert. Bitte eine neue Vorschau laden."
          : "Die Belegvorschau konnte nicht geladen werden. Bitte erneut versuchen.");
      }
    } finally {
      if (mounted.current && current === operation.current) setBusy(false);
    }
  }

  async function confirm() {
    const token = preview?.preview_token;
    const id = selectedId;
    if (!id || !token || !preview.item.eligible || preview.evidence.length === 0 || busy) return;
    const current = ++operation.current;
    setBusy(true);
    onSubmittingChange?.(true);
    setMessage("");
    try {
      const result = await api.submitSupportReassessment(id, token);
      if (!mounted.current || current !== operation.current) return;
      setPreview(null);
      setSelectedId(null);
      setPage(existing => existing && ({...existing, items: existing.items.map(item => item.id === id ? result.item : item)}));
      setMessage("Belegnutzung für lokale Antworten erneut geprüft. Der fachliche Zeitbezug der Aussage bleibt unverändert.");
      setWarning(result.audit_warning ?? "");
      setRevision(value => value + 1);
    } catch (failure) {
      if (!mounted.current || current !== operation.current) return;
      // Ein Token wird nach jeder fehlgeschlagenen Bestätigung verworfen.
      // Eine zweite Bestätigung darf nur aus einer frischen Vorschau kommen.
      setPreview(null);
      setMessage(failure instanceof ApiError && failure.status === 409
        ? "Diese Vorschau ist nicht mehr gültig. Bitte Aussage und Originalbelege erneut laden."
        : "Die Belegnutzung konnte nicht bestätigt werden. Bitte eine neue Vorschau laden.");
    } finally {
      onSubmittingChange?.(false);
      if (mounted.current && current === operation.current) setBusy(false);
    }
  }

  function previous() {
    if (loading || busy || pageIndex === 0) return;
    clearPreview();
    setPage(null);
    setPageIndex(value => value - 1);
  }

  function next() {
    if (loading || busy || !page?.next_cursor) return;
    clearPreview();
    setPage(null);
    const nextCursor = page.next_cursor;
    setCursors(existing => [...existing.slice(0, pageIndex + 1), nextCursor]);
    setPageIndex(value => value + 1);
  }

  return <section className="memory-status support-review" aria-label="Aussagen prüfen">
    <header>
      <div><p className="eyebrow">GEDÄCHTNIS</p><h1>Aussagen prüfen</h1>
        <p className="support-review-intro">Hier prüfst du bestehende Aussagen und ihre Originalbelege einzeln für lokale Antworten. Die Prüfung ändert nicht, wann die Aussage fachlich galt.</p>
      </div>
      <button type="button" disabled={busy} onClick={refresh}>Aktualisieren</button>
    </header>
    {message && <p className="support-review-message" role="status">{message}</p>}
    {warning && <p className="support-review-warning" role="alert">{warning}</p>}
    {listError ? <p role="alert">Die Aussagen konnten nicht geladen werden. Bitte erneut aktualisieren.</p> : null}
    {loading ? <p role="status">Aussagen werden geladen …</p> : null}
    {!loading && page && page.items.length === 0 ? <p className="memory-status-card">Auf dieser Seite liegen keine Aussagen zur Prüfung vor.</p> : null}
    {!loading && page ? <>
      <div className="support-review-list">
        {page.items.map(item => {
          // Die Vorschau ist die frische, tokengebundene Fassung der Aussage.
          const shown = selectedId === item.id && preview ? preview.item : item;
          return <article className="memory-status-card support-review-card" key={item.id}>
          <h2>{shown.statement}</h2>
          <dl className="support-review-facts">
            <div><dt>Art</dt><dd>{kindLabel(shown.kind)}</dd></div>
            <div><dt>Fachlicher Zeitbezug</dt><dd>{date(shown.factual_at)}</dd></div>
            <div><dt>Aktualität</dt><dd>{currencyLabel(shown.currency)}</dd></div>
            <div><dt>Belegstand</dt><dd>{supportLabel(shown.support_status)}</dd></div>
          </dl>
          {shown.reason && <p className="support-review-reason">{shown.reason}</p>}
          <button type="button" disabled={busy || loading} aria-expanded={selectedId === item.id} onClick={() => void showPreview(item.id)}>
            {selectedId === item.id && busy ? "Originalbelege werden geladen …" : selectedId === item.id ? "Vorschau neu laden" : "Aussage und Originalbelege prüfen"}
          </button>
          {selectedId === item.id && preview ? <section className="support-review-preview" aria-label="Originalbelege zur Aussage">
            <h3>Originalbelege</h3>
            <p>Diese Zitate gehören zu der bestehenden Aussage. Prüfe alle, bevor du ihre Nutzung für lokale Antworten erneut bestätigst. Externe Modelle erhalten dadurch keine Freigabe.</p>
            {preview.evidence.length ? <ol>{preview.evidence.map((evidence, index) => <li key={`${evidence.episode_id}:${index}`}>
              <strong>{evidence.title}</strong>
              <blockquote>{evidence.quote}</blockquote>
              <ProfileSource kind="episode" id={evidence.episode_id} label="Originalquelle ansehen" readOnly />
            </li>)}</ol> : <p>Für diese Aussage sind keine freigegebenen Originalbelege verfügbar.</p>}
            {preview.preview_token && preview.item.eligible && preview.evidence.length > 0 ? <>
              {preview.expires_at && <small>Vorschau gültig bis {date(preview.expires_at)}.</small>}
              <button className="support-review-confirm" type="button" disabled={busy} onClick={() => void confirm()}>
                {busy ? "Wird geprüft …" : "Nach Prüfung aller Zitate: Belegnutzung für lokale Antworten bestätigen"}
              </button>
            </> : <p>Diese Belege können derzeit nicht erneut bestätigt werden.</p>}
          </section> : null}
          {selectedId === item.id && message && <p role="alert">{message}</p>}
        </article>;
        })}
      </div>
      <nav className="support-review-pagination" aria-label="Weitere Aussagen">
        <button type="button" disabled={pageIndex === 0 || loading || busy} onClick={previous}>Zurück</button>
        <span>Seite {pageIndex + 1}</span>
        <button type="button" disabled={!page.next_cursor || loading || busy} onClick={next}>Weiter</button>
      </nav>
      {page.truncated && <p className="memory-status-note">Die Liste ist begrenzt. Weitere Aussagen können über „Weiter“ geladen werden.</p>}
    </> : null}
  </section>;
}
