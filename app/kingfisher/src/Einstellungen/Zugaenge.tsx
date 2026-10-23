import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { api, ApiError, type IntegrationOverview, type MailProvider, type MailStand } from "../api";
import { DocumentImport } from "../DocumentImport";
import { FolderSyncSettings } from "../FolderSyncSettings";
import { GoogleSignIn } from "../GoogleSignIn";
import { googleAnmeldungVorne } from "../googleWeg";
import { useGoogleKonfiguration } from "../useAnbieter";
import { InterfaceIcon } from "../InterfaceIcon";
import { KalenderMitAdresse } from "../KalenderMitAdresse";
import { MacCalendarSettings } from "../MacCalendarSettings";
import { MicrosoftZugang } from "../MicrosoftZugang";
import { PostfachMitAdresse } from "../PostfachMitAdresse";
import { adresseLesen } from "../adresseEntwurf";
import { useSystem } from "../useSystem";
import { TranscriptSettings } from "../TranscriptSettings";
import { icon } from "../ui";
import { gefuellterZugang, ZUGAENGE } from "./gliederung";
import { NeuAnmelden } from "./NeuAnmelden";
import { angemeldetSatz, googleNeuSatz, neuAnmeldenWeg } from "./neuAnmeldenWeg";
import {
  CalendarSourceForm, EMPTY_CALENDAR_FORM, EMPTY_MAIL_FORM, MailSourceForm, SourceRow, sourceState,
  type CalendarForm, type MailForm,
} from "./Quellenformulare";

/** Der Stand der verbundenen Postfächer und Kalender; die Seite liest ihn einmal und gibt ihn an alle weiter, die ihn brauchen. */
export function useIntegrationen() {
  const [overview, setOverview] = useState<IntegrationOverview | null>(null);
  const [providers, setProviders] = useState<MailProvider[]>([]);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    setError("");
    Promise.all([api.integrations(), api.mailProviders()]).then(([nextOverview, catalogue]) => {
      setOverview(nextOverview);
      setProviders(catalogue.providers);
    }).catch(() => setError("Die lokalen Integrationen sind gerade nicht erreichbar."));
  }, []);
  useEffect(() => { load(); }, [load]);
  return { overview, setOverview, providers, error, setError, load };
}
export type Integrationen = ReturnType<typeof useIntegrationen>;

const zaehlen = (anzahl: number, einzahl: string, mehrzahl: string) => anzahl === 0 ? "" : `${anzahl} ${anzahl === 1 ? einzahl : mehrzahl} verbunden`;

/**
 * Einstellungen → Zugänge: Postfächer, Kalender, Ordner. Verbinden, trennen, Stand. Die Bausteine sind die bisherigen
 * Karten; hier stehen sie nur unter einer Überschrift in Alltagssprache. Nichts wird ohne Klick verbunden, und
 * „Trennen“ löscht nur den lokalen Zugang, nicht die Daten beim Anbieter.
 */
