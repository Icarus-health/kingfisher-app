import {useCallback, useEffect, useRef, useState} from "react";
import {api, ApiError, type ModelRecommendation, type ModellLaden} from "../api";
import {watchPull} from "../modelSetup";
import {Verweis} from "../VerweisLink";
import {FAEHIGKEITEN, OHNE_OLLAMA, OLLAMA_DOWNLOAD, abschluss, ausstattungSatz, faehigkeitStand, laeufeAus, ladeSatz,
  ladenLaeuftSatz, laufAus, naechsteWahl, offeneRollen, probleme, type Lauf} from "./rechner";

const fehlerText = (fehler: unknown) => fehler instanceof ApiError && fehler.detail ? fehler.detail
  : "Kingfisher ist gerade nicht erreichbar. Bitte versuche es in einem Moment noch einmal.";

/**
 * „Dieser Rechner“ im Assistenten (Fremdprobe, Befunde 10 und 11; Fremdprobe 2, Befunde 6 und 7): was Kingfisher hier
 * kann, wie groß das Laden ist und wie lange es dauert, ein Knopf. Das Laden läuft im Sidecar im Hintergrund weiter
 * (`POST /api/v1/models/laden`); der Mensch geht sofort weiter, Heute zeigt den Fortschritt. Die Größe kommt aus einer
 * Quelle (`orchester.festplatte_noch_gb`). Am Ende steht genau ein Satz: alles, teilweise oder nichts eingerichtet.
 * Besteht ein Modell die Prüfung nicht, versucht „Anderes Modell nehmen“ das nächste, das passt. Modellnamen stehen
 * nur im Aufklapper „Für Techniker“.
 */
