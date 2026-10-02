import { useCallback, useEffect, useState, type ReactNode } from "react";
import { EinrichtungKopf } from "../Einrichtung/EinrichtungKopf";
import { RecoverySettings } from "../RecoverySettings";
import { SettingsSections } from "../SettingsSections";
import { Sidebar } from "../chrome";
import { Darf } from "./Darf";
import { BEREICHE, kennungVon, zielAus, type Bereich } from "./gliederung";
import { Ich } from "./Ich";
import { Technik } from "./Technik";
import { fuerSystem } from "../system";
import { useSystem } from "../useSystem";
import { useIntegrationen, Zugaenge } from "./Zugaenge";
import "./Einstellungen.css";

/**
 * Die Seite „Einstellungen“ in zwei Ebenen (docs/47-einstellungen.md). Vorne vier Bereiche in Alltagssprache, hinten
 * „Für Techniker“. Der Bereich steht im Adressteil (`/settings#darf`, `#technik-akten`), damit Verweise von anderen
 * Seiten ankommen; die alten Kennungen (`#world`, `#model`, …) führen an den neuen Ort.
 */
export function EinstellungenSeite({ recentConversation }: { recentConversation: string | null }) {
  const integrationen = useIntegrationen();
  const system = useSystem();
  const [ziel, setZiel] = useState(() => zielAus(window.location.hash));

  useEffect(() => {
    const lesen = () => setZiel(zielAus(window.location.hash));
    window.addEventListener("hashchange", lesen);
    window.addEventListener("popstate", lesen);
    return () => { window.removeEventListener("hashchange", lesen); window.removeEventListener("popstate", lesen); };
  }, []);

  const waehlen = useCallback((kennung: string) => {
    const neu = zielAus(kennung);
    setZiel(neu);
    window.location.hash = kennungVon(neu);
  }, []);

  const inhalt: Record<Bereich, ReactNode> = {
    zugaenge: <><EinrichtungKopf /><Zugaenge integrationen={integrationen} aktiv={ziel.bereich === "zugaenge"} /></>,
    darf: <Darf />,
    ich: <Ich />,
    sicherung: <RecoverySettings />,
    technik: <Technik integrationen={integrationen} ziel={ziel} zuBereich={waehlen} />,
  };

  return <div className="shell settings-shell">
    <Sidebar active="Einstellungen" recentConversation={recentConversation} />
    <main className="settings-page">
      <header className="settings-heading"><p className="eyebrow">EINSTELLUNGEN</p><h1>Dein Kingfisher</h1><span>Was Kingfisher darf, woher es seine Informationen holt und wie es dich kennt.</span></header>
      {integrationen.error ? <p className="settings-error">{integrationen.error} <button onClick={integrationen.load} type="button">Wiederholen</button></p> : null}
      <div className="settings-layout">
        <SettingsSections selected={ziel.bereich} onSelect={waehlen}
          sections={BEREICHE.map(b => ({ id: b.id, label: b.label, description: fuerSystem(b.satz, system), hinten: b.hinten, content: inhalt[b.id] }))} />
        <aside className="settings-data">
          <h2>Deine Daten bleiben bei dir</h2>
          <div className="settings-data-row"><strong>Lokale Speicherung</strong><span>{fuerSystem("Auf diesem {Rechner} gespeichert", system)}</span></div>
          <div className="settings-data-row"><strong>Notizen</strong><span>Nur ausdrücklich freigegebene Ordner</span></div>
          <div className="settings-data-row"><strong>Kalender-Abos</strong><span>Keine automatische Standort- oder Cloud-Freigabe</span></div>
          <p>Eine Quelle wird nie automatisch hinzugefügt. Trennen löscht nur die lokale Zugangskonfiguration, nicht die Daten beim jeweiligen Anbieter.</p>
        </aside>
      </div>
    </main>
  </div>;
}
