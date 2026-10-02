import { useEffect, useState, type ReactNode } from "react";
import "./SettingsSections.css";

type Section = { id: string; label: string; description: string; content: ReactNode; hinten?: boolean };

/**
 * Die Reiter der Einstellungen. Der Inhalt eines Reiters entsteht erst beim ersten Besuch und bleibt dann erhalten
 * (eingegebener Text geht beim Wechsel nicht verloren, und beim Öffnen der Seite laden nicht alle Karten Daten).
 * Ein Reiter mit `hinten` steht abgesetzt am Ende der Reihe („Für Techniker“).
 */
export function SettingsSections({ sections, selected, onSelect }: { sections: Section[]; selected: string; onSelect: (id: string) => void }) {
  const [besucht, setBesucht] = useState<ReadonlySet<string>>(() => new Set([selected]));
  useEffect(() => { setBesucht(alt => alt.has(selected) ? alt : new Set(alt).add(selected)); }, [selected]);
  return <div className="settings-sections">
    <nav className="settings-section-nav" aria-label="Einstellungsbereiche">
      {sections.map(section => <button key={section.id} type="button" className={section.hinten ? "settings-section-hinten" : undefined}
        aria-pressed={selected === section.id} aria-controls={`settings-${section.id}`}
        onClick={() => onSelect(section.id)}>{section.label}</button>)}
    </nav>
    {sections.map(section => <section key={section.id} id={`settings-${section.id}`}
      className="settings-section-panel" aria-label={section.label} hidden={selected !== section.id}>
      <header><h2>{section.label}</h2><p>{section.description}</p></header>
      <div className="settings-sources">{besucht.has(section.id) || selected === section.id ? section.content : null}</div>
    </section>)}
  </div>;
}
