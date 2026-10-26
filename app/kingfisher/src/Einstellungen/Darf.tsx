import { AutostartWahl } from "../Einrichtung/AutostartWahl";
import { Nachrichten, Wetter } from "../WeltSettings";
import { WegezeitSettings } from "../WegezeitSettings";
import { CloudSchalter } from "./CloudSchalter";
import { Mitteilungen } from "./Mitteilungen";
import { CloudEinordnungSchalter } from "./CloudEinordnungSchalter";
import { AufgabenSelbstSchalter } from "./AufgabenSelbstSchalter";
import { SCHALTER } from "./gliederung";
import { fuerSystem } from "../system";
import { useSystem } from "../useSystem";

/**
 * Einstellungen → Was Kingfisher darf: die Dinge, die etwas nach außen schicken oder im Hintergrund laufen, als
 * Schalter untereinander. Alle sind aus, bis man sie einschaltet, außer „Aufgaben aus Mails selbst anlegen“ (nichts
 * verlässt dabei den Rechner, jede Aufgabe hat „Rückgängig“); bei jedem steht ein Satz, was dabei den Rechner
 * verlässt. Die Schalter sind die bisherigen Bausteine, die Reihenfolge ist die des Alltags.
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
    <div role="listitem"><AufgabenSelbstSchalter /></div>
  </div>;
}
