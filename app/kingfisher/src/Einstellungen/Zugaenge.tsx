import { Fragment, useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Gruppe, zeigeHinweis } from "../grundlage";
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
import { kontenApi } from "../kontenApi";
import {
  alleUebernommenText, bereichText, kalenderNeben, neuerName, offeneVorschlaege, umbenanntText, zurueckZuOhne,
  type Konten, type Konto,
} from "../kontenBereiche";
import { KontoZeile } from "./KontoZeile";
import { kalenderZeilen } from "../zahlen";
import { gefuellterZugang, ZUGAENGE, zugangListe } from "./gliederung";
import { NeuAnmelden } from "./NeuAnmelden";
import { angemeldetSatz, googleNeuSatz, neuAnmeldenWeg } from "./neuAnmeldenWeg";
import {
  CalendarSourceForm, EMPTY_CALENDAR_FORM, EMPTY_MAIL_FORM, MailSourceForm, sourceState,
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
  const { overview, setOverview, providers, error, setError, load } = integrationen;
  const [openForm, setOpenForm] = useState<"mail" | "calendar" | null>(null);
  const [mail, setMail] = useState<MailForm>(EMPTY_MAIL_FORM);
  const [calendar, setCalendar] = useState<CalendarForm>(EMPTY_CALENDAR_FORM);
  const [submitting, setSubmitting] = useState(false);
  // Was beim Speichern abgelehnt wurde, steht am Formular und nicht oben auf der Seite (Fremdprobe 2, Befund 4).
  const [formFehler, setFormFehler] = useState("");
  const [removing, setRemoving] = useState<{ kind: "mail" | "calendar"; id: string } | null>(null);
  // Scheitert das Entfernen, steht der Grund im Dialog, nicht hinter ihm auf der Seite (Paket B, B3).
  const [removeError, setRemoveError] = useState("");
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
  // Name, Bereich und Stand je Konto (Paket K, konten_routes.py): neu gelesen, sobald sich die Zugänge ändern.
  const [konten, setKonten] = useState<Konten | null>(null);
  const kontenLaden = useCallback(() => { kontenApi.konten().then(setKonten).catch(() => { /* Ohne sie bleiben die Zeilen wie bisher. */ }); }, []);
  useEffect(() => { if (aktiv) kontenLaden(); }, [aktiv, overview, kontenLaden]);
  const fehlerSatz = (problem: unknown, sonst: string) => problem instanceof ApiError && problem.detail ? problem.detail : sonst;

  // Umbenennen, Bereich wählen, eigenen Bereich anlegen: ohne Rückfrage, danach der Hinweis mit „Rückgängig“.
  async function umbenennen(konto: Konto, eingabe: string): Promise<string | null> {
    const name = neuerName(eingabe, konto.name);
    if (!name) return eingabe.trim() ? null : "Der Name fehlt.";
    try {
      const antwort = await kontenApi.umbenennen(konto.id, name);
      setKonten(antwort); load();
      zeigeHinweis({ text: umbenanntText(name), rueckgaengig: async () => { setKonten(await kontenApi.umbenennen(konto.id, antwort.vorher)); load(); } });
      return null;
    } catch (problem) { return fehlerSatz(problem, "Der Name konnte nicht gespeichert werden."); }
  }
  async function bereichSetzen(konto: Konto, bereich: string | null) {
    try {
      const antwort = await kontenApi.bereich({ [konto.id]: bereich });
      setKonten(antwort);
      zeigeHinweis({ text: bereichText(antwort, konto.name, bereich), rueckgaengig: async () => setKonten(await kontenApi.bereich(antwort.vorher)) });
    } catch (problem) { zeigeHinweis({ text: fehlerSatz(problem, "Der Bereich konnte nicht gespeichert werden."), fehler: true }); }
  }
  async function neuerBereich(konto: Konto, name: string): Promise<string | null> {
    try { const antwort = await kontenApi.bereichAnlegen(name); setKonten(antwort); await bereichSetzen(konto, antwort.neu); return null; }
    catch (problem) { return fehlerSatz(problem, "Der Bereich konnte nicht angelegt werden."); }
  }
  const offen = offeneVorschlaege(konten);
  const offenAnzahl = Object.keys(offen).length;
  async function alleUebernehmen() {
    try {
      setKonten(await kontenApi.bereich(offen));
      zeigeHinweis({ text: alleUebernommenText(offenAnzahl), rueckgaengig: async () => setKonten(await kontenApi.bereich(zurueckZuOhne(offen))) });
    } catch (problem) { zeigeHinweis({ text: fehlerSatz(problem, "Die Vorschläge konnten nicht übernommen werden."), fehler: true }); }
  }
  const alleKnopf = offenAnzahl > 1 ? <button type="button" className="g-knopf-schlicht konto-alle" disabled={submitting} onClick={() => void alleUebernehmen()}>Alle Vorschläge übernehmen</button> : null;
  const kontoZeile = (konto: Konto, iconName: "mail" | "calendar-days", neben: string, ersatz: string | undefined, entfernen?: { kind: "mail" | "calendar" }, kinder?: ReactNode) =>
    <KontoZeile key={konto.id} konto={konto} konten={konten} iconName={iconName} neben={neben} ersatzStand={ersatz} busy={submitting}
      entfernen={entfernen ? { aktiv: removing?.kind === entfernen.kind && removing.id === konto.id, onRemove: () => remove(entfernen.kind, konto.id), onCancel: () => { setRemoving(null); setRemoveError(""); }, fehler: removeError } : undefined}
      onUmbenennen={name => umbenennen(konto, name)} onBereich={bereich => void bereichSetzen(konto, bereich)} onNeuerBereich={name => neuerBereich(konto, name)}>{kinder}</KontoZeile>;
  // Heißt das Postfach nach seiner Adresse, steht sie nicht noch einmal darunter.
  const nebenDerAdresse = (name: string, adresse: string) => name.trim().toLowerCase() === adresse.trim().toLowerCase() ? "" : adresse;
  const ohneKonto = (id: string, name: string, adresse: string): Konto => ({ id, name, adresse, bereich: null, vorschlag: null, stand: null });

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
      setRemoveError("");
      return;
    }
    setSubmitting(true);
    setError("");
    setRemoveError("");
    try {
      setOverview(await api.removeIntegration(kind, id));
      setRemoving(null);
    } catch {
      setRemoveError("Der Zugang konnte nicht getrennt werden. Bitte erneut versuchen.");
    } finally {
      setSubmitting(false);
    }
  }

  const selectedProvider = providers.find((item) => item.id === mail.provider);
  const accounts = overview?.mail_accounts ?? [];
  const calendars = overview?.calendar_sources ?? [];
  // Was unter „Kalender“ steht, auch die Mac-Kalender; die Zahl darüber ist die Länge dieser Liste (Paket Z1).
  const kalenderListe = kalenderZeilen(overview, konten);
  // Genau ein gefüllter Knopf: Ist die Einrichtung offen, ist es „Einrichtung fortsetzen“; sonst der erste fehlende Zugang.
  const gefuellt = gefuellterZugang(einrichtungOffen, overview ? accounts.length : null, overview ? calendars.length : null);
  const knopf = (art: "mail" | "calendar") => gefuellt === art ? "g-knopf zugang-neu" : "g-knopf-getoent zugang-neu";
  const plus = <InterfaceIcon name="plus" />;
  const lage = zugangListe(overview !== null, error);
  const ohneListe = lage === "laedt" ? <div className="source-loading"><i /><i /></div>
    : lage === "nicht_geladen" ? <p className="source-empty">{ZUGAENGE.nichtGeladen}</p> : null;

  // Wie die Accounts in den Systemeinstellungen am Mac: je Art eine Gruppe mit einer Zeile je Zugang, darunter rechts
  // „hinzufügen“ und links in einem Satz, was Trennen bedeutet.
  return <>
    <Gruppe className="zugang-gruppe" label={ZUGAENGE.postfaecher.titel} titel={ZUGAENGE.postfaecher.titel} flaecheKlasse="zugang-liste"
      zahl={accounts.length && !(alleKnopf && konten?.postfaecher.some(k => offen[k.id])) ? zaehlen(accounts.length, "Postfach", "Postfächer") : null}
      aktion={konten?.postfaecher.some(k => offen[k.id]) ? alleKnopf : null} fussnote={accounts.length ? ZUGAENGE.trennen : ""}
      fussAktion={openForm === "mail" ? null : <button className={knopf("mail")} onClick={() => { setOpenForm("mail"); setFormFehler(""); setMail({ ...EMPTY_MAIL_FORM, user: adresseLesen() }); }} type="button">{plus}Postfach hinzufügen</button>}>
        {ohneListe}
        {overview && accounts.length === 0 ? <p className="source-empty">{ZUGAENGE.postfaecher.leer}</p> : null}
        {accounts.map((account) => <Fragment key={account.id}>
          {kontoZeile(konten?.postfaecher.find(k => k.id === account.id) ?? ohneKonto(account.id, account.label, account.user), "mail",
            nebenDerAdresse(konten?.postfaecher.find(k => k.id === account.id)?.name ?? account.label, konten?.postfaecher.find(k => k.id === account.id)?.adresse || account.user), account.configured ? undefined : sourceState(account), { kind: "mail" })}
          {/* Dauerhaft im DOM, damit Bildschirmleser die Bestätigung sicher ansagen; leer, solange nichts zu sagen ist. */}
          <p className="source-hint neu-anmelden-status" role="status" tabIndex={-1} ref={zeile => { statusZeilen.current[account.id] = zeile; }}>{angemeldet[account.id] ?? ""}</p>
          {!angemeldet[account.id] && neuAnmeldenWeg(account, staende[account.id]) ? <div className="neu-anmelden-stand">
              {/* Den Satz trägt schon die Zeile (Stand je Konto); nur ohne ihn steht er hier. */}
              {konten?.postfaecher.find(k => k.id === account.id)?.stand ? null : <p className="source-hint">{staende[account.id].satz}</p>}
              {neuAnmeldenWeg(account, staende[account.id]) === "passwort"
                ? <NeuAnmelden konto={account} beiErfolg={(neu) => { setOverview(neu); setAngemeldet(vorher => ({ ...vorher, [account.id]: angemeldetSatz(account.label, neu.satz) })); setFokusAuf(account.id); }} />
                : <p className="source-hint">{googleNeuSatz(googleVorne)}</p>}
            </div> : null}
        </Fragment>)}
    </Gruppe>
    {/* Wie im Assistenten (Fremdprobe 2, Befund 2): vorne Adresse und Passwort, den Server findet Kingfisher selbst;
        die Servereinstellungen stehen eingeklappt für Techniker. */}
    {openForm === "mail" ? <div className="source-form postfach-hinzufuegen zugang-formular" aria-label="Postfach hinzufügen">
      <div className="zugang-formular-kopf"><h2>Postfach hinzufügen</h2><button className="g-knopf-schlicht" onClick={() => setOpenForm(null)} type="button">Schließen</button></div>
      <PostfachMitAdresse anbieter={providers} idPraefix="zugang-postfach" beiVerbunden={() => { setOpenForm(null); load(); }}
        zumPostfach={kontoId => { setOpenForm(null); requestAnimationFrame(() => document.querySelector<HTMLElement>(`[data-konto="${CSS.escape(kontoId)}"] .konto-name`)?.focus()); }} />
      <details className="kalender-techniker">
        <summary>Für Techniker: Servereinstellungen von Hand</summary>
        <MailSourceForm form={mail} provider={selectedProvider} providers={providers} submitting={submitting} fehler={formFehler} onCancel={() => setOpenForm(null)} onChange={setMail} onProviderChange={chooseProvider} onSubmit={addMail} />
      </details>
    </div> : null}

    <Gruppe className="zugang-gruppe" label={ZUGAENGE.kalender.titel} titel={ZUGAENGE.kalender.titel} flaecheKlasse="zugang-liste"
      zahl={kalenderListe.length && !(alleKnopf && !konten?.postfaecher.some(k => offen[k.id])) ? zaehlen(kalenderListe.length, "Kalender", "Kalender") : null}
      aktion={alleKnopf && !konten?.postfaecher.some(k => offen[k.id]) ? alleKnopf : null}
      fussnote={calendars.length ? ZUGAENGE.trennen : system.mac_helfer ? "Google, Mac oder ein Kalender-Abo." : "Google oder ein Kalender-Abo."}
      fussAktion={openForm === "calendar" ? null : <button className={knopf("calendar")} onClick={() => { setOpenForm("calendar"); setFormFehler(""); setCalendar(EMPTY_CALENDAR_FORM); }} type="button">{plus}Kalender hinzufügen</button>}>
        {ohneListe}
        {overview && kalenderListe.length === 0 ? <p className="source-empty">{ZUGAENGE.kalender.leer}</p> : null}
        {/* Eingetragene Kalender, dann die Mac-Kalender, die Kingfisher liest: Bereich ja, Name und Trennen am Mac (unten
            „Kalender auf diesem Mac“). */}
        {kalenderListe.map(({ id, quelle: source, konto: gefunden }) => {
          if (!source) return gefunden ? kontoZeile(gefunden, "calendar-days", kalenderNeben(gefunden), undefined) : null;
          const konto = gefunden ?? { ...ohneKonto(id, source.label, ""), art: source.kind };
          return kontoZeile(konto, "calendar-days", kalenderNeben(konto), source.configured ? undefined : sourceState(source), { kind: "calendar" });
        })}
    </Gruppe>
    {/* Kalender wie Mail (Befund 7): vorne die Mailadresse; das Abo mit eigener Adresse steht eingeklappt für Techniker. */}
    {openForm === "calendar" ? <div className="source-form kalender-hinzufuegen zugang-formular" aria-label="Kalender hinzufügen">
      <div className="zugang-formular-kopf"><h2>Kalender hinzufügen</h2><button className="g-knopf-schlicht" onClick={() => setOpenForm(null)} type="button">Schließen</button></div>
      <KalenderMitAdresse anbieter={providers} postfaecher={accounts} beiVerbunden={setOverview} />
      <details className="kalender-techniker">
        <summary>Für Techniker: ein Kalender-Abo oder eine eigene Adresse</summary>
        <CalendarSourceForm form={calendar} submitting={submitting} fehler={formFehler} onCancel={() => setOpenForm(null)} onChange={setCalendar} onSubmit={addCalendar} />
      </details>
    </div> : null}
    {system.mac_helfer ? <MacCalendarSettings /> : null}
    {googleVorne ? <GoogleSignIn compact active={aktiv} kind="mail" onConnected={() => { load(); standLaden(); }} /> : null}
    {googleVorne ? <GoogleSignIn compact active={aktiv} kind="calendar" onConnected={load} /> : null}
    <MicrosoftZugang aktiv={aktiv} beiAenderung={load} />

    {/* Ordner und Dateien: eine Gruppe mit drei Zeilen (Meetings, Dokumentenordner, Dateien), der Satz darunter. */}
    <Gruppe className="zugang-gruppe zugang-ordner" label={ZUGAENGE.ordner.titel} titel={ZUGAENGE.ordner.titel} flaecheKlasse="zugang-ordner-liste" fussnote={ZUGAENGE.ordner.satz}>
        <TranscriptSettings compact />
        <FolderSyncSettings />
        <DocumentImport />
    </Gruppe>
  </>;
}
