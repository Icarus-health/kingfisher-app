import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Ein eingeklappter Abschnitt, dessen Inhalt erst beim ersten Aufklappen entsteht. Hinter „Für Techniker“ liegen viele
 * Karten, die beim Öffnen der Seite Daten laden würden; so passiert das erst, wenn jemand sie wirklich aufschlägt.
 * Einmal aufgeklappt, bleibt der Inhalt erhalten (eingegebener Text geht beim Zuklappen nicht verloren).
 */
export function Aufklapp({ id, titel, satz, offen, praefix = "technik", children }: {
  id: string; titel: string; satz: string; offen?: boolean; praefix?: string; children: ReactNode;
}) {
  const [geoeffnet, setGeoeffnet] = useState(Boolean(offen));
  const [gezeigt, setGezeigt] = useState(Boolean(offen));
  const knoten = useRef<HTMLDetailsElement>(null);

  // Ein Sprung von außen (`#technik-akten`) öffnet den Abschnitt und bringt ihn ins Bild.
  useEffect(() => {
    if (!offen) return;
    setGeoeffnet(true); setGezeigt(true);
    knoten.current?.scrollIntoView?.({ block: "start" });
  }, [offen]);

  return <details ref={knoten} id={`${praefix}-${id}`} className="einstellungen-aufklapp" open={geoeffnet}
    onToggle={event => { const auf = event.currentTarget.open; setGeoeffnet(auf); if (auf) setGezeigt(true); }}>
    <summary><span>{titel}</span><small>{satz}</small></summary>
    <div className="einstellungen-aufklapp-inhalt">{gezeigt ? children : null}</div>
  </details>;
}
