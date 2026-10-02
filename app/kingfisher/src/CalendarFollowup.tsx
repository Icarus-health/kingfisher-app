import { useEffect, useRef, useState, type ChangeEvent } from "react";
import { ApiError, api, type NachbereitungGespeichert, type Project, type TerminNachbereitung } from "./api";
import { displayLabel } from "./displayIdentity";
import { ProfileSource } from "./ProfileSource";

type Props = { uid: string; start: string; onClose: () => void; onChange?: () => void };
type Datei = { name: string; text: string; format: "srt" | "vtt" };

const MAX_BYTES = 512 * 1024;

function wann(start: string | null) {
  if (!start) return "";
  const date = new Date(start);
  return Number.isNaN(date.getTime()) ? "" : new Intl.DateTimeFormat("de-DE", { weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit" }).format(date);
}

// Die Frage der Karte, kurz und mit Namen: „Wie war das Gespräch mit Anna Keller?“
function frage(namen: string[], titel: string | null) {
  if (!namen.length) return titel ? `Wie war „${titel}“?` : "Was ist herausgekommen?";
  const wer = namen.length === 1 ? namen[0] : namen.length === 2 ? `${namen[0]} und ${namen[1]}` : `${namen[0]} und ${namen.length - 1} weiteren`;
  return `Wie war das Gespräch mit ${wer}?`;
}

// Nach dem Termin: Wie war das Gespräch? Getippt, als Mitschrift-Datei oder, wenn ein Meeting
// aufgezeichnet wurde, aus dem Mitschriften-Ordner. Gespeichert wird eine Quelle; Bitten und
// Zusagen daraus werden vorgeschlagen, nie ungefragt übernommen.
export function CalendarFollowup({ uid, start, onClose, onChange }: Props) {
  const [stand, setStand] = useState<TerminNachbereitung | null>(null);
  const [fehler, setFehler] = useState<"" | "weg" | "netz">("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [vorschlag, setVorschlag] = useState<{ name: string; grund?: string } | null>(null);
  const [zugeordnet, setZugeordnet] = useState<{ id: string; name: string } | null>(null);
  const [text, setText] = useState("");
  const [datei, setDatei] = useState<Datei | null>(null);
  const [ergaenzen, setErgaenzen] = useState(false);
  const [sending, setSending] = useState(false);
  const [meldung, setMeldung] = useState("");
  const [sendFehler, setSendFehler] = useState("");
  const [projektFehler, setProjektFehler] = useState(false);
  const dateiFeld = useRef<HTMLInputElement>(null);
  const projektBeruehrt = useRef(false);
  const dateiGeneration = useRef(0);

  useEffect(() => {
    let active = true;
    projektBeruehrt.current = false;
    dateiGeneration.current += 1;
    setStand(null); setFehler(""); setMeldung(""); setSendFehler(""); setErgaenzen(false); setText(""); setDatei(null); setProjektFehler(false);
    api.calendarFollowup(uid, start)
      .then(next => { if (active) setStand(next); })
      .catch(cause => { if (active) setFehler(cause instanceof ApiError && cause.status === 404 ? "weg" : "netz"); });
    api.projects().then(next => { if (active) setProjects(next); }).catch(() => { if (active) setProjects([]); });
    // Das Projekt steht schon fest oder ist vorgeschlagen; niemand soll es neu wählen müssen.
    api.calendarAssignment(uid).then(next => {
      if (!active) return;
      if (!projektBeruehrt.current) setProjectId(next.projekt?.id ?? "");
      setZugeordnet(next.projekt ? { id: next.projekt.id, name: next.projekt.name } : null);
      if (!projektBeruehrt.current) setVorschlag(next.projekt?.herkunft === "vorschlag" ? { name: next.projekt.name, grund: next.projekt.grund } : null);
    }).catch(() => { if (active) setProjektFehler(true); });
    return () => { active = false; };
  }, [uid, start]);

  async function dateiGewaehlt(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const generation = ++dateiGeneration.current;
    setSendFehler("");
    if (file.size > MAX_BYTES) { setSendFehler("Die Datei ist größer als 512 KiB."); return; }
    const endung = file.name.toLowerCase().split(".").pop() ?? "";
    const inhalt = await file.text();
    if (generation !== dateiGeneration.current) return;
    if (endung === "srt" || endung === "vtt") setDatei({ name: file.name, text: inhalt, format: endung });
    else { setDatei(null); setText(value => value.trim() ? `${value.trim()}\n\n${inhalt}` : inhalt); }
  }

  async function festhalten() {
    if (!stand?.start || sending) return;
    dateiGeneration.current += 1;
    setSending(true); setSendFehler(""); setMeldung("");
    try {
      // Mit Mitschrift gehen die eigenen Notizen als Notiz mit.
      const body = datei
        ? { uid, start: stand.start, text: datei.text, format: datei.format, notiz: text, project_id: projectId || null }
        : { uid, start: stand.start, text, format: "text" as const, project_id: projectId || null };
      const result: NachbereitungGespeichert = await api.recordCalendarFollowup(body);
      setStand(result.nachbereitung);
      setText(""); setDatei(null); setErgaenzen(false); setVorschlag(null);
      setMeldung(result.einordnung === "laeuft"
        ? "Festgehalten. Bitten und Zusagen daraus erscheinen als Vorschläge, sobald die Quelle sortiert ist."
        : result.einordnung === "schon_festgehalten"
          ? "Genau das war schon festgehalten. Es wurde nichts doppelt gespeichert."
          : "Festgehalten als Quelle. Sortiert wird sie, sobald das automatische Sortieren mit der lokalen KI eingeschaltet ist.");
      onChange?.();
    } catch (cause) {
      // Der Server nennt seinen Grund; wo keiner kommt, ist offen, ob es
      // gespeichert wurde. Erneut senden legt nichts doppelt an.
      setSendFehler(cause instanceof ApiError && cause.detail && cause.status < 500
        ? cause.detail
        : "Das Festhalten ist nicht bestätigt. Bitte erneut senden; doppelt gespeichert wird dabei nichts.");
    } finally {
      setSending(false);
    }
  }

  async function mitschriftAendern(aktion: () => Promise<unknown>, text: string) {
    if (!stand?.start || sending) return;
    setSending(true); setSendFehler(""); setMeldung("");
    try {
      await aktion();
      setStand(await api.calendarFollowup(uid, stand.start));
      setMeldung(text);
      onChange?.();
    } catch {
      setSendFehler("Das hat nicht geklappt. Bitte erneut versuchen.");
    } finally {
      setSending(false);
    }
  }

  async function nichts(wert: boolean) {
    if (!stand?.start) return;
    setSending(true); setSendFehler(""); setMeldung("");
    try {
      setStand(await api.setCalendarFollowupStatus(uid, stand.start, wert));
      setMeldung(wert ? "Vermerkt: nicht nötig. Kingfisher fragt dazu nicht mehr nach." : "");
      onChange?.();
    } catch {
      setSendFehler("Das hat nicht geklappt. Bitte erneut versuchen.");
    } finally {
      setSending(false);
    }
  }

  const kopf = <div className="calendar-preparation-heading">
    <div><p className="eyebrow">NACHBEREITEN</p><h2>{stand?.summary ?? "Termin"}</h2><p>{stand ? wann(stand.start) : ""}</p></div>
    <button className="secondary-action" type="button" aria-label="Nachbereitung schließen" onClick={onClose}>Schließen</button>
  </div>;
  if (fehler) return <section className="calendar-preparation calendar-followup" aria-label="Termin nachbereiten">{kopf}
    <p role="alert">{fehler === "weg" ? "Der Termin ist im verbundenen Kalender nicht mehr zu finden." : "Der Termin kann gerade nicht geladen werden. Bitte erneut versuchen."}</p></section>;
  if (!stand) return <section className="calendar-preparation calendar-followup" aria-busy="true" aria-label="Termin nachbereiten">{kopf}<p>Wird geladen …</p></section>;

  const mitschriften = stand.transkripte ?? [];
  const angebote = stand.angebote ?? [];
  // Liegt eine Mitschrift vor, gibt es nichts nachzufragen; ergänzen darf man trotzdem.
  const formular = (stand.stand === "offen" && mitschriften.length === 0) || ergaenzen;
  const leer = datei ? false : !text.trim();
  const namen = stand.teilnehmer.map(person => displayLabel(person).name);
  return <section className="calendar-preparation calendar-followup" aria-label="Termin nachbereiten">
    {kopf}
    {stand.teilnehmer.length ? <p className="calendar-followup-people">Mit {stand.teilnehmer.map(person => displayLabel(person).name).join(", ")}</p> : null}
    {meldung && <p className="calendar-followup-done" role="status">{meldung}</p>}
    {!stand.begonnen && <p className="calendar-preparation-empty">Der Termin hat noch nicht begonnen. Nachbereiten geht, sobald er läuft.</p>}
    {mitschriften.length > 0 && <div className="calendar-followup-state" aria-label="Mitschriften zu diesem Termin">
      <p>{mitschriften.length === 1 ? "Zu diesem Termin liegt eine Mitschrift vor." : `Zu diesem Termin liegen ${mitschriften.length} Mitschriften vor.`}</p>
      {mitschriften.map(eintrag => <div className="calendar-followup-row" key={eintrag.id}>
        <ProfileSource kind="episode" id={eintrag.id} label={eintrag.titel} quiet />
        <button className="text-action" type="button" disabled={sending} onClick={() => void mitschriftAendern(() => api.transkriptLoesen(eintrag.id), "Die Zuordnung ist gelöst.")}>Gehört nicht hierher</button>
      </div>)}
      {stand.stand === "offen" && !ergaenzen && <button className="secondary-action" type="button" onClick={() => { setErgaenzen(true); setMeldung(""); }}>Etwas ergänzen</button>}
    </div>}
    {stand.begonnen && stand.termin && angebote.length > 0 && <details className="calendar-followup-angebote">
      <summary>Mitschrift zuordnen ({angebote.length})</summary>
      {angebote.map(eintrag => <div className="calendar-followup-row" key={eintrag.id}>
        <span>{eintrag.titel}<small> · aufgenommen {wann(eintrag.aufgenommen)}</small></span>
        <button className="secondary-action" type="button" disabled={sending} onClick={() => void mitschriftAendern(() => api.transkriptZuordnen(eintrag.id, stand.termin!), "Die Mitschrift gehört jetzt zu diesem Termin.")}>Zu diesem Termin</button>
      </div>)}
    </details>}
    {stand.begonnen && stand.stand === "festgehalten" && !ergaenzen && <div className="calendar-followup-state">
      <p>Nachbereitet.</p>
      {stand.episode_id && <ProfileSource kind="episode" id={stand.episode_id} label="Festgehaltenes ansehen" quiet />}
      <button className="secondary-action" type="button" onClick={() => { setErgaenzen(true); setMeldung(""); }}>Etwas ergänzen</button>
    </div>}
    {stand.begonnen && stand.stand === "nichts" && <div className="calendar-followup-state">
      <p>Vermerkt: nicht nötig.</p>
      <button className="secondary-action" type="button" disabled={sending} onClick={() => void nichts(false)}>Doch nachbereiten</button>
    </div>}
    {stand.begonnen && formular && stand.stand !== "nichts" && <form className="calendar-followup-form" onSubmit={event => { event.preventDefault(); void festhalten(); }}>
      <label htmlFor="nachbereitung-text">{ergaenzen ? "Was möchtest du ergänzen?" : frage(namen, stand.summary)}</label>
      {datei ? <p className="calendar-followup-file">Mitschrift „{datei.name}“ ist ausgewählt; deine Notizen darunter werden mitgespeichert. <button className="text-action" type="button" disabled={sending} onClick={() => setDatei(null)}>Entfernen</button></p> : null}
      <textarea id="nachbereitung-text" rows={datei ? 3 : 6} value={text} disabled={sending} onChange={event => setText(event.target.value)} placeholder={datei ? "Eigene Notizen (freiwillig)" : "Was vereinbart wurde, wer was zugesagt hat, was offen blieb …"} />
      <div className="calendar-followup-row">
        <button className="secondary-action" type="button" disabled={sending} onClick={() => dateiFeld.current?.click()}>Mitschrift wählen</button>
        <input ref={dateiFeld} type="file" accept=".txt,.md,.srt,.vtt" hidden disabled={sending} onChange={event => void dateiGewaehlt(event)} />
        <small>Ein Telefonat kannst du in zwei Sätzen festhalten. Eine Mitschrift aus Teams, Zoom oder Meet (.txt, .srt, .vtt) geht auch; Meetings aus dem Mitschriften-Ordner ordnet Kingfisher selbst zu.</small>
      </div>
      <label className="calendar-preparation-project">Projekt
        <select value={projectId} disabled={sending} onChange={event => { projektBeruehrt.current = true; setProjectId(event.target.value); setVorschlag(null); }} aria-label="Projekt der Nachbereitung">
          <option value="">Kein Projekt</option>
          {projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}
          {zugeordnet && !projects.some(project => project.id === zugeordnet.id) && <option value={zugeordnet.id}>{zugeordnet.name}</option>}
        </select>
      </label>
      {vorschlag && projectId && <p className="calendar-preparation-empty">Vorgeschlagen: {vorschlag.grund ?? vorschlag.name}</p>}
      {projektFehler && <p className="calendar-preparation-empty" role="status">Die Projektzuordnung des Termins konnte nicht geladen werden. Wähle das Projekt hier, falls es eines gibt; die Zuordnung des Termins bleibt, wie sie ist.</p>}
      {sendFehler && <p role="alert">{sendFehler}</p>}
      <div className="calendar-followup-row">
        <button className="primary-action" type="submit" disabled={sending || leer}>{sending ? "Wird festgehalten …" : "Festhalten"}</button>
        {stand.stand === "offen" && <button className="secondary-action" type="button" disabled={sending} onClick={() => void nichts(true)}>Nicht nötig</button>}
        {ergaenzen && <button className="text-action" type="button" disabled={sending} onClick={() => setErgaenzen(false)}>Abbrechen</button>}
      </div>
      <p className="calendar-preparation-empty">Gespeichert wird eine Quelle mit den Teilnehmern und dem Projekt. Bitten und Zusagen daraus werden dir vorgeschlagen, nicht ungefragt übernommen.</p>
    </form>}
    {!formular && sendFehler && <p role="alert">{sendFehler}</p>}
  </section>;
}
