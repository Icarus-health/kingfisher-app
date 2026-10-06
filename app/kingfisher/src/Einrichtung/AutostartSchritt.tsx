import {useState} from "react";
import type {AutostartStand} from "../api";
import {AUTOSTART_WARUM, autostartBeantwortet} from "./autostart";
import {AutostartWahl} from "./AutostartWahl";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";
import {Verweis} from "../VerweisLink";

/** „Kingfisher beim Anmelden starten?“ Eine Frage, keine Vorgabe: Der Schalter ist aus, bis man ihn einschaltet. */
export function AutostartSchritt({weiter, ueberspringen, zurueck}: SchrittProps) {
  const [stand, setStand] = useState<AutostartStand | null>(null);
  return <div className="erststart-inhalt">
    <p>{AUTOSTART_WARUM}</p>
    <AutostartWahl beiAenderung={setStand} />
    <p className="source-hint">Du kannst das jederzeit unter <Verweis ziel="darf" /> ändern. Den Schlaf des Rechners hält Kingfisher nie auf.</p>
    <SchrittFuss erledigt={autostartBeantwortet(stand)} zurueck={zurueck} weiter={() => void weiter()} ueberspringen={() => void ueberspringen()} />
  </div>;
}
