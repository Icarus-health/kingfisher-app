import {useEffect, useState, type FormEvent} from "react";
import {api, ApiError, type MailProvider} from "./api";
import {adresseLesen, adresseMerken} from "./adresseEntwurf";
import {hilfeText} from "./googleWeg";
import {MicrosoftAnmeldung} from "./MicrosoftAnmeldungKarte";
import {microsoftZuerst, standSatz} from "./microsoftAnmeldung";
import {EIGENER_SERVER, SCHON_VERBUNDEN_WO, SERVER_SATZ, STANDARD_PORT, adresseFertig as istFertig, anmeldeName, eigenerServer,
  erkanntText, nachsehenSatz, postfachName, schonVerbunden, schonVerbundenSatz, type Verbundenes} from "./postfachWeg";
import {kontenApi} from "./kontenApi";
import {PasswortFeld} from "./grundlage";
import {useAnbieter} from "./useAnbieter";
import {useImBlick} from "./useImBlick";

/**
 * Ein Postfach mit Adresse und Passwort, im Assistenten und unter Zugänge (Fremdprobe 2, Befunde 2 bis 4).
 *
 * Der Anbieter wird an der Adresse erkannt; für eine eigene Domain findet der Sidecar den Server selbst (Google
 * Workspace, Microsoft 365, SRV, Autoconfig, Mailserver beim Hoster). Dann steht „Erkannt: …“ da und nur das
 * Passwortfeld. Nur wenn nichts antwortet, fragt die Karte „Welcher Anbieter?“, und als letzte Möglichkeit
 * „Nicht dabei“ nach Servername und Port (Vorgabe 993), mit einem Satz, wo man ihn findet, hier und nicht in den
 * Einstellungen. Die zuletzt getippte Adresse steht schon da. Verbunden heißt angemeldet: Der Sidecar meldet sich
 * vor dem Speichern einmal an; lehnt der Server ab, steht der Grund direkt am Knopf, mit Fokus und Bildlauf.
 *
 * Ist die Adresse schon verbunden, sagt die Karte das gleich nach der Adresse, ruhig und mit dem Weg dorthin, statt
 * erst nach dem App-Passwort im roten Rahmen (Persona-Prüfung, Paket S, Befund 4).
 */
