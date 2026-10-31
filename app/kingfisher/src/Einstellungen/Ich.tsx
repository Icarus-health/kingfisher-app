import { useEffect, useState } from "react";
import { api } from "../api";
import { FassungEinstellung } from "../Fassung";
import { useEinrichtung } from "../Einrichtung/useEinrichtung";
import { KreisStandAnzeige } from "../KreisKarten";
import { KreisTon } from "../StilKreis";
import { WorkingProfileSettings } from "../WorkingProfileSettings";
import { ProcedureSettings } from "../ProcedureSettings";
import { Aufklapp } from "./Aufklapp";
import { ICH } from "./gliederung";

/**
 * Einstellungen → Kingfisher und du: was Kingfisher über dich wissen muss, damit es sich richtig anfühlt. Name und
 * Startort stehen nur hier; Wegezeit und Wetter benutzen sie und fragen nicht noch einmal (Prüffrage 2 in CLAUDE.md).
 */
export function Ich({ ablaeufeOffen = false, ablaufZiel }: { ablaeufeOffen?: boolean; ablaufZiel?: string | null }) {
  const { stand, fehler: einrichtungFehler, aendern } = useEinrichtung();
  const [name, setName] = useState("");
  const [startort, setStartort] = useState("");
  const [gespeicherterOrt, setGespeicherterOrt] = useState<string | null>(null);
  const [gespeichertName, setGespeichertName] = useState<string | null>(null);
  const [arbeitet, setArbeitet] = useState("");
  const [hinweis, setHinweis] = useState("");
  const [fehler, setFehler] = useState("");

  useEffect(() => { if (stand && gespeichertName === null) { setName(stand.name); setGespeichertName(stand.name); } }, [stand, gespeichertName]);
  useEffect(() => {
    let aktiv = true;
    api.wegezeit().then(daten => { if (aktiv) { setStartort(daten.heimat); setGespeicherterOrt(daten.heimat); } })
      .catch(() => { if (aktiv) setFehler("Der Startort konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);

  async function nameSpeichern() {
    setArbeitet("name"); setFehler(""); setHinweis("");
    const neu = await aendern({ name: name.trim() });
    if (neu) { setGespeichertName(neu.name); setName(neu.name); setHinweis(neu.name ? `Gespeichert. Kingfisher grüßt dich künftig mit „${neu.name}“.` : "Gespeichert. Kingfisher grüßt dich ohne Namen."); }
    else setFehler("Der Name konnte nicht gespeichert werden. Bitte erneut versuchen.");
    setArbeitet("");
  }

  async function ortSpeichern() {
    setArbeitet("ort"); setFehler(""); setHinweis("");
    try {
      const neu = await api.wegezeitSetzen({ heimat: startort.trim() });
      setGespeicherterOrt(neu.heimat); setStartort(neu.heimat);
      setHinweis(neu.heimat ? "Startort gespeichert. Er bleibt auf diesem Rechner, bis du „Wegezeit berechnen“ einschaltest." : "Startort entfernt.");
    } catch { setFehler("Der Startort konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { setArbeitet(""); }
  }

  // Wie die Einstellungen am Mac: Gruppen mit Überschrift; Erklärungen leise unter dem Feld oder eingeklappt darunter.
  return <div className="ich-gruppen">
    <div className="ich">
      <form className="ich-feld" onSubmit={event => { event.preventDefault(); void nameSpeichern(); }}>
        <label htmlFor="ich-name">{ICH.name.frage}</label>
        <div><input id="ich-name" value={name} maxLength={80} autoComplete="given-name" placeholder="Dein Vorname" disabled={arbeitet !== "" || (!stand && !einrichtungFehler)} onChange={event => setName(event.target.value)} />
          <button type="submit" className="g-knopf-getoent" disabled={arbeitet !== "" || gespeichertName === null || name.trim() === gespeichertName}>Speichern</button></div>
        <p className="source-hint">{ICH.name.hilfe}</p>
      </form>
      <form className="ich-feld" onSubmit={event => { event.preventDefault(); void ortSpeichern(); }}>
        <label htmlFor="ich-startort">{ICH.startort.frage}</label>
        <div><input id="ich-startort" value={startort} maxLength={300} autoComplete="street-address" placeholder="Straße, Ort" disabled={arbeitet !== "" || gespeicherterOrt === null} onChange={event => setStartort(event.target.value)} />
          <button type="submit" className="g-knopf-getoent" disabled={arbeitet !== "" || gespeicherterOrt === null || startort.trim() === gespeicherterOrt}>Speichern</button></div>
        <p className="source-hint">{ICH.startort.hilfe}</p>
      </form>
      <div className="ich-feld ich-zeitzone">
        <strong>Zeitzone: {stand?.zeitzone ?? "…"}</strong>
        <p className="source-hint">{ICH.zeitzone.hilfe}</p>
      </div>
      {hinweis && <p role="status" className="source-hint ich-meldung">{hinweis}</p>}
      {fehler && <p role="alert" className="settings-error ich-meldung">{fehler}</p>}
    </div>
    <section className="darf-gruppe" aria-label={ICH.kreis.titel}>
      <div className="g-gruppe-kopf"><h2 className="g-gruppe-titel">{ICH.kreis.titel}</h2></div>
      <div className="ich"><div className="ich-feld"><KreisStandAnzeige /></div></div>
      <details className="quiet-details ich-mehr"><summary>Was bedeutet der Kreis?</summary><p className="source-hint">{ICH.kreis.text}</p></details>
    </section>
    <section className="darf-gruppe" aria-label={ICH.ton.titel}>
      <div className="g-gruppe-kopf"><h2 className="g-gruppe-titel">{ICH.ton.titel}</h2></div>
      <div className="ich"><div className="ich-feld"><KreisTon /></div></div>
      <details className="quiet-details ich-mehr"><summary>Woher kommt der Ton?</summary><p className="source-hint">{ICH.ton.text}</p></details>
    </section>
    <div className="ich"><FassungEinstellung /></div>
    <div className="technik"><Aufklapp id="antwort" praefix="ich" titel={ICH.antwort.titel} satz={ICH.antwort.hilfe}><WorkingProfileSettings /></Aufklapp></div>
    <div className="technik"><Aufklapp id="ablaeufe" praefix="ich" titel="Bewährte Abläufe" satz="Übernommene Vorgehensweisen und neue Vorschläge prüfen." offen={ablaeufeOffen} sprungZiel={ablaufZiel}><ProcedureSettings /></Aufklapp></div>
  </div>;
}
