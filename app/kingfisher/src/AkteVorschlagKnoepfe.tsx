import { useState } from "react";
import { ApiError, api, type Attention } from "./api";
import { fehlerSatz } from "./akteVorschlag";
import { zeigeHinweis } from "./grundlage";

// „Neue Akte?“ auf Heute (sidecar: akten_vorschlaege.py): ein Satz mit Grund, zwei Knöpfe. Angelegt wird nur mit
// „Akte anlegen“; „Nein danke“ wird gemerkt. Beides antwortet mit dem Hinweis unten (V4): der Satz des Sidecars, der
// Weg in die Akte und „Rückgängig“ über `zuruecknehmen` – der Hinweis bleibt, auch wenn der Punkt danach aus dem
// Briefing verschwindet. `onDone` lädt Heute neu.
export function AkteVorschlagKnoepfe({ item, onDone }: { item: Attention; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!item.source_ref) return null;
  async function klick(was: "anlegen" | "ablehnen") {
    if (busy || !item.source_ref) return;
    const kennung = item.source_ref;
    setBusy(true); setError("");
    try {
      const ergebnis = was === "anlegen" ? await api.akteVorschlagAnnehmen(kennung) : await api.akteVorschlagAblehnen(kennung);
      zeigeHinweis({ text: ergebnis.satz, verweis: { text: "Akte öffnen", href: ergebnis.link },
        rueckgaengig: async () => { const zurueck = await api.akteVorschlagZuruecknehmen(kennung); onDone(); return zurueck.satz; } });
      onDone();
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
