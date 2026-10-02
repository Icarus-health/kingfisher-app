import { useEffect, useState } from "react";
import { api, type IntegrationOverview, type MacCalendarState, type ModelSetup, type RecoveryStatus, type Schedule, type MemoryAutomation } from "./api";
import { nurAufDemMac } from "./system";
import { useSystem } from "./useSystem";
import "./SetupOverview.css";
import { dokumenteSatz } from "./technik";

type Snapshot = {
  schedule: Schedule | null;
  memory: MemoryAutomation | null;
  model: ModelSetup | null;
  calendar: MacCalendarState | null;
  recovery: RecoveryStatus | null;
  documents: { items: Array<{ state: string }>; next_offset: number | null } | null;
};
const EMPTY: Snapshot = { schedule: null, memory: null, model: null, calendar: null, recovery: null, documents: null };
const unavailable = "Status gerade nicht erreichbar";

export function SetupOverview({ overview, active, onSelect, onRefresh }: {
  overview: IntegrationOverview | null; active: boolean; onSelect: (id: string) => void; onRefresh: () => void;
}) {
  const system = useSystem();
  const [snapshot, setSnapshot] = useState<Snapshot>(EMPTY);
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!active) return;
    let current = true;
    setLoading(true);
    // These reads do not connect accounts, run imports, test models or grant permissions.
    Promise.allSettled([api.schedule(), api.modelSetup(), api.macCalendar(), api.recoveryStatus(), api.uploadedDocuments(), api.memoryAutomation()]).then(results => {
      if (!current) return;
      const [schedule, model, calendar, recovery, documents, memory] = results;
      setSnapshot({
        memory: memory.status === "fulfilled" ? memory.value : null,
        schedule: schedule.status === "fulfilled" ? schedule.value : null,
        model: model.status === "fulfilled" ? model.value : null,
        calendar: calendar.status === "fulfilled" ? calendar.value : null,
        recovery: recovery.status === "fulfilled" ? recovery.value : null,
        documents: documents.status === "fulfilled" ? documents.value : null,
      });
      setLoading(false);
    });
    return () => { current = false; };
  }, [active, revision]);

  const accounts = overview?.mail_accounts ?? [];
  const calendars = overview?.calendar_sources ?? [];
  const { schedule, model, calendar, recovery, documents, memory } = snapshot;
  const mailReady = accounts.filter(account => account.configured && account.secret_present);
  const syncedMail = accounts.filter(account => schedule?.mail_status?.[account.id]?.last_success);
  const scheduledMail = mailReady.filter(account => account.enabled && schedule?.mail_accounts.includes(account.id));
  const failedMail = accounts.filter(account => schedule?.mail_status?.[account.id]?.last_failure);
  const pending = loading ? "Status wird geladen …" : unavailable;
  const sicherungImZeitplan = Boolean(schedule?.last_run?.jobs.some(job => job.name === "sicherung" && job.ok));
  const cards = [
    { id: "mail", label: "Mail", status: !overview ? unavailable : !accounts.length ? "Noch kein Konto eingerichtet" : `${mailReady.length} von ${accounts.length} Konten mit Zugangsdaten`,
      detail: loading ? "Abrufstatus wird geladen …" : !schedule ? unavailable : schedule.mail_stand?.length ? schedule.mail_stand.map(eintrag => eintrag.satz).join(" ") : failedMail.length ? `${failedMail.length} Konten mit Abruffehler. Bitte den Laufstatus prüfen.` : syncedMail.length ? `${syncedMail.length} Konten bereits erfolgreich abgerufen. ${schedule.enabled && scheduledMail.length ? "Mails werden regelmäßig abgerufen." : "Mails werden nicht regelmäßig abgerufen."}` : "Noch kein erfolgreicher automatischer Abruf bestätigt.", action: accounts.length ? "Konten und Aufnahme prüfen" : "Mail einrichten" },
    { id: "calendar", label: "Kalender", status: loading ? "Status wird geladen …" : calendar?.enabled ? calendar.online && calendar.status === "granted" ? `${calendar.selected.length} Mac-Kalender freigegeben` : "Mac-Kalenderzugriff prüfen" : calendars.length ? `${calendars.length} Kalenderzugänge hinterlegt` : !overview || !calendar ? unavailable : "Noch kein Kalender eingerichtet",
      detail: loading ? "Kalenderstatus wird geladen …" : calendar?.error ? "Der Mac-Kalender meldet einen Fehler. Bitte den Status prüfen." : calendar?.enabled && !calendar.online ? nurAufDemMac(system, "Das Lesen der Mac-Kalender") : calendar?.enabled && calendar.synced_at ? `Mac-Kalender zuletzt synchronisiert: ${new Date(calendar.synced_at).toLocaleString("de-DE")}` : "Hinterlegte Abos und Zugangsdaten bestätigen noch keinen erfolgreichen Abruf.", action: "Kalender einrichten" },
    // Eine Aussage aus einer Quelle (lokale_ki.py); früher „Anderer Anbieter eingerichtet“ neben „Alles eingerichtet“ (Befund 9).
    { id: "model", label: "Lokale KI", status: loading ? "Status wird geladen …" : !model?.status.lokale_ki ? unavailable : model.status.lokale_ki.kurz,
      detail: model?.status.lokale_ki?.satz ?? "Der Stand der lokalen KI ist gerade nicht erreichbar.", action: model?.status.lokale_ki?.zustand === "bereit" ? "Lokale KI ansehen" : "Lokale KI einrichten" },
    { id: "documents", label: "Dokumente", status: loading ? "Status wird geladen …" : !documents ? unavailable : dokumenteSatz(documents.items.length, documents.next_offset !== null),
      detail: "Dateien einzeln importieren oder den Status deines freigegebenen Ordners prüfen.", action: "Dokumente aufnehmen" },
    { id: "automation", label: "Automatik", status: loading ? "Status wird geladen …" : memory ? memory.state === "active" ? "Automatisches Sortieren ist an" : memory.state === "legacy_active" ? "Bisherige Automatik aktiv; lokale Ausführung nicht abgesichert" : memory.requested && (memory.state === "model_missing" || memory.state === "local_model_unavailable") ? "Automatisches Sortieren beginnt, sobald das Sprachmodell bereit ist" : memory.requested ? "Das Sortieren braucht deine Aufmerksamkeit" : "Automatisches Sortieren ist pausiert" : pending,
      detail: schedule ? `Mails regelmäßig abrufen: ${schedule.enabled ? "an" : "aus"}. Was schon gespeichert ist, wird davon getrennt sortiert.` : "Ob Mails regelmäßig abgerufen werden, ist gerade nicht zu sehen.", action: "Automatik prüfen" },
    { id: "profile", label: "Arbeitsvorlieben", status: "Nach deinen Wünschen", detail: "Antwortstil und Arbeitsweise anpassen.", action: "Vorlieben bearbeiten" },
    { id: "recovery", label: "Sicherung", status: loading ? "Status wird geladen …" : !recovery ? unavailable : recovery.job?.status === "completed" ? "Letzte Sicherung erstellt und geprüft" : recovery.job?.status === "failed" ? "Letzte Sicherung fehlgeschlagen" : recovery.job?.status === "queued" || recovery.job?.status === "running" ? "Sicherung läuft" : sicherungImZeitplan ? "Zuletzt mit dem Zeitplan erstellt" : "Noch keine vollständige Sicherung bestätigt",
      // Ohne Helfer geht die Sicherung als Datei zum Herunterladen; kein „Helfer nicht erreichbar“ neben „Erstellt“ (Befund 27).
      detail: "Daten und Schlüssel mit einem eigenen Passwort sichern; die Sicherung lädst du als Datei herunter.", action: "Sicherung öffnen" },
    { id: "advanced", label: "Erweitert", status: "Bei Bedarf", detail: "Fortgeschrittene Modellwahl und weitere Quellen verwalten.", action: "Erweiterte Einstellungen" },
  ];
  return <div className="setup-overview">
    <p className="source-hint">„Eingerichtet“ bedeutet lokal gespeichert. Erfolgreiche Abrufe und Sicherungen werden nur angezeigt, wenn ein entsprechender Lauf vorliegt. Du entscheidest über jede Freigabe.</p>
    <div className="setup-overview-actions"><button type="button" className="secondary-action" disabled={loading} onClick={() => { onRefresh(); setRevision(value => value + 1); }}>Status aktualisieren</button><span role="status">{loading ? "Status wird geladen …" : "Stand der zuletzt gelesenen Einstellungen"}</span></div>
    <div className="setup-overview-grid">{cards.map(card => <article key={card.id} className="setup-overview-card">
      <h3>{card.label}</h3><strong>{card.status}</strong><p>{card.detail}</p>
      <button className="secondary-action" type="button" onClick={() => onSelect(card.id)}>{card.action}</button>
    </article>)}</div>
  </div>;
}
