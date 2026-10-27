import { useEffect, useState } from "react";
import { Schalter } from "./grundlage";
import { api, type AntwortZeitenProtokoll } from "./api";
import { gueltigeZeiten, protokollSatz, protokollZeilen, ursacheSatz, zeitZeile } from "./antwortzeit";
import { pruefungSchalterSatz } from "./pruefHinweis";
import "./AntwortZeiten.css";

/**
 * Die Zeile unter einer Antwort: „3,2 s · Suche 0,3 · Sätze 2,1“. Nebeninformation, keine Farbe, nichts Blinkendes.
 * Ohne gemessene Zeiten (ältere Antworten, Antworten ohne Modell) steht nichts da. Wurde die Antwort langsam,
 * steht ein Satz mit der Ursache darunter.
 *
 * Die Zahlen sagen nur Technikern etwas (Persona-Prüfung, Paket S, Befund 2): Sie liegen hinter einem zugeklappten
 * „Details“. Dass es lokal dauert, sagt der Hinweis darüber in Worten (`LokalLangsam`).
 */
export function AntwortZeile({ zeiten }: { zeiten: unknown }) {
  const gemessen = gueltigeZeiten(zeiten);
  if (!gemessen) return null;
  const ursache = ursacheSatz(gemessen);
  return <details className="antwortzeit-details">
    <summary>Details</summary>
    <p className="antwortzeit" aria-label="Antwortzeit">{zeitZeile(gemessen)}
      {ursache ? <span className="antwortzeit-ursache">{ursache}</span> : null}</p>
  </details>;
}

/**
 * Einstellungen, Lokale KI: das Protokoll der letzten 50 Antwortzeiten und der Schalter für die Sätze. Der
 * Schalter steht hier, weil die Entscheidung nach der Zahl fällt: Wer sieht, dass der zweite Modellaufruf
 * zu lange dauert, schaltet ihn ab und behält die wörtlichen Belege.
 */
export function AntwortZeitenProtokoll() {
  const [daten, setDaten] = useState<AntwortZeitenProtokoll | null>(null);
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [hinweis, setHinweis] = useState("");

  useEffect(() => {
    let aktiv = true;
    api.antwortzeiten().then(stand => { if (aktiv) setDaten(stand); })
      .catch(() => { if (aktiv) setFehler("Die Antwortzeiten konnten nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);

  async function umschalten(an: boolean) {
    if (!daten) return;
    setArbeitet(true); setFehler(""); setHinweis("");
    try {
      const stand = await api.saetzeSetzen(an ? "an" : "aus");
      setDaten({ ...daten, saetze: stand.saetze });
      setHinweis(stand.saetze === "an" ? "Antworten erscheinen wieder in Sätzen." : "Antworten zeigen ab der nächsten Frage die Belege wörtlich.");
    } catch {
      setFehler("Das konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally { setArbeitet(false); }
  }

  async function pruefungUmschalten(an: boolean) {
    if (!daten) return;
    setArbeitet(true); setFehler(""); setHinweis("");
    try {
      const stand = await api.satzpruefungSetzen(an ? "an" : "aus");
      setDaten({ ...daten, pruefung: stand });
      setHinweis(stand.schalter === "an" ? "Das Prüfmodell prüft ab der nächsten Frage wieder jeden Satz." : "Ab der nächsten Frage prüft kein Prüfmodell mehr mit.");
    } catch {
      setFehler("Das konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally { setArbeitet(false); }
  }

  const zeilen = daten ? protokollZeilen(daten) : [];
  const pruefung = daten?.pruefung;
  return <section className="source-section antwortzeiten" aria-label="Antwortzeiten">
    <div className="compact-integration-heading"><div><h2>Antwortzeit</h2>
      <p>{daten ? protokollSatz(daten) : fehler || "Wird geladen …"}</p></div></div>
    {zeilen.length ? <table className="antwortzeiten-tabelle">
      <caption className="visually-hidden">Median und 90-Prozent-Wert der letzten Antworten in Sekunden</caption>
      <thead><tr><th scope="col">Abschnitt</th><th scope="col">Median</th><th scope="col">90 %-Wert</th></tr></thead>
      <tbody>{zeilen.map(zeile => <tr key={zeile.name} className={zeile.name === "gesamt" ? "ist-gesamt" : undefined}>
        <th scope="row">{zeile.titel}</th><td>{zeile.median} s</td><td>{zeile.p90} s</td></tr>)}</tbody>
    </table> : null}
    {daten ? <p className="source-hint">
      Antworten formuliert: {daten.modelle.antwort ?? "kein Modell eingerichtet"}. Fragen verstanden: {daten.modelle.frage ?? "ohne Modell"}.
    </p> : null}
    {daten ? <Schalter className="antwortzeiten-schalter" titel="Antworten in Sätzen formulieren" an={daten.saetze === "an"} deaktiviert={arbeitet}
      satz="Ein zweiter Modellaufruf schreibt die Antwort in Sätzen mit Belegnummern. Aus: Kingfisher zeigt die Belege wörtlich und spart diese Wartezeit."
      onWechsel={an => void umschalten(an)} /> : null}
    {pruefung ? <Schalter className="antwortzeiten-schalter" titel="Sätze vom Prüfmodell gegenprüfen" satz={pruefungSchalterSatz(pruefung)}
      an={pruefung.schalter === "an" && pruefung.zustand !== "kein_modell"} deaktiviert={arbeitet || pruefung.zustand === "kein_modell"}
      onWechsel={an => void pruefungUmschalten(an)} /> : null}
    {hinweis ? <p role="status" className="source-hint">{hinweis}</p> : null}
    {fehler && daten ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </section>;
}
