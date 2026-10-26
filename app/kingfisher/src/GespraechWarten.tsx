import { useEffect, useState } from "react";
import "./GespraechWarten.css";
import { api, type GespraechFortschritt } from "./api";
import { MessageText } from "./MessageText";
import { navigate } from "./ui";
import {
  ABFRAGE_MS, cloudVermerk, LANGSAM_KNOPF, LANGSAM_SATZ, LANGSAM_WEG, langsamHinweis, warteSatz, weggeklickt, wegklicken,
} from "./wartenImGespraech.ts";

/**
 * Warten im Gespräch (Paket T): die eigene Frage sofort, darunter der echte Schritt aus dem Sidecar
 * („Sucht in deinen Quellen …“, „Wählt Quellen …“, „Formuliert …“). Keine Zeitangabe, nichts blinkt; der Punkt atmet
 * nur, solange etwas läuft, und nie bei „weniger Bewegung“.
 */
export function AusstehendeFrage({ text }: { text: string }) {
  return <article className="message user ausstehend" aria-busy="true">
    <span className="message-wer">Du</span><MessageText content={text} />
  </article>;
}

export function WarteZeile({ gespraech }: { gespraech: string | null }) {
  const [stand, setStand] = useState<GespraechFortschritt | null>(null);
  useEffect(() => {
    if (!gespraech) return;
    let aktiv = true;
    let zeit: number | undefined;
    const fragen = async () => {
      try { const neu = await api.gespraechFortschritt(gespraech); if (aktiv) setStand(neu); }
      catch { /* der Stand ist eine Hilfe; ohne ihn bleibt „Kingfisher antwortet …“ */ }
      if (aktiv) zeit = window.setTimeout(fragen, ABFRAGE_MS);
    };
    void fragen();
    return () => { aktiv = false; if (zeit !== undefined) window.clearTimeout(zeit); };
  }, [gespraech]);
  return <p className="conversation-waiting warte-zeile" role="status" aria-live="polite">
    <span className="warte-punkt" aria-hidden="true" />{warteSatz(stand)}
  </p>;
}

/** Zum Schalter „Cloud für Fragen und Antworten nutzen“; die Einwilligung bleibt dort. */
export function zumCloudSchalter() {
  navigate("/settings#darf");
  let versuche = 0;
  const suchen = () => {
    const schalter = document.getElementById("darf-cloud");
    if (schalter) {
      schalter.scrollIntoView({ block: "center" });
      schalter.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
    } else if (++versuche < 40) window.setTimeout(suchen, 50);
  };
  window.setTimeout(suchen, 0);
}

/** Unter einer langsamen lokalen Antwort, wenn die Cloud aus ist: ein Satz, ein Knopf zum Schalter, einmal wegklickbar. */
export function LokalLangsam({ kontext, cloudAn }: { kontext: Parameters<typeof langsamHinweis>[0]; cloudAn: boolean | null }) {
  const [weg, setWeg] = useState(() => weggeklickt());
  if (!langsamHinweis(kontext, { cloudAn, weggeklickt: weg })) return null;
  return <p className="lokal-langsam">
    <span>{LANGSAM_SATZ}</span>
    <span className="lokal-langsam-knoepfe">
      <button className="g-knopf-getoent g-kompakt" type="button" onClick={zumCloudSchalter}>{LANGSAM_KNOPF}</button>
      <button className="g-knopf-schlicht g-kompakt" type="button" onClick={() => { wegklicken(); setWeg(true); }}>{LANGSAM_WEG}</button>
    </span>
  </p>;
}

/** Unter einer Gedächtnisantwort aus der Cloud: über wen sie lief (die Frage und die Textstellen gingen dorthin). */
export function CloudVermerk({ kontext }: { kontext: Parameters<typeof cloudVermerk>[0] }) {
  const satz = cloudVermerk(kontext);
  return satz ? <p className="antwortzeit cloud-vermerk">{satz}</p> : null;
}
