import { useCallback, useEffect, useState } from "react";
import { ApiError, api } from "./api";
import { ProfileSource } from "./ProfileSource";
import { wkAntwort, wkSatz, wkSichtbar, wkTitel, type WkEintrag, type WkStand } from "./wiederkehrendes";
import "./Kreis.css";

/**
 * Geburtstag (Person) oder Wiederkehrendes (Organisation, Serie) in der Akte: Vorschläge mit Beleg und zwei Knöpfen.
 * Erst „Stimmt, übernehmen“ legt eine Aussage an (docs/49-kreis-und-privat.md); ohne Vorschlag gibt es keine Karte.
 */
export function WiederkehrendKarte({ sache }: { sache: string }) {
  const [stand, setStand] = useState<WkStand | null>(null);
  const [hinweis, setHinweis] = useState("");
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);

  const laden = useCallback(() => api.wiederkehrendes(sache).then(setStand).catch(() => { /* ohne Stand keine Karte */ }), [sache]);
  useEffect(() => { setStand(null); setHinweis(""); setFehler(""); void laden(); }, [laden]);

  async function entscheiden(e: WkEintrag, annehmen: boolean) {
    setArbeitet(true); setFehler(""); setHinweis("");
    try {
      if (annehmen) await api.wissenAnnehmen(e.id); else await api.wissenAblehnen(e.id);
      setHinweis(wkAntwort(e, annehmen));
      await laden();
    } catch (problem) {
      setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Das ließ sich gerade nicht speichern. Bitte noch einmal versuchen.");
    } finally { setArbeitet(false); }
  }

  if (!stand || (!wkSichtbar(stand) && !hinweis)) return null;
  return <section className="mappe-teil akte-teil kreis-karte" aria-label={wkTitel(stand)}>
    <h3>{wkTitel(stand)}</h3>
    {[...stand.angenommen, ...stand.offen].map(e => <div key={e.id} className="wk-eintrag">
      <p className="kreis-satz">{wkSatz(e)}</p>
      {e.art === "vorschlag" ? <p className="kreis-warum">Warum: {e.begruendung}</p> : null}
      {e.beleg ? <p className="kreis-warum">Beleg: „{e.beleg.zitat}“ <ProfileSource kind="episode" id={e.beleg.episode_id} label="Quelle öffnen" quiet readOnly allowIgnore={false} /></p> : null}
      {e.art === "vorschlag" ? <div className="kreis-wahlen" role="group" aria-label="Vorschlag entscheiden">
        <button type="button" className="primary-action" disabled={arbeitet} onClick={() => void entscheiden(e, true)}>Stimmt, übernehmen</button>
        <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => void entscheiden(e, false)}>Stimmt nicht</button>
      </div> : null}
    </div>)}
    {hinweis ? <p role="status" className="kreis-ok">{hinweis}</p> : null}
    {fehler ? <p role="alert" className="kreis-fehler">{fehler}</p> : null}
  </section>;
}
