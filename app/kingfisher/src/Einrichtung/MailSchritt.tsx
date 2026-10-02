import {useEffect, useState} from "react";
import {api, type MailProvider} from "../api";
import {GoogleSignIn} from "../GoogleSignIn";
import {MailEinlesen} from "./MailEinlesen";
import {googleAnmeldungVorne} from "../googleWeg";
import {PostfachMitAdresse} from "../PostfachMitAdresse";
import {useGoogleKonfiguration} from "../useAnbieter";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";
import {usePostfaecher} from "./usePostfaecher";
import {kontoSatz} from "../microsoftAnmeldung";

/**
 * (b) „Deine Mail verbinden“: Adresse mit Passwort (bei Gmail ein App-Passwort, Befund 2); danach ein Klick zum Einlesen.
 * „Mit Google anmelden“ steht nur da, wenn ein Techniker es eingerichtet hat; sonst gibt es nur den Weg, der geht.
 */
export function MailSchritt({stand, neuLesen, weiter, ueberspringen, zurueck}: SchrittProps) {
  const [weg, setWeg] = useState<"google" | "adresse" | null>(null);
  const [anbieter, setAnbieter] = useState<MailProvider[]>([]);
  const [nochEins, setNochEins] = useState(false);
  const [runde, setRunde] = useState(0);
  // Nach „Mit Microsoft anmelden“ bleibt der Satz stehen, was verbunden wurde (Post und Kalender in einem).
  const [meldung, setMeldung] = useState("");
  const verbundenJetzt = (satz?: string) => { setMeldung(satz ?? ""); setNochEins(false); setWeg(null); setRunde(wert => wert + 1); void neuLesen(); };
  useEffect(() => { api.mailProviders().then(antwort => setAnbieter(antwort.providers)).catch(() => undefined); }, []);
  const verbunden = stand.vorhanden.mail;
  const wege = !verbunden || nochEins;
  const googleVorne = googleAnmeldungVorne(useGoogleKonfiguration());
  const zeigtAdresse = weg === "adresse" || !googleVorne;
  // „Verbunden“ steht nur da, wenn das Postfach auch antwortet (Befunde 3 und 5); sonst der Grund und ein Weg.
  const {stumm, prueft, pruefen} = usePostfaecher(verbunden);
  useEffect(() => { if (runde > 0 && verbunden) void pruefen(); }, [runde, verbunden, pruefen]);
  // Microsoft-Konto verbunden, aber die Karte hat ihren Satz nicht mehr melden können (sie verschwand beim Neulesen):
  // der Satz kommt aus dem gespeicherten Konto.
  useEffect(() => {
    if (!verbunden || meldung) return;
    let aktiv = true;
    api.microsoftKonten().then(antwort => {
      const satz = antwort.konten.map(kontoSatz).find(Boolean);
      if (aktiv && satz) setMeldung(satz);
    }).catch(() => undefined);
    return () => { aktiv = false; };
  }, [verbunden, meldung, runde]);
  const [entfernt, setEntfernt] = useState("");
  async function neuVerbinden(kontoId: string) {
    setEntfernt("");
    try {
      await api.removeIntegration("mail", kontoId);
      setWeg("adresse"); setNochEins(true);
      await neuLesen(); await pruefen();
    } catch { setEntfernt("Das Postfach konnte gerade nicht entfernt werden. Bitte versuche es noch einmal."); }
  }

  return <div className="erststart-inhalt">
    <p>Mit deiner Mail weiß Kingfisher, wer dir schreibt, was ansteht und worauf du wartest. Es liest nur mit und verschickt nichts ohne dein Ja.</p>
    {verbunden ? <>
      {stumm === null ? <p role="status" className="source-hint">Kingfisher prüft, ob dein Postfach antwortet …</p>
        : stumm.length ? <section className="erststart-stumm" role="alert" aria-label="Postfach antwortet nicht">
          {stumm.map(konto => <div key={konto.account_id} className="erststart-knoepfe">
            <p>{konto.satz}</p>
            <button type="button" className="secondary-action" onClick={() => void neuVerbinden(konto.account_id)}>{konto.label} neu verbinden</button>
          </div>)}
          <button type="button" className="text-action" disabled={prueft} onClick={() => void pruefen()}>{prueft ? "Wird geprüft …" : "Erneut prüfen"}</button>
        </section>
        : <p className="erststart-ok" role="status">Dein Postfach ist verbunden.</p>}
      {meldung ? <p role="status" className="erststart-ok">{meldung}</p> : null}
      {entfernt ? <p role="alert" className="settings-error">{entfernt}</p> : null}
      <MailEinlesen key={runde} />
    </> : null}
    {wege && googleVorne ? <div className="erststart-wege" role="group" aria-label="Wie möchtest du dich verbinden?">
      <button type="button" className={`secondary-action${weg === "google" ? " ist-gewaehlt" : ""}`} aria-pressed={weg === "google"} onClick={() => setWeg("google")}>Mit Google anmelden</button>
      <button type="button" className={`secondary-action${weg === "adresse" ? " ist-gewaehlt" : ""}`} aria-pressed={weg === "adresse"} onClick={() => setWeg("adresse")}>Mit Adresse und Passwort</button>
    </div> : null}
    {!wege ? <button type="button" className="text-action" onClick={() => setNochEins(true)}>Noch ein Postfach verbinden</button> : null}
    {wege && googleVorne && weg === "google" ? <GoogleSignIn active kind="mail" onConnected={verbundenJetzt} /> : null}
    {wege && zeigtAdresse ? <PostfachMitAdresse anbieter={anbieter} beiVerbunden={verbundenJetzt} /> : null}
    <SchrittFuss erledigt={verbunden} zurueck={zurueck} weiter={() => void weiter()} ueberspringen={() => void ueberspringen()} />
  </div>;
}
