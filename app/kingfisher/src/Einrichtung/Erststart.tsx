import {useEffect, useRef, useState, type ComponentType} from "react";
import type {EinrichtungAenderung, EinrichtungSchritt} from "../api";
import {ASSET, navigate} from "../ui";
import {AutostartSchritt} from "./AutostartSchritt";
import {FertigSchritt} from "./FertigSchritt";
import {FreigabenSchritt} from "./FreigabenSchritt";
import {KalenderSchritt} from "./KalenderSchritt";
import {MailSchritt} from "./MailSchritt";
import {ModellSchritt} from "./ModellSchritt";
import {NameSchritt} from "./NameSchritt";
import {SCHRITTE, nachbar, schrittStand, schrittZaehler, sichtbareSchritte, startSchritt} from "./schritte";
import type {SchrittProps} from "./SchrittFuss";
import {useEinrichtung} from "./useEinrichtung";
import {ERSTSTART_SPAETER} from "./useErststartWeiterleitung";
import "./Einrichtung.css";

const INHALT: Record<EinrichtungSchritt, ComponentType<SchrittProps>> = {
  name: NameSchritt, mail: MailSchritt, kalender: KalenderSchritt, modell: ModellSchritt, freigaben: FreigabenSchritt, autostart: AutostartSchritt, fertig: FertigSchritt,
};

// Schritte, bei denen sich draußen etwas ändern kann (Anmeldung, Freigabe, Download): Der Stand wird nachgesehen.
const NACHSEHEN: EinrichtungSchritt[] = ["mail", "kalender", "modell"];

/** Der geführte Erststart unter /willkommen. Jeder Schritt lässt sich überspringen; der Stand liegt im Sidecar. */
export function Erststart() {
  const {stand, fehler, laden, aendern} = useEinrichtung();
  const [aktuell, setAktuell] = useState<EinrichtungSchritt | null>(null);
  const [meldung, setMeldung] = useState("");
  // Was im aktuellen Schritt getippt, aber noch nicht gespeichert ist (der Name). Wer den Schritt verlässt,
  // ohne „Weiter“ zu drücken, verliert es nicht (Fremdprobe, Befund 21).
  const entwurf = useRef<EinrichtungAenderung | null>(null);

  // Beim ersten Stand: dort weitermachen, wo man aufgehört hat, oder beim Schritt aus der Adresse (?schritt=mail).
  useEffect(() => {
    if (stand && aktuell === null) setAktuell(startSchritt(stand, new URLSearchParams(window.location.search).get("schritt")));
  }, [stand, aktuell]);

  useEffect(() => {
    if (!aktuell || !NACHSEHEN.includes(aktuell)) return;
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void laden(); }, 4000);
    return () => window.clearInterval(timer);
  }, [aktuell, laden]);

  async function entwurfSichern() {
    const offen = entwurf.current;
    if (!offen) return true;
    entwurf.current = null;
    if (await aendern(offen)) return true;
    entwurf.current = offen;
    return false;
  }
  function gehe(id: EinrichtungSchritt) {
    void entwurfSichern();
    setAktuell(id); setMeldung("");
    window.history.replaceState({}, "", `/willkommen?schritt=${id}`);
    window.scrollTo({top: 0});
  }
  async function merken(id: EinrichtungSchritt, wie: "erledigt" | "uebersprungen", zusatz?: EinrichtungAenderung) {
    const antwort = await aendern({...zusatz, schritt: {id, stand: wie}});
    if (!antwort) { setMeldung("Das konnte gerade nicht gespeichert werden. Bitte versuche es noch einmal."); return false; }
    return true;
  }
  const weiterVon = (id: EinrichtungSchritt) => async (zusatz?: EinrichtungAenderung) => {
    entwurf.current = null;  // was getippt war, steckt in `zusatz`
    if (!await merken(id, "erledigt", zusatz)) return;
    // „Zum Briefing“ öffnet das Briefing selbst, nicht nur die Startseite (Befund 23).
    if (id === "fertig") navigate("/today?briefing=1"); else gehe(nachbar(id, 1, stand));
  };
  const ueberspringenVon = (id: EinrichtungSchritt) => async () => {
    // Was schon da ist, wird nicht als „übersprungen“ vermerkt.
    if (stand && schrittStand(id, stand) === "offen" && !await merken(id, "uebersprungen")) return;
    gehe(nachbar(id, 1, stand));
  };
  async function spaeter() {
    if (!await entwurfSichern()) { setMeldung("Das Getippte konnte gerade nicht gespeichert werden. Bitte versuche es noch einmal."); return; }
    try { sessionStorage.setItem(ERSTSTART_SPAETER, "1"); } catch { /* ohne Speicher fragt die Startseite eben erneut */ }
    navigate("/today");
  }

  const Inhalt = aktuell ? INHALT[aktuell] : null;
  const info = SCHRITTE.find(schritt => schritt.id === aktuell);
  const zaehler = aktuell ? schrittZaehler(aktuell, stand) : null;
  const schritte = sichtbareSchritte(stand);
  return <div className="shell erststart-shell">
    <main className="erststart">
      <header className="erststart-kopf">
        <img src={`${ASSET.media}kingfisher-flight-clean-v1.png`} alt="" />
        <p className="eyebrow">WILLKOMMEN BEI KINGFISHER</p>
        <button type="button" className="text-action" onClick={() => void spaeter()}>Später weitermachen</button>
      </header>
      <nav aria-label="Schritte der Einrichtung"><ol className="erststart-punkte">
        {schritte.map(schritt => {
          const gemacht = stand ? schrittStand(schritt.id, stand) : "offen";
          return <li key={schritt.id}>
            <button type="button" className={`erststart-punkt ist-${gemacht}${schritt.id === aktuell ? " ist-aktuell" : ""}`}
              aria-current={schritt.id === aktuell ? "step" : undefined} disabled={!stand} onClick={() => gehe(schritt.id)}>
              <span className="erststart-marke" aria-hidden="true">{gemacht === "erledigt" ? "✓" : ""}</span>
              <span className="erststart-punkt-name">{schritt.kurz}</span>
              <span className="visually-hidden">{gemacht === "erledigt" ? " (erledigt)" : gemacht === "uebersprungen" ? " (übersprungen)" : ""}</span>
            </button></li>;
        })}
      </ol></nav>
      <section className="erststart-karte" aria-labelledby="erststart-titel">
        {fehler && !stand ? <p role="alert">Kingfisher ist gerade nicht erreichbar. <button className="text-action" type="button" onClick={() => void laden()}>Erneut versuchen</button></p> : null}
        {!stand && !fehler ? <p role="status">Wird geladen …</p> : null}
        {stand && info && Inhalt ? <>
          {zaehler ? <p className="erststart-zaehler">Schritt {zaehler.nummer} von {zaehler.gesamt}</p> : null}
          <h1 id="erststart-titel">{info.titel}</h1>
          <Inhalt key={info.id} stand={stand} neuLesen={laden} weiter={weiterVon(info.id)} ueberspringen={ueberspringenVon(info.id)}
            zurueck={info.id === SCHRITTE[0].id ? null : () => gehe(nachbar(info.id, -1, stand))}
            gehe={gehe} entwurf={aenderung => { entwurf.current = aenderung; }} />
          {meldung ? <p role="alert" className="settings-error">{meldung}</p> : null}
        </> : null}
      </section>
    </main>
  </div>;
}
