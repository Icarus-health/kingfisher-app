import {useEffect, useState} from "react";
import {api, type MailAccount, type MailProvider} from "../api";
import {GoogleKalenderAdresse} from "../GoogleKalenderAdresse";
import {GoogleSignIn} from "../GoogleSignIn";
import {googleAnmeldungVorne} from "../googleWeg";
import {useGoogleKonfiguration} from "../useAnbieter";
import {KalenderMitAdresse} from "../KalenderMitAdresse";
import {MacCalendarSettings} from "../MacCalendarSettings";
import {useSystem} from "../useSystem";
import {Verweis} from "../Verweis";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";

type Weg = "adresse" | "google" | "mac";

/**
 * (c) „Deinen Kalender verbinden“: mit der Mailadresse wie bei der Post (Befund 7), mit Google oder der Kalender dieses
 * Macs. Der Weg mit der Adresse steht offen da, die Adresse des Postfachs ist eingetragen und dessen Passwort gilt; zu
 * tippen bleibt dann nichts. Für eine eigene Domain sucht Kingfisher den Kalender beim Mailserver (Fremdprobe 2,
 * Befund 5); erst danach fragt die Karte nach einer Adresse. Überspringen geht immer. Ein Kalender-Abo mit eigener Adresse steht unter Zugänge.
 * Den Weg über den Mac-Kalender gibt es nur mit dem Helfer auf dem Mac (Befund 18), wie unter Zugänge. „Google-Kalender“
 * geht ohne Cloud-Projekt über die geheime iCal-Adresse (Befund 2); „Mit Google anmelden“ steht nur da, wenn ein
 * Techniker es eingerichtet hat.
 */
export function KalenderSchritt({stand, neuLesen, weiter, ueberspringen, zurueck}: SchrittProps) {
  const system = useSystem();
  const googleVorne = googleAnmeldungVorne(useGoogleKonfiguration());
  const [anbieter, setAnbieter] = useState<MailProvider[]>([]);
  const [postfaecher, setPostfaecher] = useState<MailAccount[]>([]);
  // Der Weg mit der Adresse steht gleich offen (Fremdprobe 2, Befund 5): Kingfisher findet den Kalender selbst, wo es geht.
  const [weg, setWeg] = useState<Weg | null>("adresse");
  // Ist ein Kalender verbunden, treten die Wege zurück: „Weiteren Kalender verbinden“ holt sie wieder (Fremdprobe 3, Befund 7).
  const [nochEins, setNochEins] = useState(false);
  const [meldung, setMeldung] = useState("");
  const verbundenJetzt = (satz = "") => { setMeldung(satz); setNochEins(false); void neuLesen(); };
  useEffect(() => {
    let aktiv = true;
    Promise.all([api.mailProviders(), api.integrations()]).then(([katalog, overview]) => {
      if (!aktiv) return;
      setAnbieter(katalog.providers); setPostfaecher(overview.mail_accounts);
    }).catch(() => undefined);
    return () => { aktiv = false; };
  }, []);
  const verbunden = stand.vorhanden.kalender;
  const wege = !verbunden || nochEins;
  const knopf = (id: Weg, text: string) => <button type="button" className={`secondary-action${weg === id ? " ist-gewaehlt" : ""}`}
    aria-pressed={weg === id} onClick={() => setWeg(id)}>{text}</button>;
  return <div className="erststart-inhalt">
    <p>Mit deinem Kalender kann Kingfisher dich auf Termine vorbereiten und weiß, wann du Zeit hast. Es liest nur; Termine ändert es nicht.</p>
    {verbunden ? <p className="erststart-ok" role="status">{meldung || "Dein Kalender ist verbunden."}</p> : null}
    {wege ? <>
      <div className="erststart-wege" role="group" aria-label="Welchen Kalender möchtest du verbinden?">
        {knopf("adresse", "Mit Adresse und Passwort")}
        {knopf("google", "Google-Kalender")}
        {system.mac_helfer ? knopf("mac", "Kalender auf diesem Mac") : null}
      </div>
      {weg === "adresse" ? <KalenderMitAdresse anbieter={anbieter} postfaecher={postfaecher} beiVerbunden={(_, satz) => verbundenJetzt(satz)} /> : null}
      {weg === "google" && googleVorne ? <GoogleSignIn active kind="calendar" onConnected={() => verbundenJetzt()} /> : null}
      {weg === "google" ? <GoogleKalenderAdresse beiVerbunden={(_, satz) => verbundenJetzt(satz)} /> : null}
      {weg === "mac" && system.mac_helfer ? <MacCalendarSettings /> : null}
    </> : <button type="button" className="text-action" onClick={() => { setMeldung(""); setNochEins(true); }}>Weiteren Kalender verbinden</button>}
    <p className="source-hint">Ein Kalender-Abo mit eigener Adresse verbindest du später unter <Verweis ziel="zugaenge" />.</p>
    <SchrittFuss erledigt={verbunden} zurueck={zurueck} weiter={() => void weiter()} ueberspringen={() => void ueberspringen()} />
  </div>;
}
