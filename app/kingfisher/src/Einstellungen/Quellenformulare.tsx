import { useRef, useState, type FormEvent } from "react";
import { useImBlick } from "../useImBlick";
import { type CalendarSource, type MailAccount, type MailProvider } from "../api";
import { icon } from "../ui";
import { ServerFelder } from "./ServerFelder";

export type MailForm = {
  provider: string;
  label: string;
  user: string;
  sender: string;
  password: string;
  imap_host: string;
  imap_port: number;
  smtp_host: string;
  smtp_port: number;
};

export type CalendarForm = {
  label: string;
  kind: "caldav" | "ical";
  url: string;
  user: string;
  password: string;
};

export const EMPTY_MAIL_FORM: MailForm = {
  provider: "manual", label: "", user: "", sender: "", password: "", imap_host: "", imap_port: 993, smtp_host: "", smtp_port: 587,
};

export const EMPTY_CALENDAR_FORM: CalendarForm = {
  label: "", kind: "ical", url: "", user: "", password: "",
};

export function sourceState(source: MailAccount | CalendarSource) {
  if (!source.configured) return "Unvollständig eingerichtet";
  if ("kind" in source && source.kind === "ical") return "Lokales Abo hinterlegt";
  return source.secret_present ? "Zugang lokal hinterlegt" : "Ohne Zugangsdaten";
}


export function SourceRow({ iconName, label, detail, state, removing, busy, onRemove, onCancel }: {
  iconName: "mail" | "calendar-days";
  label: string;
  detail: string;
  state: string;
  removing: boolean;
  busy: boolean;
  onRemove: () => void;
  onCancel: () => void;
}) {
  return <div className="source-row">
    <img src={icon(iconName, "Outline")} alt="" />
    <span><strong>{label}</strong><small>{detail}</small></span>
    {removing ? <span className="source-remove-confirm">Quelle wirklich entfernen?<button disabled={busy} onClick={onRemove} type="button">Entfernen</button><button disabled={busy} onClick={onCancel} type="button">Abbrechen</button></span> : <><em>{state}</em><button aria-label={`${label} entfernen`} className="source-remove" disabled={busy} onClick={onRemove} type="button"><img src={icon("trash2", "Outline")} alt="" /></button></>}
  </div>;
}

/** Die Ablehnung steht am Knopf, nicht oben auf der Seite; die Seite rollt hin (Fremdprobe 2, Befund 4). */
function FehlerAmKnopf({ text }: { text: string }) {
  const ref = useImBlick<HTMLParagraphElement>(text);
  return text ? <p ref={ref} tabIndex={-1} role="alert" className="settings-error am-knopf">{text}</p> : null;
}

export function MailSourceForm({ form, provider, providers, submitting, fehler = "", onCancel, onChange, onProviderChange, onSubmit }: {
  form: MailForm;
  fehler?: string;
  provider: MailProvider | undefined;
  providers: MailProvider[];
  submitting: boolean;
  onCancel: () => void;
  onChange: (form: MailForm) => void;
  onProviderChange: (provider: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const [technicalOpen, setTechnicalOpen] = useState(form.provider === "manual");
  const technical = useRef<HTMLDetailsElement>(null);
  return <form className="source-form" onSubmit={onSubmit} onInvalidCapture={(event) => {
    if (technical.current?.contains(event.target as Node)) {
      technical.current.open = true;
      setTechnicalOpen(true);
    }
  }}>
    <h2>Servereinstellungen</h2>
    <label>Anbieter<select onChange={(event) => { onProviderChange(event.target.value); setTechnicalOpen(event.target.value === "manual"); }} value={form.provider}><option value="manual">Anderer Anbieter</option>{providers.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>
    <label>Name<input onChange={(event) => onChange({ ...form, label: event.target.value })} placeholder="z. B. Arbeit" required value={form.label} /></label>
    <label>E-Mail-Adresse<input onChange={(event) => onChange({ ...form, user: event.target.value })} required type="email" value={form.user} /></label>
    <details className="mail-technical-settings" ref={technical} open={technicalOpen} onToggle={event => setTechnicalOpen(event.currentTarget.open)}>
      <summary>Nur wenn dein Anbieter nicht dabei ist: Servereinstellungen</summary>
      <p className="source-hint">{provider ? "Die Werte deines Anbieters sind bereits eingetragen." : "Die Angaben stehen auf der Hilfeseite deines Mailanbieters."}</p>
      <ServerFelder form={form} onChange={onChange} />
    </details>
    <label>{provider?.app_password ? "App-Passwort" : "Postfachpasswort"}<input autoComplete="new-password" onChange={(event) => onChange({ ...form, password: event.target.value })} type="password" value={form.password} /></label>
    {provider?.hint ? <p className="source-hint">{provider.hint}{provider.help_url ? <> <a href={provider.help_url} rel="noreferrer" target="_blank">{provider.help_label || "Mehr erfahren"}</a></> : null}</p> : null}
    <p className="source-hint">Das Passwort wird nur im lokalen Schlüsselbund abgelegt und nicht erneut angezeigt.</p>
    <div className="source-form-actions"><button className="secondary-action" disabled={submitting} onClick={onCancel} type="button">Abbrechen</button><button className="primary-action" disabled={submitting} type="submit">Lokal speichern</button></div>
    <FehlerAmKnopf text={fehler} />
  </form>;
}

export function CalendarSourceForm({ form, submitting, fehler = "", onCancel, onChange, onSubmit }: {
  form: CalendarForm;
  fehler?: string;
  submitting: boolean;
  onCancel: () => void;
  onChange: (form: CalendarForm) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form className="source-form" onSubmit={onSubmit}>
    <h2>Kalender hinzufügen</h2>
    <label>Name<input onChange={(event) => onChange({ ...form, label: event.target.value })} placeholder="z. B. Privat" required value={form.label} /></label>
    <label>Wie willst du ihn verbinden?<select onChange={(event) => onChange({ ...form, kind: event.target.value as CalendarForm["kind"] })} value={form.kind}><option value="ical">Mit einer Adresse (Kalender-Abo, nur lesen)</option><option value="caldav">Mit Benutzername und Passwort</option></select></label>
    <label>{form.kind === "ical" ? "Adresse des Kalender-Abos" : "Adresse des Kalenders"}<input onChange={(event) => onChange({ ...form, url: event.target.value })} placeholder="https://…" required type="url" value={form.url} /></label>
    {form.kind === "caldav" ? <><label>Benutzername<input onChange={(event) => onChange({ ...form, user: event.target.value })} required value={form.user} /></label><label>App-Passwort<input autoComplete="new-password" onChange={(event) => onChange({ ...form, password: event.target.value })} type="password" value={form.password} /></label></> : <p className="source-hint">Für Google-Kalender kannst du die persönliche HTTPS-iCalendar-Adresse jedes einzelnen Kalenders abonnieren.</p>}
    <p className="source-hint">Der Zugang bleibt lokal. Ein Abo wird nicht an weitere Dienste weitergegeben.</p>
    <div className="source-form-actions"><button className="secondary-action" disabled={submitting} onClick={onCancel} type="button">Abbrechen</button><button className="primary-action" disabled={submitting} type="submit">Lokal speichern</button></div>
    <FehlerAmKnopf text={fehler} />
  </form>;
}

