import { useCallback, useEffect, useState, type ReactNode } from "react";
import { EinrichtungKopf } from "../Einrichtung/EinrichtungKopf";
import { RecoverySettings } from "../RecoverySettings";
import { SettingsSections } from "../SettingsSections";
import { Aufklapp } from "./Aufklapp";
import { Sidebar } from "../chrome";
import { Darf } from "./Darf";
import {WorkspaceOnlineSettings} from '../WorkspaceOnlineSettings';
import { CloudAccess } from "../CloudAccess";
import { ChatGPTAccess } from "../ChatGPTAccess";
import { DeviceModelHelp } from "../DeviceModelHelp";
import { LocalModelSettings } from "../LocalModelSettings";
import { ModelRecommendation } from "../ModelRecommendation";
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
    if (neu.bereich !== ziel.bereich) window.scrollTo({top: 0, behavior: "auto"});
  }, [ziel.bereich]);

  const inhalt: Record<Bereich, ReactNode> = {
    zugaenge: <><EinrichtungKopf /><Zugaenge integrationen={integrationen} aktiv={ziel.bereich === "zugaenge"} /></>,
    ki: <><LocalModelSettings /><ChatGPTAccess /><CloudAccess />
      <ModelRecommendation compact><Aufklapp id="geraet" praefix="ki" titel="Gerät und installierte Modelle" satz="Speicherbedarf und vorhandene Modelle."><DeviceModelHelp /></Aufklapp></ModelRecommendation></>,
    darf: <><Darf /><WorkspaceOnlineSettings /></>,
    ich: <Ich />,
    sicherung: <RecoverySettings />,
    technik: <Technik integrationen={integrationen} ziel={ziel} zuBereich={waehlen} />,
  };

  return <div className="shell settings-shell">
    <Sidebar active="Einstellungen" recentConversation={recentConversation} />
    <main className="settings-page">
      <header className="settings-heading"><h1>Einstellungen</h1></header>
      {integrationen.error ? <p className="settings-error">{integrationen.error} <button onClick={integrationen.load} type="button">Wiederholen</button></p> : null}
      <div className="settings-layout">
        <SettingsSections selected={ziel.bereich} onSelect={waehlen}
          sections={BEREICHE.map(b => ({ id: b.id, label: b.label, description: fuerSystem(b.satz, system), hinten: b.hinten, content: inhalt[b.id] }))} />
      </div>
      <details className="settings-storage quiet-details"><summary>Datenschutz & Speicherung</summary>
        <p>{fuerSystem("Kingfisher speichert Quellen und Einstellungen auf diesem {Rechner}.", system)} Externe Dienste und Cloud-Verarbeitung benötigen eine gesonderte Freigabe.</p>
        <p>Ordner und Kalender wählst du selbst. Trennen entfernt den lokalen Zugang, keine Daten beim Anbieter.</p>
      </details>
    </main>
  </div>;
}
