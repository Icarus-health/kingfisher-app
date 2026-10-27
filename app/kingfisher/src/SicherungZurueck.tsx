import { useEffect, useId, useState } from "react";
import { api, ApiError, type SicherungEintrag, type SicherungStand } from "./api";
import { Rueckfrage, zeigeHinweis } from "./grundlage";
import { holeStand, merkeStand, sicherungArt, sicherungZeit, sichtbareSicherungen, standSatz, wiederherstellenFrage } from "./personDaten";

/** Nach dem Wiederherstellen lädt die Seite neu: Alle Ansichten lesen dann den eingespielten Stand. */
function neuLaden(stand: SicherungStand) {
  merkeStand(stand);
  window.location.reload();
}

/**
 * Einstellungen → Sicherung → „Stand wiederherstellen“ (Persona-Prüfung, Paket P, D7). Eine Sicherung aus der Liste
 * wählen statt einen Pfad zu tippen; eine Rückfrage in einem Satz; vorher sichert Kingfisher den jetzigen Stand, deshalb
 * bietet der Hinweis nach dem Neuladen „Rückgängig“ an. Einstellungen, Schlüssel und Freigaben bleiben, wie sie sind.
 */
export function SicherungZurueck() {
  const [liste, setListe] = useState<SicherungEintrag[] | null>(null);
  const [zuletzt, setZuletzt] = useState<SicherungStand | null>(null);
  const [fehler, setFehler] = useState("");
  const [gewaehlt, setGewaehlt] = useState("");
  const [alle, setAlle] = useState(false);
  const [fragen, setFragen] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [dialogFehler, setDialogFehler] = useState("");
  const name = useId();

  useEffect(() => {
    // Gerade wiederhergestellt (vor dem Neuladen gemerkt): sagen, welcher Stand gilt, mit dem Weg zurück.
    const stand = holeStand();
    if (stand) zeigeHinweis({
      text: standSatz(stand),
      rueckgaengig: async () => { neuLaden(await api.sicherungWiederherstellen(stand.rueckgaengig)); return "Wird zurückgenommen …"; },
    });
    let aktiv = true;
    api.sicherungen().then(daten => {
      if (!aktiv) return;
      setListe(daten.sicherungen); setZuletzt(daten.zuletzt);
      setGewaehlt(alt => alt || (daten.sicherungen.find(e => e.art !== "vor_wiederherstellung") ?? daten.sicherungen[0])?.name || "");
    }).catch(() => { if (aktiv) setFehler("Die Sicherungen auf diesem Rechner ließen sich gerade nicht lesen. Bitte lade die Seite neu."); });
    return () => { aktiv = false; };
  }, []);

  const eintrag = liste?.find(e => e.name === gewaehlt) ?? null;
  const sichtbar = liste ? sichtbareSicherungen(liste, alle) : [];
  if (eintrag && !sichtbar.includes(eintrag)) sichtbar.push(eintrag);
  const frage = eintrag ? wiederherstellenFrage(eintrag) : null;

  async function wiederherstellen() {
    if (!eintrag) return;
    setArbeitet(true); setDialogFehler("");
    try { neuLaden(await api.sicherungWiederherstellen(eintrag.name)); }
    catch (problem) {
      setDialogFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Nicht wiederhergestellt; es gilt weiter der bisherige Stand. Bitte versuche es noch einmal.");
      setArbeitet(false);
    }
  }

  return <section className="source-section compact-model sicherung-zurueck" aria-labelledby={`${name}-titel`}>
    <div className="compact-integration-heading"><div><h2 id={`${name}-titel`}>Stand wiederherstellen</h2>
      <p>{zuletzt ? standSatz(zuletzt) + ` Wiederhergestellt am ${sicherungZeit(zuletzt.am, true)}.` : "Kingfisher sichert alle vier Stunden auf diesem Rechner. Wähle einen Stand, zu dem du zurückwillst."}</p></div></div>
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
    {!liste && !fehler ? <p role="status" className="source-hint">Sicherungen werden gelesen …</p> : null}
    {liste && !liste.length ? <p className="source-hint">Noch keine Sicherung auf diesem Rechner. Die erste entsteht von selbst, sobald Kingfisher eine Weile läuft.</p> : null}
    {liste && liste.length ? <form onSubmit={e => { e.preventDefault(); if (eintrag) { setDialogFehler(""); setFragen(true); } }}>
      <fieldset className="sicherung-liste">
        <legend className="source-hint">Sicherungen auf diesem Rechner</legend>
        {sichtbar.map(e => <label key={e.name} className="sicherung-wahl">
          <input type="radio" name={name} value={e.name} checked={gewaehlt === e.name} onChange={() => setGewaehlt(e.name)} />
          <span><strong>{sicherungZeit(e.erstellt)}</strong><small>{sicherungArt(e.art)}</small></span>
        </label>)}
      </fieldset>
      <div className="sicherung-knoepfe">
        {liste.length > sichtbar.length || alle ? <button type="button" className="g-knopf-schlicht" aria-expanded={alle} onClick={() => setAlle(w => !w)}>{alle ? "Weniger zeigen" : `Alle ${liste.length} zeigen`}</button> : <span />}
        <button type="submit" className="g-knopf-getoent" aria-disabled={!eintrag || undefined}>Wiederherstellen …</button>
      </div>
    </form> : null}
    {fragen && frage ? <Rueckfrage frage={frage.frage} satz={frage.satz} bestaetigen={arbeitet ? "Wird wiederhergestellt …" : "Wiederherstellen"}
      arbeitet={arbeitet} fehler={dialogFehler || undefined}
      onAbbrechen={() => { setFragen(false); setDialogFehler(""); }} onBestaetigen={() => void wiederherstellen()} /> : null}
  </section>;
}
