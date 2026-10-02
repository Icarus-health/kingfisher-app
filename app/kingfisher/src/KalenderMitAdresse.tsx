import {useEffect, useState, type FormEvent} from "react";
import {api, ApiError, type IntegrationOverview, type MailAccount, type MailProvider} from "./api";
import {GoogleKalenderAdresse} from "./GoogleKalenderAdresse";
import {ADRESSE_FEHLT, ADRESSE_WO, SELBST_SUCHEN, kalenderWeg, postfachZurAdresse, verbundenSatz} from "./kalenderWeg";
import {hilfeText} from "./googleWeg";
import {adresseLesen} from "./adresseEntwurf";
import {useAnbieter} from "./useAnbieter";
import {useImBlick} from "./useImBlick";

/**
 * Kalender wie Mail (Fremdprobe, Befund 7): Die Mailadresse genügt. Der Anbieter wird an ihr erkannt, Kingfisher sucht
 * den Kalender selbst und meldet sich vor dem Speichern einmal an; scheitert das, steht der Grund in einem Satz da.
 * Gibt es schon ein Postfach mit dieser Adresse, gilt dessen Passwort (nichts zweimal eingeben). Kennt der Katalog den
 * Anbieter nicht (eigene Domain), sucht Kingfisher den Kalender selbst beim Mailserver der Domain (Fremdprobe 2,
 * Befund 5); erst wenn dort nichts antwortet, fragt die Karte nach der Adresse, mit einem Satz, wo sie steht. Bei
 * Microsoft steht der Weg über einen veröffentlichten Kalender da, mit Link zur richtigen Seite in Outlook. Bei Google (auch Workspace mit eigener
 * Domain, am Mailserver erkannt) geht es ohne Passwort über die geheime iCal-Adresse (Befund 2). Nach dem Verbinden steht
 * der Satz da, kein zweiter Knopf zum Verbinden (Fremdprobe 3, Befund 7). Im Assistenten und unter Zugänge.
 */
