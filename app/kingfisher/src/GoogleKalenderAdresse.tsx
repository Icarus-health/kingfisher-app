import {useState, type FormEvent} from "react";
import {api, ApiError, type IntegrationOverview} from "./api";
import {ADRESSE_FELD, KALENDER_EINSTELLUNGEN, WO_FINDEN, aboVerbundenSatz, siehtNachAdresseAus} from "./googleWeg";
import {MICROSOFT_EINSTELLUNGEN, MICROSOFT_WO_FINDEN} from "./kalenderWeg";
import {useImBlick} from "./useImBlick";

/** Microsoft (Fremdprobe 2, Befund 5): derselbe Weg über eine Abo-Adresse, mit dem Weg in Outlook und Link dorthin. */
export type AboVariante = {art: "google"} | {art: "microsoft"; konto: "privat" | "organisation"};

/**
 * Google-Kalender ohne eigenes Cloud-Projekt (Fremdprobe, Befund 2): die geheime Adresse im iCal-Format einfügen, fertig.
 * Kingfisher ruft sie vor dem Speichern einmal ab (Zeitgrenze, gültiger Kalender) und sagt sonst in einem Satz, was nicht
 * stimmt. Nur lesend; hinaus geht nichts außer dem Abruf dieser Adresse. Im Assistenten und unter Zugänge.
 */
export function GoogleKalenderAdresse({beiVerbunden, variante = {art: "google"}}: {
  /** `satz`: „Verbunden: …“; der Assistent zeigt ihn weiter, wenn die Wege nach dem Erfolg zurücktreten (Fremdprobe 3, Befund 7). */
  beiVerbunden: (overview: IntegrationOverview, satz: string) => void;
  variante?: AboVariante;
}) {
  const [url, setUrl] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [erfolg, setErfolg] = useState("");
  const bereit = !arbeitet && siehtNachAdresseAus(url);
  const fehlerRef = useImBlick<HTMLParagraphElement>(fehler);
  const ms = variante.art === "microsoft";

  async function verbinden(event: FormEvent) {
    event.preventDefault();
    if (!bereit) return;
    setArbeitet(true); setFehler(""); setErfolg("");
    try {
      const antwort = await api.kalenderAbo({url: url.trim()});
      setUrl("");
      const satz = aboVerbundenSatz(antwort.gefunden, antwort.termine, antwort.neu);
      setErfolg(satz);
      beiVerbunden(antwort, satz);
    } catch (problem) {
      setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Der Kalender konnte gerade nicht verbunden werden. Bitte versuche es noch einmal.");
    } finally { setArbeitet(false); }
  }

  return <form className="google-kalender-adresse erststart-formular" aria-label={ms ? "Outlook-Kalender mit seiner Adresse verbinden" : "Google-Kalender mit seiner Adresse verbinden"} onSubmit={verbinden}>
    {ms ? <p className="source-hint">{MICROSOFT_WO_FINDEN} <a href={MICROSOFT_EINSTELLUNGEN[variante.konto]} rel="noreferrer" target="_blank">Zu den Kalendereinstellungen von Outlook</a></p>
      : <p className="source-hint">{WO_FINDEN} <a href={KALENDER_EINSTELLUNGEN} rel="noreferrer" target="_blank">Zu den Einstellungen von Google Kalender</a></p>}
    <label htmlFor="google-kalender-url">{ms ? "Link deines veröffentlichten Kalenders" : ADRESSE_FELD}</label>
    <input id="google-kalender-url" type="url" value={url} autoComplete="off" spellCheck={false}
      placeholder={ms ? "https://outlook.office365.com/owa/calendar/…/calendar.ics" : "https://calendar.google.com/calendar/ical/…/basic.ics"}
      onChange={event => { setUrl(event.target.value); setFehler(""); setErfolg(""); }} />
    <button className="primary-action" type="submit" disabled={!bereit}>{arbeitet ? "Wird geprüft …" : "Kalender verbinden"}</button>
    {arbeitet ? <p role="status" className="source-hint">Kingfisher ruft die Adresse einmal ab und prüft, ob dort dein Kalender liegt. Das dauert höchstens ein paar Sekunden.</p> : null}
    {erfolg ? <p role="status" className="erststart-ok">{erfolg}</p> : null}
    {fehler ? <p ref={fehlerRef} tabIndex={-1} role="alert" className="settings-error am-knopf">{fehler}</p> : null}
  </form>;
}
