import { useState } from "react";
import { ApiError, api, type Attention } from "./api";
import { fehlerSatz } from "./akteVorschlag";

// „Neue Akte?“ auf Heute (sidecar: akten_vorschlaege.py): ein Satz mit Grund, zwei Knöpfe. Angelegt wird nur mit
// „Akte anlegen“; „Nein danke“ wird gemerkt. Beides antwortet mit einem Satz, den die Seite behält, auch wenn der
// Punkt danach aus dem Briefing verschwindet (`onDone`), und die Antwort führt in die Akte.
export function AkteVorschlagKnoepfe({ item, onDone }: { item: Attention; onDone: (antwort: { satz: string; link: string }) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!item.source_ref) return null;
  async function klick(was: "anlegen" | "ablehnen") {
    if (busy || !item.source_ref) return;
    setBusy(true); setError("");
    try {
      const ergebnis = was === "anlegen" ? await api.akteVorschlagAnnehmen(item.source_ref) : await api.akteVorschlagAblehnen(item.source_ref);
      onDone({ satz: ergebnis.satz, link: ergebnis.link });
    } catch (failure) {
      setError(fehlerSatz(failure instanceof ApiError ? failure.status : null));
    } finally { setBusy(false); }
  }
  return <span className="briefing-suggestion">
    <button type="button" className="secondary-action" disabled={busy} onClick={() => void klick("anlegen")}>{busy ? "Wird gespeichert …" : "Akte anlegen"}</button>
    <button type="button" className="secondary-action" disabled={busy} onClick={() => void klick("ablehnen")}>Nein danke</button>
    {error && <small role="alert">{error}</small>}
  </span>;
}