export function Zugaenge({ integrationen, aktiv, einrichtungOffen = false }: { integrationen: Integrationen; aktiv: boolean; einrichtungOffen?: boolean }) {
  const system = useSystem();
  // „Mit Google anmelden“ nur, wenn ein Techniker es eingerichtet hat (Befund 2); sonst kein gesperrter Knopf vorne.
  const googleVorne = googleAnmeldungVorne(useGoogleKonfiguration());
  const { overview, setOverview, providers, setError, load } = integrationen;
  const [openForm, setOpenForm] = useState<"mail" | "calendar" | null>(null);
  const [mail, setMail] = useState<MailForm>(EMPTY_MAIL_FORM);
  const [calendar, setCalendar] = useState<CalendarForm>(EMPTY_CALENDAR_FORM);
  const [submitting, setSubmitting] = useState(false);
  // Was beim Speichern abgelehnt wurde, steht am Formular und nicht oben auf der Seite (Fremdprobe 2, Befund 4).
  const [formFehler, setFormFehler] = useState("");
  const [removing, setRemoving] = useState<{ kind: "mail" | "calendar"; id: string } | null>(null);
  // Die eine Aussage je Postfach (mail_stand.py): Verweist sie hierher (Anmeldung abgelaufen, Passwort fehlt), steht am
  // Postfach „Neu anmelden“. Nach dem Anmelden gilt der Satz erst beim nächsten Abruf als erledigt; bis dahin steht hier,
  // dass es geklappt hat, statt derselben Aufforderung noch einmal.
  const [staende, setStaende] = useState<Record<string, MailStand>>({});
  const [angemeldet, setAngemeldet] = useState<Record<string, string>>({});
  // Nach dem Neu-Anmelden landet der Fokus auf der Bestätigung (die Statuszeile steht dafür immer im DOM).
  const [fokusAuf, setFokusAuf] = useState<string | null>(null);
  const statusZeilen = useRef<Record<string, HTMLParagraphElement | null>>({});
  useEffect(() => {
    if (!fokusAuf) return;
    statusZeilen.current[fokusAuf]?.focus();
    setFokusAuf(null);
  }, [fokusAuf]);
  const standLaden = useCallback(() => {
    api.mailStand().then(daten => setStaende(Object.fromEntries(daten.accounts.map(eintrag => [eintrag.account_id, eintrag]))))
      .catch(() => { /* Ohne Stand bleibt die Seite wie bisher; „Postfach hinzufügen“ geht trotzdem. */ });
  }, []);
  useEffect(() => { if (aktiv) standLaden(); }, [aktiv, standLaden]);

  function chooseProvider(providerId: string) {
    const provider = providers.find((item) => item.id === providerId);
    setMail((current) => ({
      ...current,
      provider: providerId,
      imap_host: provider?.imap_host ?? "",
      imap_port: provider?.imap_port ?? 993,
      smtp_host: provider?.smtp_host ?? "",
      smtp_port: provider?.smtp_port ?? 587,
    }));
  }

  async function addMail(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setFormFehler("");
    try {
      const next = await api.addMailAccount({
        label: mail.label, user: mail.user, sender: mail.sender,
        imap_host: mail.imap_host, imap_port: mail.imap_port,
        smtp_host: mail.smtp_host, smtp_port: mail.smtp_port,
        ...(mail.password ? { password: mail.password } : {}),
      });
      setOverview(next);
      setMail(EMPTY_MAIL_FORM);
      setOpenForm(null);
    } catch (problem) {
      // Mit Passwort meldet sich der Sidecar vorher an; scheitert das, steht der Grund in einem Satz in `detail` (Befund 3),
      // am Knopf des Formulars (Fremdprobe 2, Befund 4).
      setFormFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Das Postfach konnte nicht gespeichert werden. Bitte prüfe die Angaben.");
    } finally {
      setSubmitting(false);
    }
  }

  async function addCalendar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true);
    setFormFehler("");
    try {
      const next = await api.addCalendarSource({
        label: calendar.label, kind: calendar.kind, url: calendar.url,
        ...(calendar.kind === "caldav" && calendar.user ? { user: calendar.user } : {}),
        ...(calendar.kind === "caldav" && calendar.password ? { password: calendar.password } : {}),
      });
      setOverview(next);
      setCalendar(EMPTY_CALENDAR_FORM);
      setOpenForm(null);
    } catch (problem) {
      // Mit Passwort meldet sich der Sidecar vorher an; scheitert das, steht der Grund in einem Satz in `detail` (Befund 7).
      setFormFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Der Kalender konnte nicht gespeichert werden. Bitte die Adresse und, falls verlangt, Benutzername und Passwort prüfen.");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(kind: "mail" | "calendar", id: string) {
    if (!removing || removing.kind !== kind || removing.id !== id) {
      setRemoving({ kind, id });
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      setOverview(await api.removeIntegration(kind, id));
      setRemoving(null);
    } catch {
      setError("Der Zugang konnte nicht getrennt werden. Bitte erneut versuchen.");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedProvider = providers.find((item) => item.id === mail.provider);
  const accounts = overview?.mail_accounts ?? [];
  const calendars = overview?.calendar_sources ?? [];
  // Genau ein gefüllter Knopf: Ist die Einrichtung offen, ist es „Einrichtung fortsetzen“; sonst der erste fehlende Zugang.
  const gefuellt = gefuellterZugang(einrichtungOffen, overview ? accounts.length : null, overview ? calendars.length : null);
  const knopf = (art: "mail" | "calendar") => `source-add source-add-text${gefuellt === art ? "" : " source-add-leise"}`;

  return <>
    <div className="source-section" aria-label={ZUGAENGE.postfaecher.titel}>
      <div className="source-section-heading"><InterfaceIcon name="mail" /><div><h2>{ZUGAENGE.postfaecher.titel}</h2><span>{zaehlen(accounts.length, "Postfach", "Postfächer") || "Mehrere sind möglich"}</span></div><button className={knopf("mail")} onClick={() => { setOpenForm("mail"); setFormFehler(""); setMail({ ...EMPTY_MAIL_FORM, user: adresseLesen() }); }} type="button"><img src={icon("plus", "Outline")} alt="" />Postfach hinzufügen</button></div>
      {!overview ? <div className="source-loading"><i /><i /></div> : null}
      {overview && accounts.length === 0 ? <p className="source-empty">{ZUGAENGE.postfaecher.leer}</p> : null}
      {accounts.map((account) => <Fragment key={account.id}>
        <SourceRow iconName="mail" label={account.label} detail={account.user} state={sourceState(account)} removing={removing?.kind === "mail" && removing.id === account.id} busy={submitting} onRemove={() => remove("mail", account.id)} onCancel={() => setRemoving(null)} />
        {/* Dauerhaft im DOM, damit Bildschirmleser die Bestätigung sicher ansagen; leer, solange nichts zu sagen ist. */}
        <p className="source-hint neu-anmelden-status" role="status" tabIndex={-1} ref={zeile => { statusZeilen.current[account.id] = zeile; }}>{angemeldet[account.id] ?? ""}</p>
        {!angemeldet[account.id] && neuAnmeldenWeg(account, staende[account.id]) ? <div className="neu-anmelden-stand">
            <p className="source-hint">{staende[account.id].satz}</p>
            {neuAnmeldenWeg(account, staende[account.id]) === "passwort"
              ? <NeuAnmelden konto={account} beiErfolg={(neu) => { setOverview(neu); setAngemeldet(vorher => ({ ...vorher, [account.id]: angemeldetSatz(account.label, neu.satz) })); setFokusAuf(account.id); }} />
              : <p className="source-hint">{googleNeuSatz(googleVorne)}</p>}
          </div> : null}
      </Fragment>)}
    </div>
    {/* Wie im Assistenten (Fremdprobe 2, Befund 2): vorne Adresse und Passwort, den Server findet Kingfisher selbst;
        die Servereinstellungen stehen eingeklappt für Techniker. */}
    {openForm === "mail" ? <div className="source-form postfach-hinzufuegen" aria-label="Postfach hinzufügen">
      <h2>Postfach hinzufügen</h2>
      <PostfachMitAdresse anbieter={providers} idPraefix="zugang-postfach" beiVerbunden={() => { setOpenForm(null); load(); }} />
      <details className="kalender-techniker">
        <summary>Für Techniker: Servereinstellungen von Hand</summary>
        <MailSourceForm form={mail} provider={selectedProvider} providers={providers} submitting={submitting} fehler={formFehler} onCancel={() => setOpenForm(null)} onChange={setMail} onProviderChange={chooseProvider} onSubmit={addMail} />
      </details>
      <div className="source-form-actions"><button className="secondary-action" onClick={() => setOpenForm(null)} type="button">Schließen</button></div>
    </div> : null}

    <div className="source-section" aria-label={ZUGAENGE.kalender.titel}>
      <div className="source-section-heading"><InterfaceIcon name="calendar-days" /><div><h2>{ZUGAENGE.kalender.titel}</h2><span>{zaehlen(calendars.length, "Kalender", "Kalender") || (system.mac_helfer ? "Google, Mac oder ein Kalender-Abo" : "Google oder ein Kalender-Abo")}</span></div><button className={knopf("calendar")} onClick={() => { setOpenForm("calendar"); setFormFehler(""); setCalendar(EMPTY_CALENDAR_FORM); }} type="button"><img src={icon("plus", "Outline")} alt="" />Kalender hinzufügen</button></div>
      {!overview ? <div className="source-loading"><i /><i /></div> : null}
      {overview && calendars.length === 0 ? <p className="source-empty">{ZUGAENGE.kalender.leer}</p> : null}
      {calendars.map((source) => <SourceRow key={source.id} iconName="calendar-days" label={source.label} detail={source.kind === "ical" ? "Kalender-Abo" : source.kind === "google" ? "Google · nur lesen" : source.kind === "microsoft" ? "Microsoft · nur lesen" : "Mit Benutzername und Passwort"} state={sourceState(source)} removing={removing?.kind === "calendar" && removing.id === source.id} busy={submitting} onRemove={() => remove("calendar", source.id)} onCancel={() => setRemoving(null)} />)}
    </div>
    {/* Kalender wie Mail (Befund 7): vorne die Mailadresse; das Abo mit eigener Adresse steht eingeklappt für Techniker. */}
    {openForm === "calendar" ? <div className="source-form kalender-hinzufuegen" aria-label="Kalender hinzufügen">
      <h2>Kalender hinzufügen</h2>
      <KalenderMitAdresse anbieter={providers} postfaecher={accounts} beiVerbunden={setOverview} />
      <details className="kalender-techniker">
        <summary>Für Techniker: ein Kalender-Abo oder eine eigene Adresse</summary>
        <CalendarSourceForm form={calendar} submitting={submitting} fehler={formFehler} onCancel={() => setOpenForm(null)} onChange={setCalendar} onSubmit={addCalendar} />
      </details>
      <div className="source-form-actions"><button className="secondary-action" onClick={() => setOpenForm(null)} type="button">Schließen</button></div>
    </div> : null}
    {system.mac_helfer ? <MacCalendarSettings /> : null}
    {googleVorne ? <GoogleSignIn compact active={aktiv} kind="mail" onConnected={() => { load(); standLaden(); }} /> : null}
    {googleVorne ? <GoogleSignIn compact active={aktiv} kind="calendar" onConnected={load} /> : null}
    <MicrosoftZugang aktiv={aktiv} beiAenderung={load} />

    <header className="zugang-kopf"><h2>{ZUGAENGE.ordner.titel}</h2><p>{ZUGAENGE.ordner.satz}</p></header>
    <TranscriptSettings compact />
    <FolderSyncSettings />
    <DocumentImport />
  </>;
}