export function KalenderMitAdresse({anbieter, postfaecher, beiVerbunden}: {
  anbieter: MailProvider[];
  postfaecher: MailAccount[];
  /** Nach dem Verbinden, mit dem Satz, was verbunden wurde (der Assistent zeigt ihn weiter, wenn die Karte verschwindet). */
  beiVerbunden: (overview: IntegrationOverview, satz: string) => void;
}) {
  const [adresse, setAdresse] = useState("");
  const [beruehrt, setBeruehrt] = useState(false);
  const [passwort, setPasswort] = useState("");
  const [eigenesPasswort, setEigenesPasswort] = useState(false);
  const [url, setUrl] = useState("");
  const [adresseVerlangt, setAdresseVerlangt] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [erfolg, setErfolg] = useState("");
  const fehlerRef = useImBlick<HTMLParagraphElement>(fehler);

  // Die Adresse des ersten Postfachs steht schon da, sonst die zuletzt getippte; getippt wird sie nicht noch einmal.
  useEffect(() => {
    if (beruehrt || adresse) return;
    const vorhanden = postfaecher.find(konto => konto.secret_present)?.user ?? postfaecher[0]?.user ?? adresseLesen();
    if (vorhanden) setAdresse(vorhanden);
  }, [postfaecher, beruehrt, adresse]);

  const vomServer = useAnbieter(adresse, anbieter);
  const weg = kalenderWeg(adresse, anbieter, adresseVerlangt, vomServer.anbieter);
  const postfach = eigenesPasswort ? null : postfachZurAdresse(adresse, postfaecher);
  const wer = weg.art !== "unvollstaendig" && weg.anbieter ? weg.anbieter.label : "deinem Anbieter";
  const kannVerbinden = !arbeitet && (weg.art === "bekannt" || weg.art === "selbst_suchen"
    || (weg.art === "adresse_fehlt" && url.trim().startsWith("https://")))
    && (Boolean(postfach) || passwort.length > 0);

  async function verbinden(event: FormEvent) {
    event.preventDefault();
    if (!kannVerbinden) return;
    setArbeitet(true); setFehler(""); setErfolg("");
    try {
      const antwort = await api.kalenderAnmelden({adresse: adresse.trim(),
        ...(postfach ? {mail_konto: postfach.id} : {password: passwort}),
        ...(weg.art === "adresse_fehlt" ? {url: url.trim()} : {})});
      setPasswort("");
      const satz = verbundenSatz(antwort.gefunden, antwort.neu);
      setErfolg(satz);
      beiVerbunden(antwort, satz);
    } catch (problem) {
      // Nichts gefunden: Dann steht das Feld für die Adresse da, mit dem Satz, wo sie steht; kein zweiter Satz darüber.
      const verlangt = problem instanceof ApiError && (problem.grund === "adresse_fehlt" || problem.grund === "kein_kalender");
      if (verlangt) setAdresseVerlangt(true);
      if (problem instanceof ApiError && problem.grund === "passwort_fehlt") setEigenesPasswort(true);
      if (!(verlangt && weg.art === "selbst_suchen")) setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Der Kalender konnte gerade nicht verbunden werden. Bitte versuche es noch einmal.");
    } finally { setArbeitet(false); }
  }

  // Solange der Sidecar am Mailserver nachsieht, fragt die Karte noch nicht nach einer Adresse.
  const offen = weg.art === "adresse_fehlt" && !vomServer.prueft;
  return <><form className="kalender-adresse erststart-formular" onSubmit={verbinden}>
    <label htmlFor="kalender-adresse">Deine Mailadresse</label>
    <input id="kalender-adresse" type="email" value={adresse} autoComplete="email" placeholder="name@beispiel.de"
      onChange={event => { setBeruehrt(true); setAdresse(event.target.value); setAdresseVerlangt(false); setFehler(""); setErfolg(""); }} />
    {weg.art === "bekannt" ? <p className="erststart-ok" role="status">Erkannt: {weg.anbieter.label}. Kingfisher findet deinen Kalender selbst.</p> : null}
    {weg.art === "google_ical" ? <p className="erststart-ok" role="status">Erkannt: {weg.anbieter.label}. Dein Kalender geht ohne Passwort über seine Adresse.</p> : null}
    {weg.art === "kein_zugang" ? <p className="source-hint" role="status">{weg.satz}</p> : null}
    {weg.art === "selbst_suchen" && !vomServer.prueft ? <p className="source-hint" role="status">{SELBST_SUCHEN}</p> : null}
    {(weg.art === "adresse_fehlt" || weg.art === "selbst_suchen") && vomServer.prueft ? <p className="source-hint" role="status">Kingfisher sieht nach, wo deine Mail liegt …</p> : null}
    {offen ? <>
      <p className="source-hint" role="status">{ADRESSE_FEHLT}</p>
      <label htmlFor="kalender-url">Adresse deines Kalenders</label>
      <input id="kalender-url" type="url" value={url} placeholder="https://…" onChange={event => setUrl(event.target.value)} />
      <p className="source-hint">{ADRESSE_WO}</p>
    </> : null}
    {weg.art === "bekannt" || offen || (weg.art === "selbst_suchen" && !vomServer.prueft) ? <>
      {postfach ? <p className="source-hint">Kingfisher nimmt dasselbe Passwort wie für dein Postfach. <button type="button" className="text-action" onClick={() => setEigenesPasswort(true)}>Anderes Passwort eingeben</button></p>
        : <>
          <label htmlFor="kalender-passwort">{weg.passwortLabel}</label>
          <input id="kalender-passwort" type="password" value={passwort} autoComplete="new-password" onChange={event => setPasswort(event.target.value)} />
          {weg.anbieter?.app_password && weg.anbieter.hint ? <p className="source-hint">{weg.anbieter.hint}{weg.anbieter.help_url ? <> <a href={weg.anbieter.help_url} rel="noreferrer" target="_blank">{hilfeText(weg.anbieter)}</a></> : null}</p> : null}
          <p className="source-hint">Das Passwort bleibt im Schlüsselbund dieses Rechners. Es geht nur an {wer}, wenn du auf den Knopf darunter klickst.</p>
        </>}
      {erfolg ? null : <button className="primary-action" type="submit" disabled={!kannVerbinden}>{arbeitet ? "Wird verbunden …" : weg.art === "selbst_suchen" ? "Kalender suchen und verbinden" : "Kalender verbinden"}</button>}
    </> : null}
    {arbeitet ? <p role="status" className="source-hint">Kingfisher meldet sich bei {wer} an und sucht deinen Kalender. Das dauert höchstens ein paar Sekunden.</p> : null}
    {erfolg ? <p role="status" className="erststart-ok">{erfolg}</p> : null}
    {fehler ? <p ref={fehlerRef} tabIndex={-1} role="alert" className="settings-error am-knopf">{fehler}</p> : null}
  </form>
  {weg.art === "google_ical" ? <GoogleKalenderAdresse beiVerbunden={(antwort, satz) => beiVerbunden(antwort, satz)} /> : null}
  {weg.art === "kein_zugang" && weg.anbieter.id === "outlook" ? <GoogleKalenderAdresse beiVerbunden={(antwort, satz) => beiVerbunden(antwort, satz)}
    variante={{art: "microsoft", konto: vomServer.erkennung?.art === "organisation" ? "organisation" : "privat"}} /> : null}
  </>;
}
