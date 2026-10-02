import { type MailForm } from "./Quellenformulare";

// Die technischen Felder eines Postfachs. Sie stehen nur in einem eingeklappten Bereich („Nur wenn dein Anbieter nicht
// dabei ist“); wer seinen Anbieter in der Liste wählt, sieht sie nie. Deshalb gehört diese Datei nicht zu den vorderen
// Dateien, in denen der Wortlistentest nach Fachwörtern sucht (docs/47-einstellungen.md).
export function ServerFelder({ form, onChange }: { form: MailForm; onChange: (form: MailForm) => void }) {
  return <>
      <label>IMAP-Server<input onChange={(event) => onChange({ ...form, imap_host: event.target.value })} required value={form.imap_host} /></label>
      <label>IMAP-Port<input onChange={(event) => onChange({ ...form, imap_port: Number(event.target.value) })} required type="number" min={1} max={65535} value={form.imap_port} /></label>
      <label>SMTP-Server <small>(optional für Versand)</small><input onChange={(event) => onChange({ ...form, smtp_host: event.target.value })} value={form.smtp_host} /></label>
      <label>SMTP-Port<input onChange={(event) => onChange({ ...form, smtp_port: Number(event.target.value) })} required type="number" min={1} max={65535} value={form.smtp_port} /></label>
      <label>Absenderadresse <small>(optional für Versand)</small><input onChange={(event) => onChange({ ...form, sender: event.target.value })} type="email" value={form.sender} /></label>
  </>;
}
