import { useCallback, useEffect, useState, type FormEvent } from "react";
import { api, ApiError, type IntegrationOverview, type MailProvider } from "../api";
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
import { ZUGAENGE } from "./gliederung";
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
export function Zugaenge({ integrationen, aktiv }: { integrationen: Integrationen; aktiv: boolean }) {
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

  return <>
    {googleVorne ? <GoogleSignIn active={aktiv} kind="mail" onConnected={load} /> : null}
    <MicrosoftZugang aktiv={aktiv} beiAenderung={load} />
    <div className="source-section" aria-label={ZUGAENGE.postfaecher.titel}>
      <div className="source-section-heading"><InterfaceIcon name="mail" /><div><h2>{ZUGAENGE.postfaecher.titel}</h2><span>{zaehlen(accounts.length, "Postfach", "Postfächer") || "Mehrere sind möglich"}</span></div><button className="source-add source-add-text" onClick={() => { setOpenForm("mail"); setFormFehler(""); setMail({ ...EMPTY_MAIL_FORM, user: adresseLesen() }); }} type="button"><img src={icon("plus", "Outline")} alt="" />Postfach hinzufügen</button></div>
      {!overview ? <div className="source-loading"><i /><i /></div> : null}
      {overview && accounts.length === 0 ? <p className="source-empty">{ZUGAENGE.postfaecher.leer}</p> : null}
      {accounts.map((account) => <SourceRow key={account.id} iconName="mail" label={account.label} detail={account.user} state={sourceState(account)} removing={removing?.kind === "mail" && removing.id === account.id} busy={submitting} onRemove={() => remove("mail", account.id)} onCancel={() => setRemoving(null)} />)}
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

    {googleVorne ? <GoogleSignIn active={aktiv} kind="calendar" onConnected={load} /> : null}
    <div className="source-section" aria-label={ZUGAENGE.kalender.titel}>
      <div className="source-section-heading"><InterfaceIcon name="calendar-days" /><div><h2>{ZUGAENGE.kalender.titel}</h2><span>{zaehlen(calendars.length, "Kalender", "Kalender") || (system.mac_helfer ? "Google, Mac oder ein Kalender-Abo" : "Google oder ein Kalender-Abo")}</span></div><button className="source-add source-add-text" onClick={() => { setOpenForm("calendar"); setFormFehler(""); setCalendar(EMPTY_CALENDAR_FORM); }} type="button"><img src={icon("plus", "Outline")} alt="" />Kalender hinzufügen</button></div>
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

    <header className="zugang-kopf"><h2>{ZUGAENGE.ordner.titel}</h2><p>{ZUGAENGE.ordner.satz}</p></header>
    <TranscriptSettings />
    <FolderSyncSettings />
    <DocumentImport />
  </>;
}
