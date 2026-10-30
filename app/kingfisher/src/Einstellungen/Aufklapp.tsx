import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Ein eingeklappter Abschnitt, dessen Inhalt erst beim ersten Aufklappen entsteht. Hinter „Für Techniker“ liegen viele
 * Karten, die beim Öffnen der Seite Daten laden würden; so passiert das erst, wenn jemand sie wirklich aufschlägt.
 * Einmal aufgeklappt, bleibt der Inhalt erhalten (eingegebener Text geht beim Zuklappen nicht verloren).
 */
export function Aufklapp({ id, titel, satz, offen, sprungZiel, praefix = "technik", children }: {
  id: string; titel: string; satz: string; offen?: boolean; sprungZiel?: string | null; praefix?: string; children: ReactNode;
}) {
  const [geoeffnet, setGeoeffnet] = useState(Boolean(offen));
  const [gezeigt, setGezeigt] = useState(Boolean(offen));
  const knoten = useRef<HTMLDetailsElement>(null);

  // Ein Sprung von außen (`#technik-akten`) öffnet den Abschnitt und bringt ihn ins Bild.
  useEffect(() => {
    if (!offen) return;
    setGeoeffnet(true); setGezeigt(true);
    knoten.current?.scrollIntoView?.({ block: "start" });
  }, [offen, sprungZiel]);

  return <details ref={knoten} id={`${praefix}-${id}`} className="einstellungen-aufklapp" open={geoeffnet}
    onToggle={event => {
      // Browserseitiges Öffnen (etwa Fundstelle) übernehmen. Eine verzögerte
      // Schließmeldung darf einen neueren Navigationssprung nicht zurücknehmen.
      if (event.target === event.currentTarget && event.currentTarget.open) { setGeoeffnet(true); setGezeigt(true); }
    }}>
    <summary onClick={event => { event.preventDefault(); setGeoeffnet(auf => !auf); setGezeigt(true); }}><span>{titel}</span></summary>
    {/* Der Satz steht aufgeklappt über dem Inhalt: zu ist es eine ruhige Zeile mit Pfeil (wie am Mac). */}
    <div className="einstellungen-aufklapp-inhalt">{gezeigt ? <><p className="einstellungen-satz">{satz}</p>{children}</> : null}</div>
  </details>;
}
