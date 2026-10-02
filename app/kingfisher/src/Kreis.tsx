import { useEffect, useState } from "react";
import { ApiError, api } from "./api";
import { aktePfad, artSatz, kreisGespeichert, kreisSatz, offeneKollegen, sammelFrage, sammelKnopf, sammlungSatz, uebersichtSatz, type ArtStand, type KreisStand, type KreisUebersicht } from "./kreis";
import { navigate } from "./ui";
import "./Kreis.css";

function fehlerText(e: unknown, sonst: string): string {
  return e instanceof ApiError && e.detail ? e.detail : sonst;
}

/**
 * Die Karte „Kreis“ in der Akte einer Person: Vorschlag mit Begründung in einem Satz, drei Knöpfe. Erst der Klick legt
 * den Kreis fest; ein bestätigter Kreis bleibt, bis du ihn änderst (docs/49-kreis-und-privat.md).
 */
export function KreisKarte({ sache }: { sache: string }) {
  const [stand, setStand] = useState<KreisStand | null>(null);
  const [hinweis, setHinweis] = useState("");
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);

  useEffect(() => {
    let aktiv = true;
    setStand(null); setHinweis(""); setFehler("");
    api.kreis(sache).then(daten => { if (aktiv) setStand(daten); })
      .catch(e => { if (aktiv) setFehler(fehlerText(e, "Der Kreis ließ sich gerade nicht laden.")); });
    return () => { aktiv = false; };
  }, [sache]);

  async function waehlen(kreis: KreisStand["vorschlag"]["kreis"] | null) {
    setArbeitet(true); setFehler(""); setHinweis("");
    try {
      const neu = kreis ? await api.kreisBestaetigen(sache, kreis) : await api.kreisZuruecknehmen(sache);
      setStand(neu); setHinweis(kreisGespeichert(neu));
    } catch (e) { setFehler(fehlerText(e, "Das ließ sich gerade nicht speichern. Bitte noch einmal versuchen.")); }
    finally { setArbeitet(false); }
  }

  if (!stand) return fehler ? <section className="mappe-teil akte-teil kreis-karte"><h3>Kreis</h3><p role="alert" className="kreis-fehler">{fehler}</p></section> : null;
  return <section className="mappe-teil akte-teil kreis-karte" aria-label="Kreis">
    <h3>Kreis</h3>
    <p className="kreis-satz">{kreisSatz(stand)}</p>
    {stand.ohne_vorschlag ? null : <p className="kreis-warum">Warum: {stand.vorschlag.begruendung}</p>}
    <div className="kreis-wahlen" role="group" aria-label="Kreis wählen">
      {stand.wahlen.map(w => {
        const gewaehlt = stand.bestaetigt && stand.kreis === w.kreis;
        const vorgeschlagen = !stand.bestaetigt && !stand.ohne_vorschlag && stand.vorschlag.kreis === w.kreis;
        return <button key={w.kreis} type="button" disabled={arbeitet || gewaehlt} aria-pressed={gewaehlt}
          className={vorgeschlagen ? "primary-action" : "secondary-action"} title={w.wirkung} onClick={() => void waehlen(w.kreis)}>
          {w.text}{vorgeschlagen ? <small>vorgeschlagen</small> : gewaehlt ? <small>bestätigt</small> : null}
        </button>;
      })}
    </div>
    {stand.bestaetigt ? <button type="button" className="chronik-mehr kreis-zurueck" disabled={arbeitet} onClick={() => void waehlen(null)}>Wieder offen lassen</button> : null}
    <p className="kreis-hilfe">Der Kreis bestimmt nur, wie viel Kingfisher dir ungefragt über diese Person sagt und wie zurückhaltend. Es verlässt nichts deinen Rechner.</p>
    {hinweis ? <p role="status" className="kreis-ok">{hinweis}</p> : null}
    {fehler ? <p role="alert" className="kreis-fehler">{fehler}</p> : null}
  </section>;
}

