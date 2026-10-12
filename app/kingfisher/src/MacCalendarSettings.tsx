import { useEffect, useState } from "react";
import { api, type MacCalendarState } from "./api";
import { nurAufDemMac } from "./system";
import { useSystem } from "./useSystem";
import { requestMacCalendarPermission } from "./macCalendarBridge";

// Nur auf dem Mac sichtbar (Zugaenge.tsx): Die Mac-Kalender liest ein Helfer der Kingfisher-App.
export function MacCalendarSettings() {
  const system = useSystem();
  const [state, setState] = useState<MacCalendarState | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    async function load() {
      try { const next = await api.macCalendar(); if (active) { setState(next); if (!dirty) setSelected(next.selected); } }
      catch { if (active) setError("Mac-Kalenderstatus konnte nicht geladen werden."); }
    }
    void load(); const timer = window.setInterval(load, 5000);
    return () => { active = false; window.clearInterval(timer); };
  }, [dirty]);
  async function run(action: () => Promise<MacCalendarState>) {
    setBusy(true); setError("");
    try { const next = await action(); setState(next); setSelected(next.selected); setDirty(false); }
    catch (e) { setError(e instanceof Error ? e.message : "Verbindung fehlgeschlagen."); }
    finally { setBusy(false); }
  }
  async function connect() {
    await run(async () => {
      const next = await api.connectMacCalendar();
      if (!requestMacCalendarPermission(next)) {
        throw new Error("Die Kalenderfreigabe ist im Kingfisher-App-Fenster verfügbar. Öffne die App und wähle dort „Freigabe öffnen“.");
      }
      return next;
    });
  }
  return <section className="source-section mac-calendar" aria-label="Kalender auf diesem Mac">
    <h2>Kalender auf diesem Mac</h2>
    <p>Termine aus deinen ausgewählten Mac-Kalendern.</p>
    {!state ? <p>Status wird geladen …</p> : <>
      {!state.online && <p role="status">{nurAufDemMac(system, "Das Lesen der Mac-Kalender")}</p>}
      {!state.enabled ? <button disabled={busy || !state.online} onClick={() => void connect()}>Mac-Kalender verbinden</button> : <>
        {state.authorize && <p role="status">Kalenderfreigabe steht aus. Bestätige den macOS-Dialog, falls er geöffnet ist. <button disabled={busy || !state.online} onClick={() => void connect()}>Freigabe öffnen</button></p>}
        {!state.authorize && state.status !== "granted" && <p>Kalenderzugriff fehlt. <button disabled={busy || !state.online} onClick={() => void connect()}>Freigabe erneut anfragen</button></p>}
        {state.status === "granted" && <details className="calendar-selection" open={dirty || undefined}>
          <summary>Kalender auswählen ({state.selected.length})</summary><fieldset disabled={busy}>
          <legend>Diese Kalender lesen</legend>
          {state.calendars.length === 0 && <p>Keine Kalender verfügbar.</p>}
          {state.calendars.map(c => <label key={c.id}><input type="checkbox" checked={selected.includes(c.id)} onChange={e => { setDirty(true); setSelected(e.target.checked ? [...selected, c.id] : selected.filter(id => id !== c.id)); }} /><span>{c.name}<small>{c.source}</small></span></label>)}
          <button disabled={!state.online} onClick={() => void run(() => api.selectMacCalendars(selected))}>Auswahl speichern und synchronisieren</button>
        </fieldset></details>}
        {state.synced_at && <p role="status">{state.event_count} Termine · Stand {new Date(state.synced_at).toLocaleString("de-DE")}</p>}
        {!state.synced_at && state.selected.length > 0 && <p role="status">Synchronisation ausstehend …</p>}

      </>}
    </>}
    <details className="calendar-permissions"><summary>Zugriff und Datenschutz</summary><p className="source-empty">Kingfisher liest Titel, Zeiten, Ort und genannte Teilnehmer aus den ausgewählten Kalendern. Für das Gedächtnis werden auch Terminnotizen aus den letzten drei Jahren und dem kommenden Jahr gelesen; dieser Abgleich wartet bei pausierter Hintergrundverarbeitung. macOS nennt die Leseberechtigung „Vollzugriff“. Dieser Adapter verändert keine Termine. Der Systemzugriff lässt sich unter Datenschutz &amp; Sicherheit → Kalender entziehen.</p>{state?.enabled && <button disabled={busy} onClick={() => void run(api.disconnectMacCalendar)}>Trennen und lokale Terminkopie löschen</button>}</details>
    {(error || state?.error) && <p role="alert" className="settings-error">{error || state?.error}</p>}
    {state?.memory_error && <p role="status" className="settings-error">{state.memory_error}</p>}
  </section>;
}
