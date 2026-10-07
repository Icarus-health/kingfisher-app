import { useState } from "react";
import { api, type Attention } from "./api";

// Ein erkannter Vorschlag im Briefing. Übernehmen ist ein Klick mit dem
// vorgeschlagenen Titel; wer Projekt, Frist oder Wortlaut ändern oder den
// Vorschlag verwerfen will, prüft ihn in den Vorhaben. Nichts wird angelegt,
// ohne dass hier geklickt wurde.
export function BriefingSuggestion({item, onDone}: {item: Attention; onDone: (message: string) => void}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!item.source_ref) return null;
  async function accept() {
    if (busy || !item.source_ref) return;
    setBusy(true); setError("");
    try {
      await api.acceptTaskCandidate(item.source_ref, {title: item.title, project_id: null, due: null, waiting_for: null});
      onDone(`„${item.title}“ steht jetzt unter deinen Aufgaben.`);
    } catch (failure) {
      setError(failure instanceof Error && failure.message === "HTTP 409"
        ? "Dieser Vorschlag ist nicht mehr verfügbar, etwa weil seine Quelle ausgeschlossen wurde."
        : "Die Aufgabe konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally { setBusy(false); }
  }
  return <span className="briefing-suggestion">
    {!item.review_required && <button type="button" className="secondary-action" disabled={busy} onClick={() => void accept()}>{busy ? "Wird übernommen …" : "Als Aufgabe übernehmen"}</button>}
    <a className="attention-task-link" href="/vorhaben?view=mine&pruefen=1">Prüfen</a>
    {error && <small role="alert">{error}</small>}
  </span>;
}
