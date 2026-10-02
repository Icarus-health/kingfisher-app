import { useCallback, useEffect, useRef, useState } from "react";
import { api, type TagAktion, type TagBriefing } from "./api";
import { ProfileSource } from "./ProfileSource";
import { Logbuch } from "./Logbuch";
import { navigate } from "./ui";
import { TerminVorbereitung } from "./TerminVorbereitung";
import "./TagesLage.css";

// Das Morgenbriefing in drei bis fünf Zeilen: ein Urteil, keine Liste. Jede Zeile hat ihre Aktion
// (Vorbereitung öffnen, Quelle öffnen); was fehlt oder nicht belegt ist, steht nicht da. Die Vorbereitung
// der Termine entsteht ohne Klick im Sidecar (tag_routes.py); hier wird nur gezeigt und gefragt.
const KOPF: Record<string, string> = { termin: "Wohin", leute: "Wer kommt", einpacken: "Einpacken", fristen: "Fristen", wetter: "Wetter", geburtstag: "Geburtstag", welt: "Welt" };

export function TagesLage() {
  const [daten, setDaten] = useState<TagBriefing | null>(null);
  const [fehler, setFehler] = useState(false);
  const [offen, setOffen] = useState<string | null>(null);
  const [verlaufOffen, setVerlaufOffen] = useState(false);
  const [frage, setFrage] = useState<"fahrzeiten" | "heimat" | null>(null);
  const [heimat, setHeimat] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [meldung, setMeldung] = useState("");
  const nachladen = useRef<number | undefined>(undefined);

  const laden = useCallback(async (still = false) => {
    try {
      const neu = await api.tagBriefing(still);
      setDaten(neu); setFehler(false);
      // Fahrzeiten, die das Briefing nicht abwarten konnte, holt der Sidecar im Hintergrund; ein zweiter Blick zeigt sie.
      window.clearTimeout(nachladen.current);
      if (neu.termine.some(t => t.wegezeit?.status === "wird_berechnet")) nachladen.current = window.setTimeout(() => void laden(true), 4000);
    } catch { setFehler(true); }
  }, []);
  useEffect(() => {
    void laden();
    // Das stille Erneuern zählt nicht als Blick: Das Logbuch bezieht sich auf das letzte Öffnen, nicht auf den offenen Tab.
    const takt = window.setInterval(() => { if (!document.hidden) void laden(true); }, 60_000);
    return () => { window.clearInterval(takt); window.clearTimeout(nachladen.current); };
  }, [laden]);

  async function speichern(aenderung: Parameters<typeof api.wegezeitSetzen>[0], antwort: string) {
    if (arbeitet) return;
    setArbeitet(true); setMeldung("");
    try {
      const stand = await api.wegezeitSetzen(aenderung);
      await laden(true);
      // Apple Karten antwortet über den Mac-Helfer; ein zweiter Blick nach wenigen Sekunden holt die Zahl.
      window.clearTimeout(nachladen.current);
      nachladen.current = window.setTimeout(() => void laden(true), 7000);
      setMeldung(antwort);
      setFrage(stand.aktiv && !stand.heimat ? "heimat" : null);
    } catch { setMeldung("Das konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }

  async function abbestellen(a: TagAktion) {
    if (arbeitet || !a.ref) return;
    setArbeitet(true); setMeldung("");
    try {
      await api.weltAbbestellen(a.art === "welt_quelle" ? { quelle_id: a.ref } : { sache: a.ref });
      await laden(true);
      setMeldung(a.art === "welt_quelle" ? "Abbestellt. Unter Einstellungen → Was Kingfisher darf kannst du die Quelle wieder einschalten."
        : "Abbestellt. Unter Einstellungen → Was Kingfisher darf kannst du es wieder zulassen.");
    } catch { setMeldung("Das konnte nicht abbestellt werden. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }

  if (fehler && !daten) return <section className="tageslage" aria-label="Das zählt heute"><p className="tageslage-hinweis" role="status">Die Tageslage ist gerade nicht erreichbar.</p></section>;
  if (!daten || !daten.tageslage) return null;
  const lage = daten.tageslage;
  const termin = daten.termine.find(t => t.uid === offen) ?? null;
  const verlauf = lage.verlauf ?? [];

  function aktion(a: TagAktion, index: number) {
    if (a.art === "vorbereitung") return <button key={index} type="button" className="today-text-link tageslage-knopf" aria-expanded={offen === a.ref}
      onClick={() => setOffen(offen === a.ref ? null : a.ref)}>{offen === a.ref ? "Vorbereitung schließen" : a.beschriftung}<span aria-hidden="true">→</span></button>;
    if (a.art === "quelle" && a.ref) return <ProfileSource key={index} kind="episode" id={a.ref} label={a.beschriftung} quiet readOnly allowIgnore={false} />;
    if (a.art === "link" && a.ref) return <a key={index} className="today-text-link tageslage-knopf" href={a.ref} target="_blank" rel="noopener noreferrer">{a.beschriftung}<span aria-hidden="true">↗</span></a>;
    if (a.art === "akte" && a.ref) return <button key={index} type="button" className="today-text-link tageslage-knopf"
      onClick={() => navigate(`/memory/akte/${encodeURIComponent(a.ref as string)}`)}>{a.beschriftung}<span aria-hidden="true">→</span></button>;
    if (a.art === "welt_quelle" || a.art === "welt_sache") return <button key={index} type="button" className="today-text-link tageslage-knopf" disabled={arbeitet}
      onClick={() => void abbestellen(a)}>{a.beschriftung}</button>;
    if (a.art === "fahrzeiten" || a.art === "heimat") return <button key={index} type="button" className="today-text-link tageslage-knopf"
      onClick={() => setFrage(frage === a.art ? null : a.art as "fahrzeiten" | "heimat")}>{a.beschriftung}<span aria-hidden="true">→</span></button>;
    return null;
  }

  return <section className="tageslage" aria-labelledby="tageslage-titel">
    {verlauf.length > 0 && <div className="tageslage-verlauf" role="group" aria-label="Seit dem letzten Blick">
      {verlauf.map((zeile, index) => <p key={index}>{zeile}</p>)}
      <button type="button" className="today-text-link tageslage-knopf" aria-expanded={verlaufOffen}
        onClick={() => setVerlaufOffen(!verlaufOffen)}>{verlaufOffen ? "Verlauf schließen" : "Verlauf"}<span aria-hidden="true">→</span></button>
      {verlaufOffen && <Logbuch />}
    </div>}
    <h2 id="tageslage-titel">{lage.einleitung}</h2>
    {lage.zeilen.length > 0 && <ol className="tageslage-zeilen">{lage.zeilen.map(z => <li key={z.art} className={`tageslage-zeile tageslage-${z.art}`}>
      <span className="tageslage-kopf">{KOPF[z.art] ?? ""}</span>
      <p>{z.text}</p>
      {z.aktionen.length > 0 && <div className="tageslage-aktionen">{z.aktionen.map(aktion)}</div>}
    </li>)}</ol>}
    {frage === "fahrzeiten" && <div className="tageslage-frage" role="group" aria-label="Fahrzeiten berechnen">
      <p>Soll Kingfisher die Fahrzeit berechnen? Dafür geht nur die Adresse des Termins und dein Startort an Apple Karten oder an den Kartendienst, den du eingerichtet hast. Bei einem Folgetermin am selben Tag ist der Startpunkt der Ort des vorherigen Termins; auch dessen Adresse wird dann gesendet. Sonst verlässt nichts deinen Rechner. Du kannst das jederzeit in den Einstellungen ausschalten.</p>
      <div><button type="button" className="primary-action" disabled={arbeitet} onClick={() => void speichern({ aktiv: true }, "Fahrzeiten werden berechnet.")}>Ja, berechnen</button>
        <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => setFrage(null)}>Nein, danke</button></div>
    </div>}
    {frage === "heimat" && <form className="tageslage-frage" onSubmit={event => { event.preventDefault(); if (heimat.trim()) void speichern({ heimat: heimat.trim() }, "Startort gespeichert."); }}>
      <label htmlFor="tageslage-heimat">Von wo fährst du meistens los?</label>
      <div><input id="tageslage-heimat" value={heimat} maxLength={300} placeholder="Straße, Ort" onChange={event => setHeimat(event.target.value)} autoComplete="street-address" />
        <button type="submit" className="primary-action" disabled={arbeitet || !heimat.trim()}>Speichern</button></div>
    </form>}
    {meldung && <p className="tageslage-hinweis" role="status">{meldung}</p>}
    {termin && <TerminVorbereitung termin={termin} />}
    {Object.values(daten.fehler).map(text => <p key={text} className="tageslage-hinweis" role="status">{text}</p>)}
  </section>;
}