export function PostfachMitAdresse({anbieter, beiVerbunden, idPraefix = "erststart", zumPostfach}: {
  anbieter: MailProvider[];
  beiVerbunden: (meldung?: string) => void;
  idPraefix?: string;
  /** Unter Zugänge: führt zur Zeile des schon verbundenen Postfachs. Ohne steht, wo es zu finden ist. */
  zumPostfach?: (id: string) => void;
}) {
  const [adresse, setAdresse] = useState(adresseLesen);
  const [verbundene, setVerbundene] = useState<Verbundenes[]>([]);
  useEffect(() => {
    let aktiv = true;
    kontenApi.konten().then(antwort => { if (aktiv) setVerbundene(antwort.postfaecher); }).catch(() => undefined);
    return () => { aktiv = false; };
  }, []);
  // Was der Sidecar beim Speichern als schon verbunden meldet (409), steht ebenso ruhig da wie die Erkennung vorher.
  const [doppeltSatz, setDoppeltSatz] = useState("");
  const schon = schonVerbunden(adresse, verbundene);
  const [passwort, setPasswort] = useState("");
  const [gewaehlt, setGewaehlt] = useState("");
  const [server, setServer] = useState("");
  const [port, setPort] = useState(STANDARD_PORT);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const fehlerRef = useImBlick<HTMLParagraphElement>(fehler);
  // Eine Frage, eine Antwort (`anbieter_erkennen.py`): bekannter Anbieter, Google Workspace, Microsoft 365 oder der
  // selbst gefundene Server einer eigenen Domain. Daran verzweigt die Karte; gefragt wird niemand.
  // Schon verbunden: Es gibt nichts nachzusehen; auch die Domain wird dann nicht gefragt.
  const {anbieter: gefunden, prueft, erkennung} = useAnbieter(schon ? "" : adresse, anbieter);
  const adresseFertig = istFertig(adresse);
  const [mitPasswort, setMitPasswort] = useState(false);
  const [ohneApp, setOhneApp] = useState(false);
  const sauber = adresse.trim().toLowerCase();
  useEffect(() => { setMitPasswort(false); setOhneApp(false); setFehler(""); setDoppeltSatz(""); }, [sauber]);
  useEffect(() => { adresseMerken(adresse); }, [adresse]);
  // Microsoft 365 zuerst: Den Passwortweg (Outlook) gibt es dann erst auf Wunsch oder ohne Kennung der App.
  const ms = microsoftZuerst(erkennung);
  const erkannt = ms ? null : gefunden;
  const eigen = gewaehlt === EIGENER_SERVER ? eigenerServer(server, port) : null;
  const gilt = ms ? (mitPasswort || ohneApp ? gefunden : null)
    : erkannt ?? (gewaehlt === EIGENER_SERVER ? eigen : anbieter.find(eintrag => eintrag.id === gewaehlt) ?? null);
  const id = (name: string) => `${idPraefix}-${name}`;

  async function verbinden(event: FormEvent) {
    event.preventDefault();
    if (!gilt || arbeitet) return;
    setArbeitet(true); setFehler("");
    try {
      await api.addMailAccount({label: postfachName(adresse, gilt), user: anmeldeName(adresse, gilt), sender: adresse.trim(),
        imap_host: gilt.imap_host, imap_port: gilt.imap_port, smtp_host: gilt.smtp_host, smtp_port: gilt.smtp_port,
        ...(passwort ? {password: passwort} : {})});
      setPasswort(""); setAdresse(""); adresseMerken("");
      beiVerbunden();
    } catch (problem) {
      if (problem instanceof ApiError && problem.status === 409 && problem.detail) { setDoppeltSatz(problem.detail); return; }
      setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Das Postfach konnte nicht gespeichert werden. Bitte prüfe die Angaben.");
    } finally { setArbeitet(false); }
  }

  const wer = gilt ? (gilt.id === EIGENER_SERVER || gilt.id === "gefunden" ? `dem Mailserver ${gilt.imap_host}` : gilt.label) : "";
  return <form className="erststart-formular postfach-adresse" onSubmit={verbinden}>
    <label htmlFor={id("adresse")}>Deine Mailadresse</label>
    <input id={id("adresse")} type="email" value={adresse} autoComplete="email" placeholder="name@beispiel.de" onChange={event => setAdresse(event.target.value)} />
    {schon || doppeltSatz ? <p className="source-hint postfach-schon" role="status">
      {schon ? schonVerbundenSatz(schon.name) : doppeltSatz}{" "}
      {schon && zumPostfach ? <button type="button" className="text-action" onClick={() => zumPostfach(schon.id)}>Zum Postfach</button>
        : SCHON_VERBUNDEN_WO}
    </p> : null}
    {schon ? null : <>
    {adresseFertig && ms ? <>
      <p className="erststart-ok" role="status">Erkannt: Microsoft 365 deiner Hochschule oder Firma</p>
      {!mitPasswort ? <>
        <MicrosoftAnmeldung adresse={adresse.trim()} beiVerbunden={stand => { setAdresse(""); adresseMerken(""); beiVerbunden(standSatz(stand)); }} ohneApp={() => setOhneApp(true)} />
        {!ohneApp ? <button type="button" className="text-action" onClick={() => setMitPasswort(true)}>Lieber mit Adresse und Passwort</button> : null}
      </> : null}
    </> : null}
    {adresseFertig && prueft ? <p className="source-hint" role="status">Kingfisher sieht nach, wo deine Mail liegt … {nachsehenSatz(adresse)}</p> : null}
    {adresseFertig && !erkannt && !prueft && !ms ? <>
      <label htmlFor={id("anbieter")}>Welcher Anbieter?</label>
      <select id={id("anbieter")} value={gewaehlt} onChange={event => setGewaehlt(event.target.value)}>
        <option value="">Bitte wählen</option>
        {anbieter.map(eintrag => <option key={eintrag.id} value={eintrag.id}>{eintrag.label}</option>)}
        <option value={EIGENER_SERVER}>Nicht dabei: Mailserver selbst eintragen</option>
      </select>
      {!gewaehlt ? <p className="source-hint">Kingfisher hat zu {adresse.trim().split("@").pop()} keine Angaben gefunden. Ist dein Anbieter nicht in der Liste, wähle „Nicht dabei“.</p> : null}
      {gewaehlt === EIGENER_SERVER ? <div className="postfach-server">
        <label htmlFor={id("server")}>Name des Mailservers</label>
        <input id={id("server")} value={server} placeholder="mail.beispiel.de" autoCapitalize="off" spellCheck={false} onChange={event => setServer(event.target.value)} />
        <label htmlFor={id("port")}>Port</label>
        <input id={id("port")} type="number" min={1} max={65535} value={port} onChange={event => setPort(Number(event.target.value))} />
        <p className="source-hint">{SERVER_SATZ} Den Port ändert fast niemand.</p>
      </div> : null}
    </> : null}
    {adresseFertig && erkannt ? <p className="erststart-ok" role="status">{erkanntText(erkannt)}</p> : null}
    {gilt ? <>
      <label htmlFor={id("passwort")}>{gilt.app_password ? "App-Passwort" : "Passwort deines Postfachs"}</label>
      <PasswortFeld id={id("passwort")} wert={passwort} onWert={setPasswort} />
      {gilt.hint ? <p className="source-hint">{gilt.hint}{gilt.help_url ? <> <a href={gilt.help_url} rel="noreferrer" target="_blank">{hilfeText(gilt)}</a></> : null}</p> : null}
      <p className="source-hint">Das Passwort bleibt im Schlüsselbund dieses Rechners und wird nicht wieder angezeigt.</p>
      <button className="primary-action" type="submit" disabled={arbeitet || !adresseFertig || !passwort}>{arbeitet ? "Wird verbunden …" : "Postfach verbinden"}</button>
    </> : null}
    {arbeitet && gilt ? <p role="status" className="source-hint">Kingfisher meldet sich bei {wer} an. Das dauert höchstens ein paar Sekunden.</p> : null}
    {fehler ? <p ref={fehlerRef} tabIndex={-1} role="alert" className="settings-error am-knopf">{fehler}</p> : null}
    </>}
  </form>;
}
