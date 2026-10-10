import { useEffect, useRef, useState } from "react";
import { api, DocumentPreviewError, type Project } from "./api";
import { DocumentSources } from "./DocumentSources";
import { ProfileSource } from "./ProfileSource";

export function DocumentImport({initiallyExpanded=false, showLibrary=true, title='Dateien', onClose}: {
  initiallyExpanded?: boolean; showLibrary?: boolean; title?: string; onClose?: ()=>void;
} = {}) {
  const [expanded, setExpanded] = useState(initiallyExpanded);
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [file, setFile] = useState<{filename: string; body: string; warning?: string} | null>(null);
  const [result, setResult] = useState<Awaited<ReturnType<typeof api.importDocument>> | null>(null);
  const [reading, setReading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [closing,setClosing] = useState(false);
  const version = useRef(0);
  useEffect(() => {let active = true; api.projects().then(items => {if (active) setProjects(items);}).catch(() => {if (active) setError("Projekte konnten nicht geladen werden. Eine Aufnahme ohne Projekt ist möglich.");});return () => {active = false;version.current++;};}, []);
  async function choose(selected: File | undefined) {
    const current = ++version.current;
    setFile(null);setResult(null);setError("");setClosing(false);
    setReading(false);
    if (!selected) return;
    const pdf = /\.pdf$/i.test(selected.name);
    const word = /\.docx$/i.test(selected.name);
    const transcript = /\.(srt|vtt)$/i.test(selected.name);
    if (!/\.(md|markdown|txt|org|rst|csv|docx|pdf|srt|vtt)$/i.test(selected.name) || selected.size > (word || pdf ? 5 * 1024 * 1024 : 512 * 1024)) {setError("Bitte eine Textdatei bis 512 KiB oder DOCX/PDF bis 5 MiB auswählen.");return;}
    setReading(true);
    try {
      const bytes = await selected.arrayBuffer();
      let body: string;
      let warning: string | undefined;
      if (word || pdf) {
        const data = new Uint8Array(bytes);
        let binary = "";
        for (let offset = 0; offset < data.length; offset += 8192) binary += String.fromCharCode(...data.subarray(offset, offset + 8192));
        if (pdf) {
          const preview = await api.previewPdf(btoa(binary));
          body = preview.body;
          if (preview.empty_pages.length) warning = `Seiten ohne lesbare Textebene: ${preview.empty_pages.join(", ")}. Die Aufnahme enthält nur den erkannten Text.`;
        } else body = (await api.previewDocx(btoa(binary))).body;
      } else {
        body = new TextDecoder("utf-8", {fatal: true}).decode(bytes);
        if (transcript) {
          const format = selected.name.toLowerCase().endsWith(".srt") ? "srt" : "vtt";
          const preview = await api.previewTranscript(body, format);
          body = preview.body;
          warning = `${preview.segment_count} ${preview.segment_count === 1 ? "Abschnitt" : "Abschnitte"} mit relativen Zeitangaben. Sprecherlabels stammen aus der Datei und bestätigen keine Personenidentität.`;
        }
      }
      if (current !== version.current) return;
      if (!body.trim() || body.includes("\0")) {setError("Die Datei enthält keinen lesbaren Text.");return;}
      setFile({filename: selected.name, body, warning});
    } catch (cause) {if (current === version.current) setError(cause instanceof DocumentPreviewError ? cause.message : "Die Datei konnte nicht gelesen werden. Unterstützt werden UTF-8-Textdateien und unverschlüsselte DOCX/PDF mit höchstens 512 KiB Haupttext.");}
    finally {if (current === version.current) setReading(false);}
  }
  async function save() {
    if (!file || busy) return;
    setBusy(true);setError("");
    try {setResult(await api.importDocument({filename:file.filename, body:file.body, project_id: projectId || null}));setFile(null);setClosing(false);}
    catch {setError("Die Datei konnte nicht aufgenommen werden. Bitte Auswahl und Projekt prüfen und erneut versuchen.");}
    finally {setBusy(false);}
  }
  return <section className="source-section document-import" aria-label="Dateien aufnehmen">
    <div className="compact-integration-heading"><div><h2>{title}</h2><p>Dokumente als Quellen aufnehmen und verwalten.</p></div><button className="secondary-action" type="button" aria-expanded={expanded} disabled={busy || reading} onClick={() => {if(expanded && onClose) {if(file) setClosing(true); else onClose();} else setExpanded(value => !value);}}>{expanded ? "Schließen" : "Dateien verwalten"}</button></div>
    {expanded && <div>
    <p>Textdateien, Transkripte (SRT/VTT), Word-Dokumente (DOCX) und PDFs werden lokal eingelesen. Gespeichert wird nur der Text nach deiner Bestätigung. Daraus wird kein Wissen automatisch bestätigt. Die Originaldatei bleibt unverändert.</p>
    <p>Bei Word wird der Haupttext übernommen. Bilder, Formatierungen, Kopf- und Fußzeilen bleiben unberücksichtigt. Bitte die Vorschau prüfen.</p>
    <label>Datei auswählen<input type="file" accept=".md,.markdown,.txt,.org,.rst,.csv,.docx,.pdf,.srt,.vtt" disabled={busy || reading} onChange={event => {void choose(event.target.files?.[0]);event.target.value = "";}} /></label>
    <p>PDFs benötigen eine Textebene. Seitenangaben bleiben erhalten; bitte Lesereihenfolge und Vollständigkeit prüfen.</p>
    {reading && <p role="status">Text wird lokal ausgelesen …</p>}
    {file && <div><p><strong>{file.filename}</strong> · {new TextEncoder().encode(file.body).length.toLocaleString("de-DE")} Bytes</p>
      {file.warning && <p role="status">{file.warning}</p>}
      <label>Projekt für die Datei<select aria-label="Projekt für die Datei" disabled={busy} value={projectId} onChange={event => setProjectId(event.target.value)}><option value="">Ohne Projekt</option>{projects.map(project => <option value={project.id} key={project.id}>{project.name}</option>)}</select></label>
      <details><summary>Vorschau prüfen</summary><div className="task-source-body">{file.body.slice(0, 4000)}</div>{file.body.length > 4000 && <p>Vorschau gekürzt; aufgenommen wird der vollständige ausgelesene Text.</p>}</details>
      <button className="primary-action" type="button" disabled={busy} onClick={() => void save()}>Datei als Quelle aufnehmen</button>
      <button className="secondary-action" type="button" disabled={busy} onClick={() => {setFile(null);setClosing(false);}}>Abbrechen</button>
    </div>}
    {closing && file && <div className="health-confirm" role="group" aria-label="Dateivorschau schließen">
      <p>Die Dateivorschau ist noch nicht gespeichert. Beim Schließen wird dieser Entwurf verworfen; die Originaldatei bleibt erhalten.</p>
      <button type="button" className="secondary-action" disabled={busy} onClick={()=>setClosing(false)}>Weiter bearbeiten</button>
      <button type="button" className="secondary-action" disabled={busy} onClick={()=>onClose?.()}>Vorschau verwerfen und schließen</button>
    </div>}
    {result && <div role="status"><p>{result.created ? "Datei als Quelle aufgenommen." : "Dieser Inhalt ist bereits vorhanden. Herkunft und Projektzuordnung wurden nicht verändert."}</p><ProfileSource key={result.id} kind="episode" id={result.id} />{result.project_id && <p><a href={`/memory/projects/${encodeURIComponent(result.project_id)}`}>Projektakte öffnen</a></p>}</div>}
    {showLibrary && <DocumentSources key={result ? `${result.id}:${result.created}` : "initial"} />}
    {error && <p role="alert">{error}</p>}
    </div>}
  </section>;
}
