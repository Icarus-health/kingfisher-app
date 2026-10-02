import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import {
  angebot, auftrag, brueckeFinden, fassungText, merken, nachgesehenText, rueckmeldung, SATZ_PRUEFEN, zuletztText,
  type FassungStand,
} from "./fassungsAngebot";
import "./Fassung.css";

/**
 * Fassung und Update-Angebot (docs/53-download-und-updates.md): der ruhige Hinweis auf Heute, die Zeile unter
 * „Kingfisher und du“ und der Weg für Techniker. Die Logik steht in `fassungsAngebot.ts`; hier nur Laden, Klicks und Sätze.
 */
function useFassung() {
  const [stand, setStand] = useState<FassungStand | null>(null);
  const [nachricht, setNachricht] = useState("");
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);

  useEffect(() => {
    let aktiv = true;
    api.fassung().then(daten => {
      if (!aktiv) return;
      setStand(daten);
      // Nach dem Neuladen durch die App: einmal sagen, wie das Update ausging.
      const gesagt = rueckmeldung(daten.fassung);
      if (gesagt) setNachricht(gesagt);
    }).catch(() => { if (aktiv) setFehler("Die Fassung konnte nicht gelesen werden."); });
    return () => { aktiv = false; };
  }, []);

  const ausfuehren = useCallback(async (aktion: () => Promise<FassungStand>, satz: (neu: FassungStand) => string) => {
    setArbeitet(true); setFehler(""); setNachricht("");
    try { const neu = await aktion(); setStand(neu); setNachricht(satz(neu)); }
    catch { setFehler("Das hat nicht geklappt. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }, []);

  return { stand, nachricht, setNachricht, fehler, setFehler, arbeitet, ausfuehren };
}

/** Das Angebot selbst: Überschrift mit der ersten Neuerung, ein Satz, und der Knopf oder der Weg dorthin. */
function Angebot({ stand, beiNachricht }: { stand: FassungStand; beiNachricht: (satz: string, fehler?: boolean) => void }) {
  const bruecke = brueckeFinden();
  const daten = angebot(stand, bruecke !== null);
  const [gesendet, setGesendet] = useState(false);
  if (!daten || !stand.neueste) return null;
  const manifest = stand.neueste;

  function aktualisieren() {
    if (!bruecke) return;
    merken(manifest.fassung, stand.fassung);
    try {
      bruecke.postMessage(auftrag(manifest));
      setGesendet(true);
      beiNachricht(`Kingfisher sichert jetzt deine Daten und wechselt auf Fassung ${manifest.fassung}. Gleich lädt diese Seite neu.`);
    } catch {
      beiNachricht("Die App hat den Auftrag nicht angenommen. Bitte erneut versuchen.", true);
    }
  }

  return <div className="fassung-angebot">
    <p className="fassung-titel">{daten.titel}</p>
    {daten.weg === "app_laden" ? <p className="fassung-satz">{daten.satz}{" "}
      {stand.download_seite ? <a href={stand.download_seite} target="_blank" rel="noreferrer">Zur Download-Seite</a> : null}</p>
      : <p className="fassung-satz">{daten.satz}</p>}
    {daten.weg === "knopf" ? <button type="button" className="secondary-action fassung-knopf" disabled={gesendet} onClick={aktualisieren}>
      Jetzt aktualisieren</button> : null}
  </div>;
}

/** Auf Heute: still, solange es nichts gibt; ein ruhiger Hinweis, wenn eine neue Fassung da ist. */
export function FassungHeute() {
  const { stand, nachricht, setNachricht, fehler, setFehler } = useFassung();
  const melden = (satz: string, istFehler = false) => { if (istFehler) setFehler(satz); else { setFehler(""); setNachricht(satz); } };
  const zeigen = Boolean(stand && angebot(stand, brueckeFinden() !== null));
  if (!zeigen && !nachricht) return null;
  return <section className="fassung-heute" aria-label="Neue Fassung">
    {nachricht ? <p role="status" className="fassung-nachricht">{nachricht}</p> : null}
    {stand && zeigen ? <Angebot stand={stand} beiNachricht={melden} /> : null}
    {fehler && stand ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </section>;
}

/** Einstellungen → Kingfisher und du: welche Fassung läuft, die tägliche Prüfung und „Jetzt nachsehen“. */
export function FassungEinstellung() {
  const { stand, nachricht, setNachricht, fehler, setFehler, arbeitet, ausfuehren } = useFassung();
  const melden = (satz: string, istFehler = false) => { if (istFehler) setFehler(satz); else { setFehler(""); setNachricht(satz); } };
  return <div className="ich-feld fassung-einstellung">
    <strong>{stand ? fassungText(stand.fassung) : "Fassung …"}</strong>
    {stand ? <>
      <label className="wegezeit-schalter"><input type="checkbox" role="switch" checked={stand.pruefen} disabled={arbeitet}
        onChange={event => void ausfuehren(() => api.fassungSchalten(event.target.checked),
          neu => neu.pruefen ? "Kingfisher sieht einmal am Tag nach neuen Fassungen." : "Kingfisher sieht nicht mehr von selbst nach.")} />
        <span><strong>Nach neuen Fassungen sehen</strong><small>{SATZ_PRUEFEN}</small></span></label>
      <div><button type="button" className="secondary-action" disabled={arbeitet}
        onClick={() => void ausfuehren(api.fassungPruefen, nachgesehenText)}>{arbeitet ? "Sieht nach …" : "Jetzt nachsehen"}</button></div>
      <p className="source-hint">{zuletztText(stand.geprueft_um)}</p>
    </> : null}
    {nachricht ? <p role="status" className="source-hint">{nachricht}</p> : null}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
    {stand ? <Angebot stand={stand} beiNachricht={melden} /> : null}
  </div>;
}
