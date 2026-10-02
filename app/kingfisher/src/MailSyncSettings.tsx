import "./MailSyncSettings.css";
import { useEffect, useRef, useState } from "react";
import { api, type MailAccount, type Schedule } from "./api";
import { MailIntake } from "./MailIntake";
import { VORGABE_MINUTEN, abrufSatz, abstandAuswahl } from "./mailAbruf";
import { kostenSatz, laufZeile } from "./technik";

// Für Techniker → Zeitplan und Hintergrund: „Mails regelmäßig abrufen“. Ein Schalter, eine Auswahl, wie oft, und, bei
// mehreren Postfächern, welche. Jede Änderung gilt sofort und lässt sich mit einem Klick zurücknehmen, deshalb ohne
// „Speichern“. Die Technik dahinter ist der gemeinsame Zeitplan (`PUT /api/v1/schedule`); die Wörter sind neu
// (Fremdprobe, Befund 12, mailAbruf.ts).
export function MailSyncSettings({ accounts }: { accounts: MailAccount[] }) {
  const [saved, setSaved] = useState<Schedule | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(false);
  const [notice, setNotice] = useState("");
  const [revision, setRevision] = useState(0);
  const [einlesenOffen, setEinlesenOffen] = useState(false);
  const requestVersion = useRef(0);
  const waehlbar = accounts.filter(account => account.configured && account.secret_present);

  useEffect(() => {
    let active = true;
    const version = ++requestVersion.current;
    api.schedule().then(value => {
      if (!active || version !== requestVersion.current) return;
      setSaved(value); setError(false);
    }).catch(() => { if (active && version === requestVersion.current) setError(true); });
    return () => { active = false; };
  }, [revision]);

  const gewaehlt = saved?.mail_accounts.filter(id => waehlbar.some(account => account.id === id)) ?? [];
  const an = Boolean(saved?.enabled && gewaehlt.length);
  const minuten = saved?.interval_minutes ?? VORGABE_MINUTEN;

  async function speichern(neu: { an?: boolean; minuten?: number; konten?: string[] }) {
    if (!saved) return;
    requestVersion.current++;
    setBusy(true); setError(false); setNotice("");
    const einschalten = neu.an ?? an;
    // Beim Einschalten ohne Auswahl gelten alle verbundenen Postfächer: niemand muss sie einzeln ankreuzen.
    const konten = neu.konten ?? (gewaehlt.length ? gewaehlt : waehlbar.map(account => account.id));
    try {
      const ergebnis = await api.saveSchedule({ enabled: einschalten && konten.length > 0, interval_minutes: neu.minuten ?? minuten, mail_accounts: konten });
      setSaved(ergebnis);
      const namen = waehlbar.filter(account => ergebnis.mail_accounts.includes(account.id)).map(account => account.label);
      setNotice(`Gespeichert. ${abrufSatz(ergebnis.enabled && namen.length > 0, ergebnis.interval_minutes, namen)}`);
    } catch { setError(true); }
    finally { setBusy(false); }
  }

  function kontoStand(account: MailAccount) {
    // Die eine Aussage des Sidecars über das Postfach, dieselbe wie auf Heute (Fremdprobe 2, Befund 17).
    const stand = saved?.mail_stand?.find(eintrag => eintrag.account_id === account.id);
    if (stand) return stand.satz;
    const status = saved?.mail_status?.[account.id];
    if (!status) return "noch nicht abgerufen";
    const fehler = status.last_failure === "credentials_missing" ? "Zugangsdaten fehlen"
      : status.last_failure === "cancelled" ? "abgebrochen"
      : status.last_failure === "unavailable" ? "zuletzt nicht erreichbar, wird erneut versucht" : "";
    const zuletzt = status.last_success ? `zuletzt abgerufen ${new Date(status.last_success).toLocaleString("de-DE")}` : "noch nie erfolgreich abgerufen";
    return fehler ? `${fehler} · ${zuletzt}` : zuletzt;
  }

  const namen = waehlbar.filter(account => gewaehlt.includes(account.id)).map(account => account.label);
  return <section className="source-section mail-sync-settings" aria-label="Mails regelmäßig abrufen">
    {!saved && !error ? <p role="status">Wird geladen …</p> : null}
    {saved ? <>
      <label className="mail-abruf-schalter">
        <input type="checkbox" role="switch" checked={an} disabled={busy || !waehlbar.length} onChange={event => void speichern({ an: event.target.checked })} />
        <span><strong>Mails regelmäßig abrufen</strong><small>{abrufSatz(an, minuten, namen.length ? namen : waehlbar.map(account => account.label))}</small></span>
      </label>
      {an ? <label className="mail-abruf-wie-oft">Wie oft
        <select value={minuten} disabled={busy} onChange={event => void speichern({ minuten: Number(event.target.value) })}>
          {abstandAuswahl(minuten).map(eintrag => <option key={eintrag.minuten} value={eintrag.minuten}>{eintrag.text}</option>)}
        </select>
      </label> : null}
      {an && waehlbar.length > 1 ? <fieldset className="mail-abruf-konten" disabled={busy}>
        <legend>Diese Postfächer</legend>
        {waehlbar.map(account => <label key={account.id}><input type="checkbox" checked={gewaehlt.includes(account.id)}
          onChange={event => void speichern({ konten: event.target.checked ? [...gewaehlt, account.id] : gewaehlt.filter(id => id !== account.id) })} />{account.label}</label>)}
      </fieldset> : null}
      <details className="mail-abruf-verlauf">
        <summary>Was zuletzt lief</summary>
        {accounts.map(account => <p key={account.id}>{account.configured && account.secret_present ? (saved.mail_stand?.some(eintrag => eintrag.account_id === account.id) ? kontoStand(account) : `${account.label}: ${kontoStand(account)}`) : `${account.label}: Zugangsdaten fehlen`}</p>)}
        {saved.last_run ? <>
          <p>Letzter Lauf: {saved.last_run.finished_at ? new Date(saved.last_run.finished_at).toLocaleString("de-DE") : "läuft gerade"}</p>
          {saved.last_run.jobs.map((job, index) => <p key={index}>{laufZeile(job.name.startsWith("mail:") ? accounts.find(account => account.id === job.name.slice(5))?.label ?? "Postfach" : ({ verdichtung: "Wissensvorschläge", zusammenfassung: "Zusammenfassungen", sicherung: "Sicherung" }[job.name] ?? "Weitere Quellen"), job.ok, job.name === "sicherung" && job.ok ? "Erstellt" : job.detail)}</p>)}
        </> : null}
        <p>Bei jedem Abruf sortiert Kingfisher auch, was schon gespeichert ist{Object.keys(saved.sources).length ? `, und liest ${Object.keys(saved.sources).length} freigegebene Ordner` : ""}. {saved.backup ? "Eine Sicherung läuft mit." : ""} {kostenSatz(saved.with_model, saved.kosten_modell)} Abgewählte Postfächer werden nicht weiter abgerufen; was schon gespeichert ist, bleibt.</p>
        <button className="text-action" disabled={busy} type="button" onClick={() => setRevision(value => value + 1)}>Stand neu laden</button>
      </details>
    </> : null}
    {notice ? <p role="status">{notice}</p> : null}
    {error ? <p role="alert">Das konnte nicht geladen oder gespeichert werden. Bitte noch einmal versuchen. <button className="text-action" type="button" onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p> : null}
    <details className="mail-abruf-einlesen" open={einlesenOffen} onToggle={event => setEinlesenOffen(event.currentTarget.open)}>
      <summary>Ältere Mails einlesen</summary>
      <MailIntake accounts={accounts} active={einlesenOffen} onChanged={() => setRevision(value => value + 1)} />
    </details>
  </section>;
}

