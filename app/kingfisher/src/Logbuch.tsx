import { useEffect, useState } from "react";
import { api, type LogbuchAnsicht } from "./api";
import "./Logbuch.css";

// Der Verlauf: was Kingfisher in den letzten Tagen getan hat, nach Tagen gruppiert, ohne Zahlenfriedhof.
// Keine eigene Seite, sondern die Ansicht hinter dem stillen Link „Verlauf“ im Briefing. Sie liest nur.
export function Logbuch() {
  const [daten, setDaten] = useState<LogbuchAnsicht | null>(null);
  const [fehler, setFehler] = useState(false);
  useEffect(() => {
    let aktiv = true;
    api.logbuch().then(neu => { if (aktiv) setDaten(neu); }).catch(() => { if (aktiv) setFehler(true); });
    return () => { aktiv = false; };
  }, []);
  if (fehler) return <p className="logbuch-hinweis" role="status">Der Verlauf ist gerade nicht erreichbar.</p>;
  if (!daten) return <p className="logbuch-hinweis" role="status">Der Verlauf wird geladen …</p>;
  if (daten.tage.length === 0) return <p className="logbuch-hinweis" role="status">In den letzten Tagen hat sich noch nichts getan.</p>;
  return <section className="logbuch" aria-label="Verlauf der letzten Tage">
    {daten.tage.map(tag => <div key={tag.tag} className="logbuch-tag">
      <h3>{tag.titel}</h3>
      <ul>{tag.eintraege.map((text, index) => <li key={index}>{text}</li>)}</ul>
    </div>)}
  </section>;
}
