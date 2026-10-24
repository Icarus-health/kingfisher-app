import { useEffect, useState, type ComponentProps, type ReactNode } from "react";
import { InterfaceIcon } from "./InterfaceIcon";
import "./SettingsSections.css";

type Section = { id: string; label: string; description: string; content: ReactNode; hinten?: boolean;
  /** Das Zeichen vor dem Namen in der Seitenliste (wie in den Systemeinstellungen am Mac). */
  zeichen?: ComponentProps<typeof InterfaceIcon>["name"] };

/**
 * Die Reiter der Einstellungen. Der Inhalt eines Reiters entsteht erst beim ersten Besuch und bleibt dann erhalten
 * (eingegebener Text geht beim Wechsel nicht verloren, und beim Öffnen der Seite laden nicht alle Karten Daten).
 * Ein Reiter mit `hinten` steht abgesetzt am Ende der Reihe („Für Techniker“). Breit eine Seitenliste mit Zeichen wie
 * in den Systemeinstellungen am Mac, schmal ein Auswahlfeld (Einstellungen.css).
 */
export function SettingsSections({ sections, selected, onSelect }: { sections: Section[]; selected: string; onSelect: (id: string) => void }) {
  const [besucht, setBesucht] = useState<ReadonlySet<string>>(() => new Set([selected]));
  useEffect(() => { setBesucht(alt => alt.has(selected) ? alt : new Set(alt).add(selected)); }, [selected]);
  return <div className="settings-sections">
    <label className="settings-section-picker">Bereich
      <select aria-label="Einstellungsbereich" value={selected} onChange={event => onSelect(event.target.value)}>
        <optgroup label="Alltag">{sections.filter(section => !section.hinten).map(section => <option key={section.id} value={section.id}>{section.label}</option>)}</optgroup>
        <optgroup label="Für Techniker">{sections.filter(section => section.hinten).map(section => <option key={section.id} value={section.id}>{section.label}</option>)}</optgroup>
      </select>
    </label>
    <nav className="settings-section-nav" aria-label="Einstellungsbereiche">
      {sections.map(section => <button key={section.id} type="button" className={section.hinten ? "settings-section-hinten" : undefined}
        aria-pressed={selected === section.id} aria-controls={`settings-${section.id}`}
        onClick={() => onSelect(section.id)}>
        {section.zeichen ? <span className="settings-nav-zeichen" aria-hidden="true"><InterfaceIcon name={section.zeichen} /></span> : null}
        <span>{section.label}</span></button>)}
    </nav>
    {sections.map(section => <section key={section.id} id={`settings-${section.id}`}
      className="settings-section-panel" aria-label={section.label} hidden={selected !== section.id} aria-hidden={selected !== section.id ? true : undefined}>
      <header><h2>{section.label}</h2><p>{section.description}</p></header>
      <div className="settings-sources">{besucht.has(section.id) || selected === section.id ? section.content : null}</div>
    </section>)}
  </div>;
}
