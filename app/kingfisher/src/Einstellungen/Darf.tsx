import { useEffect, useState } from "react";
import { AutostartWahl } from "../Einrichtung/AutostartWahl";
import { api } from "../api";
import { FassungSchalter } from "../Fassung";
import { Schalter } from "../grundlage";
import { Nachrichten, Wetter } from "../WeltSettings";
import { WegezeitSettings } from "../WegezeitSettings";
import { CloudSchalter } from "./CloudSchalter";
import { Mitteilungen } from "./Mitteilungen";
import { CloudEinordnungSchalter } from "./CloudEinordnungSchalter";
import { AufgabenSelbstSchalter } from "./AufgabenSelbstSchalter";
import { SCHALTER } from "./gliederung";
import { fuerSystem } from "../system";
import { useSystem } from "../useSystem";

/** Webseiten im Gespräch abrufen (Persona-Prüfung, D2): an, aber jeder einzelne Abruf wartet auf die Freigabe. */
function WebSchalter() {
  const [an, setAn] = useState<boolean | null>(null);
  const [arbeitet, setArbeitet] = useState(false);
  const [meldung, setMeldung] = useState("");
  const [fehler, setFehler] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.webAbruf().then(stand => { if (aktiv) setAn(stand.an); }).catch(() => { if (aktiv) setFehler("Die Einstellung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);
  async function schalten(neu: boolean) {
    setArbeitet(true); setFehler(""); setMeldung("");
    try {
      const stand = await api.webAbrufSetzen(neu);
      setAn(stand.an);
      setMeldung(stand.an ? "Kingfisher darf Webseiten abrufen, jede erst nach deiner Freigabe im Gespräch." : "Kingfisher ruft keine Webseiten mehr ab.");
    } catch { setFehler("Das konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }
  return <section className="darf-zeile" aria-label={SCHALTER.web.titel}>
    {an === null ? (fehler ? null : <p>Wird geladen …</p>) : <Schalter className="welt-schalter" titel={SCHALTER.web.titel} satz={SCHALTER.web.verlaesst}
      an={an} deaktiviert={arbeitet} onWechsel={neu => void schalten(neu)} />}
    {meldung ? <p role="status" className="source-hint">{meldung}</p> : null}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </section>;
}

/**
 * Einstellungen → Was Kingfisher darf: die Dinge, die etwas nach außen schicken oder im Hintergrund laufen, als
 * Schalter untereinander. Alle sind aus, bis man sie einschaltet, außer drei: „Webseiten im Gespräch abrufen“ (jeder
 * Abruf wartet trotzdem auf die Freigabe im Gespräch), „Nach neuen Fassungen sehen“ (sonst erreicht ein
 * Sicherheitsupdate niemanden; GitHub sieht dabei die IP-Adresse) und „Aufgaben aus Mails selbst anlegen“ (nichts
 * verlässt dabei den Rechner, jede Aufgabe hat „Rückgängig“). Bei jedem steht ein Satz, was dabei den Rechner verlässt
 * und an wen. Die Schalter sind die bisherigen Bausteine, die Reihenfolge ist die des Alltags.
 */
export function Darf() {
  const system = useSystem();
  return <div className="darf" role="list" aria-label="Was Kingfisher darf">
    <div role="listitem"><Wetter /></div>
    <div role="listitem"><Nachrichten /></div>
    <div role="listitem"><WegezeitSettings /></div>
    <div role="listitem"><section className="darf-zeile" aria-label={SCHALTER.autostart.titel}>
      <AutostartWahl titel={SCHALTER.autostart.titel} satz={fuerSystem(SCHALTER.autostart.verlaesst, system)} /></section></div>
    <div role="listitem"><Mitteilungen /></div>
    <div role="listitem"><CloudSchalter /></div>
    <div role="listitem"><CloudEinordnungSchalter /></div>
    <div role="listitem"><WebSchalter /></div>
    <div role="listitem"><FassungSchalter /></div>
    <div role="listitem"><AufgabenSelbstSchalter /></div>
  </div>;
}