export function RechnerKarte({beiFertig, beiLaden}: {beiFertig?: () => void; beiLaden?: (laeuft: boolean) => void}) {
  const [daten, setDaten] = useState<ModelRecommendation | null>(null);
  const [ladefehler, setLadefehler] = useState(false);
  const [laden, setLaden] = useState<ModellLaden | null>(null);
  const [einzeln, setEinzeln] = useState<Record<string, Lauf>>({});
  const [versucht, setVersucht] = useState<Record<string, string[]>>({});
  const [arbeitet, setArbeitet] = useState(false);
  const [meldung, setMeldung] = useState<{ok: boolean; text: string} | null>(null);
  const lebt = useRef(true);
  const vorher = useRef<boolean | null>(null);
  const meldeLaden = useRef(beiLaden);
  meldeLaden.current = beiLaden;
  const meldeFertig = useRef(beiFertig);
  meldeFertig.current = beiFertig;

  const empfehlung = useCallback(async () => {
    try { const neu = await api.modelRecommendation(); if (lebt.current) { setDaten(neu); setLadefehler(false); } return neu; }
    catch { if (lebt.current) setLadefehler(true); return null; }
  }, []);
  useEffect(() => { lebt.current = true; void empfehlung(); return () => { lebt.current = false; }; }, [empfehlung]);

  // Der Lauf im Hintergrund: nachsehen, solange er läuft (auch nach dem Neuladen der Seite); endet er, einmal die
  // Empfehlung neu lesen, damit „Bereit“ an den Fähigkeiten stimmt.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function lesen() {
      const stand = await api.modellLaden().catch(() => null);
      if (!lebt.current) return;
      if (stand) {
        setLaden(stand);
        if (vorher.current !== stand.laeuft) {
          if (vorher.current === true && !stand.laeuft) { void empfehlung(); meldeFertig.current?.(); }
          vorher.current = stand.laeuft;
          meldeLaden.current?.(stand.laeuft);
        }
      }
      timer = setTimeout(lesen, stand?.laeuft ? 1500 : 6000);
    }
    void lesen();
    return () => clearTimeout(timer);
  }, [empfehlung]);

  async function allesLaden() {
    if (arbeitet) return;
    setArbeitet(true); setMeldung(null); setEinzeln({});
    try {
      const stand = await api.modelleLaden();
      setLaden(stand); vorher.current = stand.laeuft; meldeLaden.current?.(stand.laeuft);
    } catch (fehler) {
      setMeldung({ok: false, text: fehlerText(fehler)});
    } finally { setArbeitet(false); }
  }

  async function anderesModell(rolle: string, modell: string) {
    if (arbeitet) return;
    setArbeitet(true); setMeldung(null);
    try {
      const start = await api.startModelPull(rolle, modell);
      setVersucht(alt => ({...alt, [rolle]: [...(alt[rolle] ?? []), start.modell]}));
      setEinzeln(alt => ({...alt, [rolle]: laufAus(start)}));
      const ende = await watchPull({read: () => api.modelPull(start.id), onState: stand => setEinzeln(alt => ({...alt, [rolle]: laufAus(stand)})), isStopped: () => !lebt.current});
      await empfehlung();
      if (ende?.phase === "fertig") { setMeldung({ok: true, text: "Eingerichtet und geprüft."}); meldeFertig.current?.(); }
    } catch (fehler) {
      setEinzeln(alt => ({...alt, [rolle]: {phase: "fehler", prozent: null, nichtBestanden: false, satz: fehlerText(fehler), modell}}));
    } finally { setArbeitet(false); }
  }

  if (!daten) return <section className="rechner-karte" aria-label="Was Kingfisher auf diesem Rechner kann">
    {ladefehler ? <p role="alert">Das konnte gerade nicht geladen werden. <button className="secondary-action" type="button" onClick={() => void empfehlung()}>Erneut versuchen</button></p>
      : <p role="status">Kingfisher sieht sich diesen Rechner an …</p>}
  </section>;

  const zeilen = daten.rollen;
  const laeufe = {...laeufeAus(laden), ...einzeln};
  const laeuft = Boolean(laden?.laeuft);
  const offen = offeneRollen(zeilen);
  const satz = daten.orchester ? ladeSatz(daten.orchester) : "";
  const erreichbar = daten.ollama.erreichbar;
  const ende = abschluss(laden);
  // Vor dem ersten Lauf „Laden starten“; ist alles fehlgeschlagen, „Noch einmal versuchen“. Sonst stehen die Wege je
  // Fähigkeit darunter (einmal, nicht doppelt).
  const zeigeStart = erreichbar && !laeuft && offen.length > 0 && (ende === null || ende.nochmal);

  return <section className="rechner-karte" aria-label="Was Kingfisher auf diesem Rechner kann">
    <p className="source-hint">{ausstattungSatz(daten.geraet)}</p>
    <ul className="rechner-faehigkeiten">
      {FAEHIGKEITEN.map(faehigkeit => {
        const stand = faehigkeitStand(faehigkeit, zeilen, laeufe);
        return <li key={faehigkeit.id} className={`ist-${stand.art}`}>
          <div><strong>{faehigkeit.titel}</strong><p>{faehigkeit.satz}</p></div>
          <span className="rechner-marke" role="status">{stand.text}</span>
        </li>;
      })}
    </ul>
    {!erreichbar ? <div className="rechner-ohne-ollama" role="status">
      <p>{OHNE_OLLAMA.satz} <a href={OLLAMA_DOWNLOAD} target="_blank" rel="noreferrer">{OHNE_OLLAMA.link}</a>.</p>
      <p className="source-hint">{OHNE_OLLAMA.ohne}</p>
      <button className="secondary-action" type="button" disabled={arbeitet} onClick={() => void empfehlung()}>Erneut prüfen</button>
    </div> : null}
    {laeuft && laden ? <div className="rechner-laden" role="status" aria-live="polite">
      <p>{ladenLaeuftSatz(laden)}</p>
      <progress max={100} value={laden.prozent} aria-label="Sprachmodell wird geladen" />
    </div> : null}
    {zeigeStart ? <div className="rechner-laden">
      {satz ? <p>{satz}</p> : <p>Es muss nichts geladen werden; Kingfisher übernimmt, was schon da ist.</p>}
      <button className="primary-action" type="button" disabled={arbeitet} onClick={() => void allesLaden()}>{arbeitet ? "Wird gestartet …" : ende?.nochmal ? "Noch einmal versuchen" : "Laden starten"}</button>
    </div> : null}
    {meldung ? <p className={meldung.ok ? "erststart-ok" : "source-hint"} role="status">{meldung.text}</p>
      : ende ? <p className={ende.ok ? "erststart-ok" : "source-hint"} role="status">{ende.text}</p> : null}
    {laeuft ? null : probleme(zeilen, laeufe).map(({titel, zeile, lauf}) => {
      const naechste = naechsteWahl(zeile, versucht[zeile.rolle] ?? []);
      return <div key={zeile.rolle} className="rechner-problem" role="alert">
        <p><strong>{titel}:</strong> {lauf.satz}</p>
        {lauf.nichtBestanden
          ? naechste ? <button className="secondary-action" type="button" disabled={arbeitet} onClick={() => void anderesModell(zeile.rolle, naechste.name)}>Anderes Modell nehmen</button>
            : <p className="source-hint">Für diese Aufgabe gibt es auf diesem Rechner keine weitere Wahl. Kingfisher arbeitet ohne sie weiter.</p>
          : <button className="secondary-action" type="button" disabled={arbeitet} onClick={() => void anderesModell(zeile.rolle, lauf.modell || zeile.empfohlen.name)}>Erneut versuchen</button>}
      </div>;
    })}
    <details className="rechner-techniker">
      <summary>Für Techniker</summary>
      <ul>{zeilen.map(zeile => <li key={zeile.rolle}>{zeile.titel}: <code>{laeufe[zeile.rolle]?.modell || zeile.empfohlen.name}</code></li>)}</ul>
      <p className="source-hint">{daten.hinweis} Alles Weitere unter <Verweis ziel="technik-modelle" />.</p>
    </details>
  </section>;
}
