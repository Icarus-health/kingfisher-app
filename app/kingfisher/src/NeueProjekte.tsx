import { useEffect, useState } from "react";
import { api, type NeuesProjekt } from "./api";
import { InterfaceIcon } from "./InterfaceIcon";
import { MemoryEntityLink } from "./MemoryEntityLink";
import { zeigeHinweis } from "./grundlage";
import { neueProjekteZeile, projektGrund } from "./projektAutomatik";
import "./NeueProjekte.css";

// „Neues Projekt: Umbau Praxis, aus 4 Mails mit Anna Keller und Ben Braun · Ansehen · Rückgängig“ (Paket P, sidecar:
// projekt_automatik.py). Eine ruhige Zeile unter „Braucht dich“: Ein angelegtes Projekt braucht niemanden, es soll nur
// gesehen und zurückgenommen werden können. Mehrere stehen zusammengefasst in einer Zeile, „Ansehen“ klappt sie auf.
// „Rückgängig“ löst nur Kingfishers eigene Zuordnungen und wird gemerkt; der Hinweis unten sagt, was geschah.
export function NeueProjekte({ onChange }: { onChange: () => void }) {
  const [liste, setListe] = useState<NeuesProjekt[]>([]);
  const [offen, setOffen] = useState(false);
  const [arbeitet, setArbeitet] = useState<string | null>(null);
  const [fehler, setFehler] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.neueProjekte().then(antwort => { if (aktiv) setListe(antwort.neu); }).catch(() => undefined);
    return () => { aktiv = false; };
  }, []);
  const zeile = neueProjekteZeile(liste);
  if (!zeile) return null;

  async function zurueck(projekt: NeuesProjekt) {
    if (arbeitet) return;
    setArbeitet(projekt.kennung); setFehler("");
    try {
      const antwort = await api.akteVorschlagZuruecknehmen(projekt.kennung);
      setListe(alt => alt.filter(p => p.kennung !== projekt.kennung));
      zeigeHinweis({ text: antwort.satz });
      onChange();
    } catch {
      setFehler("Das ließ sich gerade nicht zurücknehmen. Bitte noch einmal versuchen.");
    } finally { setArbeitet(null); }
  }

  const eins = liste.length === 1 ? liste[0] : null;
  return <section className="today-neue-projekte" aria-label="Von Kingfisher angelegt">
    <p className="today-neue-projekte-zeile">
      <span className="today-neue-projekte-symbol" aria-hidden="true"><InterfaceIcon name="project" /></span>
      <span className="today-neue-projekte-inhalt">
      <span className="today-neue-projekte-text">{zeile}</span>
      <span className="today-neue-projekte-aktionen">
        {eins ? <MemoryEntityLink kind="project" className="today-text-link" href={eins.link}>Ansehen</MemoryEntityLink>
          : <button type="button" className="today-text-link" aria-expanded={offen} onClick={() => setOffen(x => !x)}>{offen ? "Weniger" : "Ansehen"}</button>}
        {eins ? <button type="button" className="today-text-link" disabled={arbeitet !== null} onClick={() => void zurueck(eins)}>Rückgängig</button> : null}
      </span>
      </span>
    </p>
    {!eins && offen ? <ul className="today-neue-projekte-liste">{liste.map(p => <li key={p.kennung}>
      <MemoryEntityLink kind="project" className="today-text-link" href={p.link}>{projektGrund(p)}</MemoryEntityLink>
      <button type="button" className="today-text-link" disabled={arbeitet !== null} aria-label={`Rückgängig: ${p.name}`} onClick={() => void zurueck(p)}>Rückgängig</button>
    </li>)}</ul> : null}
    {fehler ? <p className="today-neue-projekte-fehler" role="alert">{fehler}</p> : null}
  </section>;
}
