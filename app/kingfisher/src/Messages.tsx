import { useEffect, useRef, useState } from "react";
import { api, type InboxMessage, type MailAccount } from "./api";
import { Sidebar } from "./chrome";
import { MailReader } from "./MailReader";
import { aktualisiertSatz } from "./heute";
import "./Messages.css";

type Tab = "inbox" | "unread" | "newsletter" | "spam" | "all";
const tabs: Array<{ id: Tab; label: string }> = [
  { id: "inbox", label: "Posteingang" }, { id: "unread", label: "Ungelesen" },
  { id: "newsletter", label: "Newsletter" }, { id: "spam", label: "Spamverdacht" }, { id: "all", label: "Alle" },
];
const reasons: Record<string, string> = {
  content_incomplete: "Mailinhalt für die automatische KI-Prüfung zu lang oder unvollständig",
  spam_header: "Spam-Markierung im Mailkopf", newsletter: "Newsletter erkannt", blocked: "Absender blockiert",
  ai_spam: "Lokale KI erkennt möglichen Spam", ai_newsletter: "Lokale KI erkennt einen Newsletter",
  ai_unclear: "Lokale KI konnte die Mail nicht sicher sortieren", ai_unavailable: "Lokale KI war nicht verfügbar",
};
function categoryLabel(category: InboxMessage["category"]) {
  return category === "newsletter" ? "Newsletter" : category === "spam" || category === "blocked" ? "Spamverdacht" : category === "unclear" ? "Zur Prüfung" : "Posteingang";
}
function matches(message: InboxMessage, tab: Tab) {
  if (tab === "all") return true;
  if (tab === "unread") return message.unread;
  if (tab === "newsletter") return message.category === "newsletter";
  if (tab === "spam") return message.category === "spam" || message.category === "blocked";
  return message.category !== "newsletter" && message.category !== "spam" && message.category !== "blocked";
}

export function Messages({ recentConversation }: { recentConversation: string | null }) {
  const [selectedUid, setSelectedUid] = useState<string | null>(null);
  const [messages, setMessages] = useState<InboxMessage[] | null>(null);
  const [accounts, setAccounts] = useState<MailAccount[]>([]);
  const [accountId, setAccountId] = useState("");
  const [tab, setTab] = useState<Tab>("inbox");
  const [failure, setFailure] = useState("");
  // Wohin der Nutzer gehen kann, wenn das Postfach selbst nicht antwortet (Einstellungen → Zugänge, Befund 14).
  const [failureZiel, setFailureZiel] = useState("");
  const [notice, setNotice] = useState("");
  const [abgerufen, setAbgerufen] = useState("");
  const [busy, setBusy] = useState(false);
  const requestVersion = useRef(0);
  async function loadAccounts() {
    try { const overview = await api.integrations(); setAccounts(overview.mail_accounts); } catch { /* Messages load reports the useful failure. */ }
  }
  async function load(aktualisieren = false) {
    const version = ++requestVersion.current;
    // Nach „Aktualisieren“ ein Satz, was dabei herauskam (Fremdprobe 2, Befund 18); beim ersten Laden keiner.
    const vorher = aktualisieren ? (messages ?? []).map(message => `${message.account_id}:${message.id}`) : null;
    setBusy(true); setFailure(""); setFailureZiel(""); setNotice(""); setAbgerufen(""); setMessages(null);
    try {
      const payload = await api.messages(accountId || undefined);
      if (version !== requestVersion.current) return;
      setMessages(payload.messages);
      const uhrzeit = payload.abgerufen_um ?? new Date().toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
      if (!payload.partial_failure) setAbgerufen(aktualisiertSatz(vorher, payload.messages.map(message => `${message.account_id}:${message.id}`), uhrzeit) ?? "");
      if (payload.partial_failure?.code === "unavailable") { setFailure(payload.partial_failure.message); setFailureZiel(payload.partial_failure.ziel ?? ""); }
      if (payload.partial_failure?.code === "not_configured") setNotice(payload.partial_failure.message);
    } catch { if (version === requestVersion.current) setFailure("Kingfisher selbst antwortet gerade nicht. Bitte gleich noch einmal versuchen."); }
    finally { if (version === requestVersion.current) setBusy(false); }
  }
  useEffect(() => { void loadAccounts(); }, []);
  useEffect(() => { void load(); }, [accountId]);
  const visible = messages?.filter(message => matches(message, tab)) ?? null;
  return <div className="shell inbox-shell">
    <Sidebar active="Nachrichten" recentConversation={recentConversation} />
    <main className="inbox-page">
      <header className="inbox-heading"><h1>Nachrichten</h1><p>Deine Post, mit dem Zusammenhang, der zählt.</p><button className="text-action" type="button" disabled={busy} onClick={() => void load(true)}>{busy ? "Wird abgerufen …" : "Aktualisieren"}</button></header>
      {abgerufen ? <p className="inbox-abgerufen" role="status">{abgerufen}</p> : null}
      <div className="inbox-content">
      <p className="inbox-count">Filter gelten für die bis zu 30 neuesten Mails des gewählten Posteingangs; Spamordner nicht enthalten.</p>
      <div className="inbox-filter" role="group" aria-label="Nachrichtenfilter">
        {tabs.map(item => <button key={item.id} type="button" aria-pressed={tab === item.id} onClick={() => { setSelectedUid(null); setTab(item.id); }}>{item.label}{messages ? ` (${messages.filter(message => matches(message, item.id)).length})` : ""}</button>)}
        <select className="inbox-account" aria-label="Posteingang auswählen" value={accountId} onChange={event => { setSelectedUid(null); setAccountId(event.target.value); }}><option value="">Alle Konten</option>{accounts.map(account => <option key={account.id} value={account.id}>{account.label}</option>)}</select>
      </div>
      {failure ? <p className="inbox-error" role="alert">{failure} {failureZiel ? <a className="text-action" href={failureZiel}>Postfach prüfen →</a> : null} <button onClick={() => void load()} type="button">Wiederholen</button></p> : null}
      <section aria-label="Lokaler Posteingang" className="inbox-list">
        {selectedUid ? <MailReader key={selectedUid} uid={selectedUid} onClose={() => setSelectedUid(null)} /> : <>
          {!messages && !failure ? Array.from({ length: 4 }, (_, index) => <div className="inbox-row inbox-skeleton" key={index}><i /><i /></div>) : null}
          {visible?.map(message => <article className={`inbox-row ${message.unread ? "unread" : ""}`} key={`${message.account_id}:${message.id}`}>
            <span className="inbox-copy"><button className="inbox-open" type="button" onClick={() => setSelectedUid(message.id)}><strong>{message.sender}</strong><small>{message.subject}{message.category !== "inbox" ? <span className="inbox-category">{categoryLabel(message.category)}</span> : null}</small></button>{message.preview ? <p>{message.preview}</p> : null}{message.filter_reason && message.filter_reason !== "not_flagged" ? <small className="inbox-reason">{reasons[message.filter_reason] ?? "Automatische Filterprüfung"}</small> : null}</span>
            <span className="inbox-meta">{message.date ? <time dateTime={message.date}>{new Date(message.date).toLocaleDateString("de-DE")}</time> : null}{message.source ? <small>{message.source}</small> : null}</span>
          </article>)}
          {visible && visible.length === 0 && !failure ? <p className="inbox-empty">{notice || "Keine Nachrichten in dieser Ansicht."}</p> : null}
        </>}
      </section>
      <p><a className="text-action" href="/settings#technik-filter">Automatische Mailfilter in den Einstellungen öffnen</a></p>
      </div>
    </main>
  </div>;
}
