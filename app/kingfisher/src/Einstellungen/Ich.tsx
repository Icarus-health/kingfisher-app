import { useEffect, useState } from "react";
import { api } from "../api";
import { FassungEinstellung } from "../Fassung";
import { useEinrichtung } from "../Einrichtung/useEinrichtung";
import { KreisStandAnzeige } from "../Kreis";
import { WorkingProfileSettings } from "../WorkingProfileSettings";
import { Aufklapp } from "./Aufklapp";
import { ICH } from "./gliederung";

/**
 * Einstellungen → Kingfisher und du: was Kingfisher über dich wissen muss, damit es sich richtig anfühlt. Name und
 * Startort stehen nur hier; Wegezeit und Wetter benutzen sie und fragen nicht noch einmal (Prüffrage 2 in CLAUDE.md).
 */
export function Ich() {
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

  return <div className="ich">
    <form className="ich-feld" onSubmit={event => { event.preventDefault(); void nameSpeichern(); }}>
      <label htmlFor="ich-name">{ICH.name.frage}</label>
      <div><input id="ich-name" value={name} maxLength={80} autoComplete="given-name" placeholder="Dein Vorname" disabled={arbeitet !== "" || (!stand && !einrichtungFehler)} onChange={event => setName(event.target.value)} />
        <button type="submit" className="secondary-action" disabled={arbeitet !== "" || gespeichertName === null || name.trim() === gespeichertName}>Speichern</button></div>
      <p className="source-hint">{ICH.name.hilfe}</p>
    </form>
    <form className="ich-feld" onSubmit={event => { event.preventDefault(); void ortSpeichern(); }}>
      <label htmlFor="ich-startort">{ICH.startort.frage}</label>
      <div><input id="ich-startort" value={startort} maxLength={300} autoComplete="street-address" placeholder="Straße, Ort" disabled={arbeitet !== "" || gespeicherterOrt === null} onChange={event => setStartort(event.target.value)} />
        <button type="submit" className="secondary-action" disabled={arbeitet !== "" || gespeicherterOrt === null || startort.trim() === gespeicherterOrt}>Speichern</button></div>
      <p className="source-hint">{ICH.startort.hilfe}</p>
    </form>
    <div className="ich-feld">
      <strong>Zeitzone: {stand?.zeitzone ?? "…"}</strong>
      <p className="source-hint">{ICH.zeitzone.hilfe}</p>
    </div>
    <div className="ich-feld">
      <strong>{ICH.kreis.titel}</strong>
      <p className="source-hint">{ICH.kreis.text}</p>
      <KreisStandAnzeige />
    </div>
    <FassungEinstellung />
    <Aufklapp id="antwort" praefix="ich" titel={ICH.antwort.titel} satz={ICH.antwort.hilfe}><WorkingProfileSettings /></Aufklapp>
    {hinweis && <p role="status" className="source-hint">{hinweis}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </div>;
}
