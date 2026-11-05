import { useCallback, useEffect, useRef, useState } from "react";
import { api, type TagAktion, type TagBriefing } from "./api";
import { ProfileSource } from "./ProfileSource";
import { Logbuch } from "./Logbuch";
import { navigate } from "./ui";
import { TerminVorbereitung } from "./TerminVorbereitung";
import "./TagesLage.css";
import { dailyIntroduction } from "./dailyFlow";

// Das Morgenbriefing in drei bis fünf Zeilen: ein Urteil, keine Liste. Jede Zeile hat ihre Aktion
// (Vorbereitung öffnen, Quelle öffnen); was fehlt oder nicht belegt ist, steht nicht da. Die Vorbereitung
// der Termine entsteht ohne Klick im Sidecar (tag_routes.py); hier wird nur gezeigt und gefragt.
const KOPF: Record<string, string> = { termin: "Wohin", leute: "Wer kommt", einpacken: "Einpacken", fristen: "Fristen", aufgaben_post: "Post", wetter: "Wetter", geburtstag: "Geburtstag", welt: "Welt" };

export function TagesLage({sourcesIncomplete = false}: {sourcesIncomplete?: boolean}) {
  const [daten, setDaten] = useState<TagBriefing | null>(null);
  const [fehler, setFehler] = useState(false);
  const [laedt, setLaedt] = useState(false);
  const [offen, setOffen] = useState<string | null>(null);
  const [verlaufOffen, setVerlaufOffen] = useState(false);
  const [frage, setFrage] = useState<"fahrzeiten" | "heimat" | null>(null);
  const [heimat, setHeimat] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [meldung, setMeldung] = useState("");
  const nachladen = useRef<number | undefined>(undefined);
  const live = useRef(false);
  const lesestand = useRef(0);
  const laufendeAbrufe = useRef(0);

  const laden = useCallback(async (still = false) => {
    if (!live.current) return;
    const anfrage = ++lesestand.current;
    laufendeAbrufe.current += 1;
    setLaedt(true);
    window.clearTimeout(nachladen.current);
    try {
      const neu = await api.tagBriefing(still);
      // Ein älterer Abruf darf z. B. eine inzwischen abbestellte Quelle nicht wieder einsetzen.
      if (!live.current || anfrage !== lesestand.current) return;
      setDaten(neu); setFehler(false);
      // Fahrzeiten, die das Briefing nicht abwarten konnte, holt der Sidecar im Hintergrund; ein zweiter Blick zeigt sie.
      if (neu.termine.some(t => t.wegezeit?.status === "wird_berechnet")) nachladen.current = window.setTimeout(() => void laden(true), 4000);
    } catch { if (live.current && anfrage === lesestand.current) setFehler(true); }
    finally {
      laufendeAbrufe.current -= 1;
      if (live.current && anfrage === lesestand.current) setLaedt(false);
    }
  }, []);
  useEffect(() => {
    live.current = true;
    void laden();
    // Das stille Erneuern zählt nicht als Blick: Das Logbuch bezieht sich auf das letzte Öffnen, nicht auf den offenen Tab.
    const takt = window.setInterval(() => { if (!document.hidden && !laufendeAbrufe.current) void laden(true); }, 60_000);
    return () => { live.current = false; lesestand.current += 1; window.clearInterval(takt); window.clearTimeout(nachladen.current); };
  }, [laden]);

  async function speichern(aenderung: Parameters<typeof api.wegezeitSetzen>[0], antwort: string) {
    if (arbeitet) return;
    setArbeitet(true); setMeldung("");
    try {
      const stand = await api.wegezeitSetzen(aenderung);
      await laden(true);
      if (!live.current) return;
      // Apple Karten antwortet über den Mac-Helfer; ein zweiter Blick nach wenigen Sekunden holt die Zahl.
      window.clearTimeout(nachladen.current);
      nachladen.current = window.setTimeout(() => void laden(true), 7000);
      setMeldung(antwort);
      setFrage(stand.aktiv && !stand.heimat ? "heimat" : null);
    } catch { if (live.current) setMeldung("Das konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { if (live.current) setArbeitet(false); }
  }

  async function abbestellen(a: TagAktion) {
    if (arbeitet || !a.ref) return;
    setArbeitet(true); setMeldung("");
    try {
      await api.weltAbbestellen(a.art === "welt_quelle" ? { quelle_id: a.ref } : { sache: a.ref });
      await laden(true);
      if (!live.current) return;
      setMeldung(a.art === "welt_quelle" ? "Abbestellt. Unter Einstellungen → Was Kingfisher darf kannst du die Quelle wieder einschalten."
        : "Abbestellt. Unter Einstellungen → Was Kingfisher darf kannst du es wieder zulassen.");
    } catch { if (live.current) setMeldung("Das konnte nicht abbestellt werden. Bitte erneut versuchen."); }
    finally { if (live.current) setArbeitet(false); }
  }

  const ladeHinweis = fehler ? <p className="tageslage-hinweis" role="status">
    {daten ? "Aktualisierung fehlgeschlagen. Angezeigt wird der letzte geladene Stand." : "Die Tageslage ist gerade nicht erreichbar."}{" "}
    <button className="today-text-link tageslage-knopf" type="button" disabled={laedt} onClick={() => void laden(true)}>{laedt ? "Wird geladen …" : "Erneut versuchen"}</button>
  </p> : null;
  if (fehler && !daten?.tageslage) return <section className="tageslage" aria-label="Das zählt heute">{ladeHinweis}</section>;
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
    // Aufgaben folgen der Post: die erledigte Aufgabe öffnen (dort steht der Grund mit „Rückgängig“).
    if (a.art === "aufgabe" && a.ref) return <button key={index} type="button" className="today-text-link tageslage-knopf"
      onClick={() => navigate(`/vorhaben?view=done&task=${encodeURIComponent(a.ref as string)}`)}>{a.beschriftung}<span aria-hidden="true">→</span></button>;
    if (a.art === "welt_quelle" || a.art === "welt_sache") return <button key={index} type="button" className="today-text-link tageslage-knopf" disabled={arbeitet}
      onClick={() => void abbestellen(a)}>{a.beschriftung}</button>;
    if (a.art === "fahrzeiten" || a.art === "heimat") return <button key={index} type="button" className="today-text-link tageslage-knopf"
      onClick={() => setFrage(frage === a.art ? null : a.art as "fahrzeiten" | "heimat")}>{a.beschriftung}<span aria-hidden="true">→</span></button>;
    return null;
  }

  return <section className="tageslage" aria-labelledby="tageslage-titel">
    {ladeHinweis}
    {verlauf.length > 0 && <div className="tageslage-verlauf" role="group" aria-label="Seit dem letzten Blick">
      {verlauf.map((zeile, index) => <p key={index}>{zeile}</p>)}
      <button type="button" className="today-text-link tageslage-knopf" aria-expanded={verlaufOffen}
        onClick={() => setVerlaufOffen(!verlaufOffen)}>{verlaufOffen ? "Verlauf schließen" : "Verlauf"}<span aria-hidden="true">→</span></button>
      {verlaufOffen && <Logbuch />}
    </div>}
    <h2 id="tageslage-titel">{dailyIntroduction(lage.einleitung, lage.zeilen.length > 0, fehler || sourcesIncomplete || Object.keys(daten.fehler).length > 0)}</h2>
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
