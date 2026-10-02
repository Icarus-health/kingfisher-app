import { useRef, useState } from "react";
import { ProfileSource } from "./ProfileSource";
import type { SatzAntwortDaten } from "./api";
import { belegHinweise, istGekennzeichnet } from "./belegHinweis";
import { nebensatz, pruefungFuss, verworfenPruefmodell } from "./pruefHinweis";
import "./SatzAntwort.css";

/**
 * Eine belegte Antwort in Sätzen (E3). Ruhig: die Sätze, dahinter kleine Belegnummern. Wer nachsehen will,
 * öffnet „Weg nach unten“ und sieht die Akte, die Belege im Wortlaut und, wo etwas überholt ist, was jetzt gilt.
 */
export function SatzAntwort({ daten, onChange }: { daten: SatzAntwortDaten; onChange?: () => void }) {
  const [offen, setOffen] = useState(false);
  const wurzel = useRef<HTMLDivElement>(null);
  function zeigeBeleg(nummer: number) {
    setOffen(true);
    // Erst nach dem Öffnen gibt es etwas zum Ansteuern.
    window.setTimeout(() => wurzel.current?.querySelector<HTMLElement>(`[data-beleg="${nummer}"]`)?.scrollIntoView({ block: "nearest" }), 0);
  }
  return <div className="satzantwort" ref={wurzel}>
    <ol className="satz-liste">
      {daten.saetze.map((satz, index) => <li key={index}>
        <p>{satz.text}{" "}
          <span className="satz-belege" aria-label="Belege">
            {[...new Set(satz.belege)].sort((a, b) => a - b).map(nummer => <button className="satz-nr" key={nummer} type="button" aria-label={`Beleg ${nummer} anzeigen`} onClick={() => zeigeBeleg(nummer)}>{nummer}</button>)}
          </span>
          {nebensatz(satz) ? <span className="satz-verlaesslichkeit">{" "}({nebensatz(satz)})</span> : null}
        </p>
      </li>)}
    </ol>
    {verworfenPruefmodell(daten.verworfen_pruefmodell) ? <p className="satz-hinweis">{verworfenPruefmodell(daten.verworfen_pruefmodell)}.</p> : null}
    {daten.verworfen ? <p className="satz-hinweis">{daten.verworfen === 1 ? "Ein Satz" : `${daten.verworfen} Sätze`} verworfen, weil die Belege {daten.verworfen === 1 ? "ihn" : "sie"} nicht getragen haben.</p> : null}
    <details className="satz-weg" open={offen} onToggle={event => setOffen(event.currentTarget.open)}>
      <summary>Weg nach unten: Akte und Quellen</summary>
      {daten.akte.length ? <section aria-label="Aus der Akte">
        <h4>Aus der Akte</h4>
        {daten.akte.map((zeile, index) => <article key={index}>
          <small>{zeile.name} · {zeile.rolle}{zeile.datum ? ` · ${tag(zeile.datum)}` : ""}</small>
          <blockquote>{zeile.text}</blockquote>
        </article>)}
      </section> : null}
      <section aria-label="Belege">
        <h4>Belege</h4>
        {daten.belege.map(beleg => <article key={beleg.nummer} data-beleg={beleg.nummer} className={istGekennzeichnet(beleg) ? "satz-ueberholt" : undefined}>
          <small><span className="satz-nr satz-nr-still">{beleg.nummer}</span> {beleg.titel}{beleg.datum ? ` · ${beleg.datum}` : ""}{belegHinweise(beleg).map(hinweis => ` · ${hinweis}`).join("")}</small>
          <blockquote>{beleg.zitat}</blockquote>
          <ProfileSource kind="episode" id={beleg.episode_id} label={`Quelle öffnen: ${beleg.titel || "Original"}`} allowDismiss quiet onChange={onChange} />
        </article>)}
      </section>
      <p className="satz-hinweis">{pruefungFuss(daten.pruefung?.zustand)} Stand vom {tag(daten.stichtag)}.</p>
    </details>
  </div>;
}

function tag(wert: string) {
  const zeit = /^\d{4}-\d{2}-\d{2}$/.test(wert) ? new Date(`${wert}T12:00:00`) : new Date(wert);
  return Number.isNaN(zeit.getTime()) ? wert : zeit.toLocaleDateString("de-DE", { day: "numeric", month: "numeric", year: "numeric" });
}
