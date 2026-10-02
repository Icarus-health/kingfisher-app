import { type ReactNode } from "react";
import { AntwortZeitenProtokoll } from "../AntwortZeiten";
import { AktenOrdnerSettings } from "../AktenOrdnerSettings";
import { WasAufgefallenIst } from "../Befunde";
import { DeviceModelHelp } from "../DeviceModelHelp";
import { GoogleVorbereiten } from "../GoogleVorbereiten";
import { LocalModelSettings } from "../LocalModelSettings";
import { MailFilterSettings } from "../MailFilterSettings";
import { MailSyncSettings } from "../MailSyncSettings";
import { MemoryAutomationSettings } from "../MemoryAutomationSettings";
import { MicrosoftVorbereiten } from "../MicrosoftVorbereiten";
import { ModelRecommendation } from "../ModelRecommendation";
import { RoutingControls } from "../RoutingControls";
import { RueckmeldungenListe } from "../Rueckmeldung";
import { SetupOverview } from "../SetupOverview";
import { SuchindexSettings } from "../SuchindexSettings";
import { WegezeitKartendienst } from "../WegezeitSettings";
import { WorldControls } from "../WorldControls";
import { Aufklapp } from "./Aufklapp";
import { TECHNIK, type Ziel } from "./gliederung";
import type { Integrationen } from "./Zugaenge";

/** Wo auf diesem Rechner was liegt. Steht hier als Text, weil es dafür keine Einstellung gibt (docs/09-einrichtung.md). */
function Speicherorte() {
  return <div className="source-section speicherorte">
    <ul>
      <li><strong>Einstellungen</strong>: eine Datei im Datenordner von Kingfisher (<code>einstellungen.json</code>, nur für dich lesbar). Sie enthält keine Passwörter.</li>
      <li><strong>Passwörter und Zugangsschlüssel</strong>: im Schlüsselbund dieses Rechners, nie in einer Datei.</li>
      <li><strong>Gedächtnis, Quellen, Gespräche, Aufgaben</strong>: Datenbanken im selben Datenordner.</li>
      <li><strong>Sicherungen</strong>: dort, wo du sie bei „Sicherung“ ablegst, verschlüsselt mit deinem Passwort.</li>
    </ul>
    <p className="source-hint">Nichts davon verlässt diesen Rechner, außer was du unter „Was Kingfisher darf“ eingeschaltet hast.</p>
  </div>;
}

/** Hinter „Für Techniker“: der Weg ohne App, für eine Arbeitskopie mit `make start`. */
function FassungTechnik() {
  return <div className="source-section">
    <p>Ohne die App aktualisiert ein Befehl im Ordner von Kingfisher: <code>make aktualisieren</code>. Er sichert
      zuerst (wie <code>make backup</code>, als Sicherung vor einem Update), lädt das fertige Bild der neuen Fassung,
      trägt es als <code>KINGFISHER_IMAGE</code> in <code>.kingfisher.env</code> ein und startet neu. Eine bestimmte
      Fassung: <code>make aktualisieren FASSUNG=1.2.0</code>.</p>
    <p className="source-hint">Startet die neue Fassung nicht, läuft danach wieder die alte. Den Datenstand von vorher
      holt <code>make zurueck-vor-update</code> zurück. Die Prüfung fragt nur die Datei <code>latest.json</code> der
      Download-Seite ab, ohne Kekse und ohne Kennung (docs/53-download-und-updates.md).</p>
  </div>;
}

/**
 * Einstellungen → Für Techniker: alles, was die Vorgaben übernehmen. Jeder Abschnitt ist eingeklappt und lädt seine
 * Daten erst beim Aufklappen. Die Karten darin sind unverändert; es ist nur die Gliederung darüber.
 */
export function Technik({ integrationen, ziel, zuBereich }: {
  integrationen: Integrationen; ziel: Ziel; zuBereich: (kennung: string) => void;
}) {
  const accounts = integrationen.overview?.mail_accounts ?? [];
  const inhalt: Record<string, ReactNode> = {
    modelle: <><ModelRecommendation /><LocalModelSettings /><DeviceModelHelp /></>,
    routing: <RoutingControls />,
    antwortzeiten: <AntwortZeitenProtokoll />,
    suchindex: <SuchindexSettings active />,
    akten: <AktenOrdnerSettings />,
    rueckmeldungen: <RueckmeldungenListe active />,
    befunde: <WasAufgefallenIst active />,
    hintergrund: <>
      <MemoryAutomationSettings active />
      {integrationen.overview ? <MailSyncSettings accounts={accounts} /> : <p className="source-hint" role="status">Die Postfächer werden gelesen …</p>}
    </>,
    filter: <MailFilterSettings />,
    quellen: <WorldControls />,
    kartendienst: <WegezeitKartendienst />,
    google: <GoogleVorbereiten />,
    microsoft: <MicrosoftVorbereiten />,
    stand: <SetupOverview overview={integrationen.overview} active onSelect={id => zuBereich(id)} onRefresh={integrationen.load} />,
    speicherorte: <Speicherorte />,
    fassung: <FassungTechnik />,
  };
  return <div className="technik">
    {TECHNIK.map(abschnitt => <Aufklapp key={abschnitt.id} id={abschnitt.id} titel={abschnitt.titel} satz={abschnitt.satz}
      offen={ziel.technik === abschnitt.id}>{inhalt[abschnitt.id]}</Aufklapp>)}
  </div>;
}