/** Die Karte „Art der Akte“ für Praxis, Versicherung, Vermieter, Schule: nur wenn es einen Vorschlag gibt oder eine Wahl. */
export function ArtKarte({ sache }: { sache: string }) {
  const [stand, setStand] = useState<ArtStand | null>(null);
  const [hinweis, setHinweis] = useState("");
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);

  useEffect(() => {
    let aktiv = true;
    setStand(null); setHinweis(""); setFehler("");
    api.aktenArt(sache).then(daten => { if (aktiv) setStand(daten); }).catch(() => { /* ohne Art bleibt die Akte, wie sie ist */ });
    return () => { aktiv = false; };
  }, [sache]);

  async function waehlen(art: ArtStand["wahlen"][number]["art"]) {
    setArbeitet(true); setFehler(""); setHinweis("");
    try {
      const neu = await api.aktenArtBestaetigen(sache, art);
      setStand(neu);
      setHinweis(art === "keine" ? "Gespeichert: keine private Akte. Kingfisher sucht hier keine Fristen mehr." : `Gespeichert: ${neu.art_text}.`);
    } catch (e) { setFehler(fehlerText(e, "Das ließ sich gerade nicht speichern. Bitte noch einmal versuchen.")); }
    finally { setArbeitet(false); }
  }

  const satz = stand ? artSatz(stand) : null;
  if (!stand || !satz) return null;
  return <section className="mappe-teil akte-teil kreis-karte" aria-label="Art der Akte">
    <h3>Art der Akte</h3>
    <p className="kreis-satz">{satz}</p>
    {stand.vorschlag.art ? <p className="kreis-warum">Warum: {stand.vorschlag.begruendung}</p> : null}
    <div className="kreis-wahlen" role="group" aria-label="Art wählen">
      {stand.wahlen.map(w => {
        const gewaehlt = stand.bestaetigt && stand.art === w.art;
        const vorgeschlagen = !stand.bestaetigt && stand.vorschlag.art === w.art;
        return <button key={w.art} type="button" disabled={arbeitet || gewaehlt} aria-pressed={gewaehlt}
          className={vorgeschlagen ? "primary-action" : "secondary-action"} onClick={() => void waehlen(w.art)}>
          {w.text}{vorgeschlagen ? <small>vorgeschlagen</small> : gewaehlt ? <small>bestätigt</small> : null}
        </button>;
      })}
    </div>
    <p className="kreis-hilfe">Aus Mails dieser Akte und ihren PDF-Anhängen schlägt Kingfisher Kündigungs- und Zahlungsfristen als Aufgaben vor, nur mit Datum und Betrag, die so in der Quelle stehen.</p>
    {hinweis ? <p role="status" className="kreis-ok">{hinweis}</p> : null}
    {fehler ? <p role="alert" className="kreis-fehler">{fehler}</p> : null}
  </section>;
}

/** Unter „Kingfisher und du“: wie viele Personen bestätigt sind, wie viele Vorschläge offen, und welche (mit Weg zur Akte). */
export function KreisStandAnzeige() {
  const [stand, setStand] = useState<KreisUebersicht | null>(null);
  const [fehler, setFehler] = useState("");
  const [frage, setFrage] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [meldung, setMeldung] = useState("");
  const [runde, setRunde] = useState(0);
  useEffect(() => {
    let aktiv = true;
    let zeitgeber: ReturnType<typeof setTimeout> | null = null;
    // Zählt der Sidecar noch (Abgleich im Hintergrund), fragt die Karte in kurzen Abständen nach, bis die Zahl steht.
    const laden = () => api.kreisUebersicht().then(daten => {
      if (!aktiv) return;
      setStand(daten);
      if (daten.zaehlt_noch) zeitgeber = setTimeout(laden, 1500);
    }).catch(e => { if (aktiv) setFehler(fehlerText(e, "Der Stand der Kreise ließ sich gerade nicht laden.")); });
    laden();
    return () => { aktiv = false; if (zeitgeber) clearTimeout(zeitgeber); };
  }, [runde]);

  // Sammelbestätigung nur für Kollegen: eine Rückfrage in einem Satz, danach rückgängig machbar.
  async function sammeln(anzahl: number) {
    setArbeitet(true); setFehler(""); setMeldung("");
    try { setMeldung((await api.kreisSammeln(anzahl)).satz); setFrage(false); setRunde(r => r + 1); }
    catch (e) { setFehler(fehlerText(e, "Das ließ sich gerade nicht speichern. Bitte noch einmal versuchen.")); setFrage(false); setRunde(r => r + 1); }
    finally { setArbeitet(false); }
  }
  async function zuruecknehmen(sammlung: number) {
    setArbeitet(true); setFehler(""); setMeldung("");
    try { setMeldung((await api.kreisSammlungZurueck(sammlung)).satz); setRunde(r => r + 1); }
    catch (e) { setFehler(fehlerText(e, "Das ließ sich gerade nicht zurücknehmen. Bitte noch einmal versuchen.")); }
    finally { setArbeitet(false); }
  }

  if (fehler && !stand) return <p role="alert" className="settings-error">{fehler}</p>;
  if (!stand) return <p className="source-hint">Wird gezählt …</p>;
  const kollegen = offeneKollegen(stand);
  return <div className="kreis-stand">
    <p className="source-hint" role="status">{uebersichtSatz(stand)}</p>
    <OffeneListe eintraege={stand.vorschlaege.filter(v => v.kreis === "innerer_kreis")} />
    {kollegen > 0 && !stand.zaehlt_noch ? <div className="kreis-sammel">
      {frage ? <div className="kreis-frage" role="group" aria-label="Rückfrage">
        <p>{sammelFrage(kollegen)}</p>
        <div className="kreis-wahlen">
          <button type="button" className="primary-action" disabled={arbeitet} onClick={() => void sammeln(kollegen)}>Ja, festlegen</button>
          <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => setFrage(false)}>Abbrechen</button>
        </div>
      </div> : <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => { setMeldung(""); setFrage(true); }}>{sammelKnopf(kollegen)}</button>}
    </div> : null}
    {stand.letzte_sammlung ? <div className="kreis-sammel">
      <p className="source-hint">{sammlungSatz(stand.letzte_sammlung)}</p>
      <button type="button" className="chronik-mehr" disabled={arbeitet} onClick={() => void zuruecknehmen(stand.letzte_sammlung!.sammlung)}>Liste zurücknehmen</button>
    </div> : null}
    {meldung ? <p role="status" className="kreis-ok">{meldung}</p> : null}
    {fehler ? <p role="alert" className="kreis-fehler">{fehler}</p> : null}
    {stand.vorschlaege.some(v => v.kreis === "kollegen") ? <details className="kreis-mehr">
      <summary>Vorschläge für Kollegen zeigen</summary>
      <OffeneListe eintraege={stand.vorschlaege.filter(v => v.kreis === "kollegen")} />
    </details> : null}
    {stand.offen > stand.vorschlaege.length ? <p className="source-hint">{stand.offen - stand.vorschlaege.length} weitere Vorschläge stehen in den Akten.</p> : null}
  </div>;
}

function OffeneListe({ eintraege }: { eintraege: KreisUebersicht["vorschlaege"] }) {
  if (!eintraege.length) return null;
  return <ul className="kreis-offen" aria-label="Offene Vorschläge">
    {eintraege.map(v => <li key={v.sache}>
      <button type="button" className="secondary-action" onClick={() => navigate(aktePfad(v.sache))}>
        {v.name}<small>Vorschlag: {v.kreis_text} · {v.begruendung}</small>
      </button>
    </li>)}
  </ul>;
}

/** „Steht an“ in der Akte einer Person: ihr bestätigter Geburtstag, sonst nichts (Fremdprobe 2, Befund 20). */
export function GeburtstagKarte({ sache }: { sache: string }) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    let aktiv = true;
    setText(null);
    api.geburtstag(sache).then(daten => { if (aktiv) setText(daten.geburtstag?.text ?? null); }).catch(() => { /* ohne Geburtstag bleibt die Akte, wie sie ist */ });
    return () => { aktiv = false; };
  }, [sache]);
  if (!text) return null;
  return <section className="mappe-teil akte-teil kreis-karte" aria-label="Steht an">
    <h3>Steht an</h3>
    <p className="kreis-satz">{text}.</p>
    <p className="kreis-hilfe">Er steht auch im Kalender, jedes Jahr wieder, nur in Kingfisher; in keinen anderen Kalender geschrieben.</p>
  </section>;
}
