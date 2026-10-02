import { useEffect, useState } from "react";
import { api } from "./api";
import { SourceCorrection } from "./SourceCorrection";
import { SourceCategories } from "./SourceCategories";
import { SourceBezuege } from "./SourceBezuege";
import { SourceProject } from "./SourceProject";
import { Herkunft } from "./Herkunft";

type Source = Awaited<ReturnType<typeof api.profileSource>>;
/**
 * `eigeneFrage`: Die Quelle ist die eigene Frage im Gespräch („Gesprächsquelle ansehen“). Dann steht vorne nur ein Satz in
 * Alltagssprache, der Wortlaut und zwei Knöpfe mit erkennbarer Wirkung (berichtigen, nicht mehr verwenden); Status,
 * Themen, Bezüge, Sortierergebnis und Herkunft liegen eingeklappt unter „Für Techniker“ (Fremdprobe, Befund 15).
 */
export function ProfileSource({kind, id, label = "Inhalt öffnen", onChange, allowIgnore = true, allowDismiss = false, readOnly = false, quiet = false, eigeneFrage = false}: {kind: "episode" | "note"; id: string; label?: string; onChange?: (change?: "correction") => void; allowIgnore?: boolean; allowDismiss?: boolean; readOnly?: boolean; quiet?: boolean; eigeneFrage?: boolean}) {
  // Nur-Lesen: In der Belegprüfung darf das Ansehen einer Quelle niemals
  // Ausschluss oder Wiederzulassung auslösen. Ein unterdrückter Knopf allein
  // genügt nicht, deshalb sind beide Handler zusätzlich gesperrt.
  const mayIgnore = !readOnly && allowIgnore;
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Source | null>(null);
  const [error, setError] = useState(false);
  const [confirmIgnore, setConfirmIgnore] = useState(false);
  const [confirmReopen, setConfirmReopen] = useState(false);
  const [confirmDismiss, setConfirmDismiss] = useState(false);
  const [changing, setChanging] = useState(false);
  const [reopenError, setReopenError] = useState<string | null>(null);
  const [reopenBlocked, setReopenBlocked] = useState(false);
  const [reopened, setReopened] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setData(null); setError(false); setConfirmReopen(false); setConfirmIgnore(false); setConfirmDismiss(false); setReopenError(null); setReopenBlocked(false);
    let loading = false;
    async function refresh() {
      if (loading) return;
      loading = true;
      try {const result = await api.profileSource(kind, id); if (active) {setData(result); setError(false);}}
      catch {if (active) setError(true);}
      finally {loading = false;}
    }
    void refresh();
    const timer = kind === "episode" ? window.setInterval(() => {if (!document.hidden) void refresh();}, 5000) : undefined;
    return () => {active = false; window.clearInterval(timer);};
  }, [kind, id, open, revision]);
  async function ignore() {
    if (changing || readOnly) return;
    setChanging(true); setReopenError(null);
    try {
      await api.ignoreSource(id);
      // Auch übergeordnete Aussagen müssen sofort ihren neuen Stand zeigen.
      if (onChange) onChange(); else window.location.reload();
    } catch {
      setReopenError("Die Quelle konnte nicht ausgeschlossen werden. Bitte erneut versuchen.");
    } finally { setChanging(false); }
  }
  async function reopen() {
    if (changing || readOnly) return;
    setChanging(true); setReopenError(null);
    try {
      await api.reopenSource(id);
      setConfirmReopen(false); setReopened(true); setRevision(value => value + 1); onChange?.();
    } catch (failure) {
      setReopenBlocked(failure instanceof Error && failure.message === "HTTP 409");
      setReopenError(failure instanceof Error && failure.message === "HTTP 409"
        ? "Es gibt eine andere aktuelle Fassung. Diese frühere Quelle bleibt ausgeschlossen."
        : "Die Quelle konnte nicht wieder zugelassen werden. Bitte erneut versuchen.");
    } finally { setChanging(false); }
  }
  async function dismiss() {
    if (changing || readOnly || !allowDismiss || kind !== "episode") return;
    setChanging(true); setReopenError(null);
    try {
      await api.dismissWorkingMemory(id);
      if (onChange) onChange(); else window.location.reload();
    } catch {
      setReopenError("Das Sortierergebnis konnte nicht verworfen werden. Bitte erneut versuchen.");
    } finally { setChanging(false); }
  }
  const korrekturUngueltig = data?.provenance?.source_type === "manual_correction" && data?.correction_current === false;
  const berichtigt = () => {setRevision(value => value + 1); if (onChange) onChange("correction"); else window.location.reload();};
  const verwerfen = allowDismiss && !readOnly && kind === "episode" && data?.state !== "ignored" && !korrekturUngueltig ? <div>
    {!confirmDismiss && <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmDismiss(true)}>Sortierergebnis verwerfen</button>}
    {confirmDismiss && <div role="group" aria-label="Automatisches Sortierergebnis verwerfen">
      <p>Das automatische Sortierergebnis dieser Quelle wird nicht weiter verwendet und nicht erneut erzeugt. Die Originalquelle und bereits bestätigte Angaben bleiben erhalten.</p>
      <button type="button" className="primary-action" disabled={changing} onClick={() => void dismiss()}>Sortierergebnis jetzt verwerfen</button>
      <button type="button" className="secondary-action" disabled={changing} onClick={() => setConfirmDismiss(false)}>Abbrechen</button>
    </div>}
  </div> : null;
  const schlicht = data && kind === "episode" ? <>
    <p className="eigene-frage-satz">{data.state === "ignored" ? "Kingfisher verwendet diese Frage nicht mehr; gespeichert bleibt sie." : "So hat Kingfisher deine Frage gespeichert; als Wissen zählt sie erst, wenn du etwas daraus bestätigst."}</p>
    <div className="task-source-body">{data.body.slice(0, 20000)}</div>
    {data.state !== "ignored" && !readOnly && !korrekturUngueltig ? <div className="eigene-frage-knoepfe">
      {allowDismiss ? <SourceCorrection key={id} id={id} knopf="Wortlaut berichtigen" onChange={berichtigt} /> : null}
      {mayIgnore && !confirmIgnore ? <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmIgnore(true)}>Nicht mehr verwenden</button> : null}
      {mayIgnore && confirmIgnore ? <div role="group" aria-label="Nicht mehr verwenden">
        <p>Kingfisher verwendet diese Frage und die Antworten, die darauf beruhen, dann nicht mehr; gespeichert bleibt sie.</p>
        <button type="button" className="primary-action" disabled={changing} onClick={() => void ignore()}>Ja, nicht mehr verwenden</button>
        <button type="button" className="secondary-action" disabled={changing} onClick={() => setConfirmIgnore(false)}>Abbrechen</button>
      </div> : null}
    </div> : null}
    {data.state === "ignored" && !data.correction_id && !reopenBlocked && !readOnly && !korrekturUngueltig ? <div className="eigene-frage-knoepfe">
      {!confirmReopen ? <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmReopen(true)}>Wieder verwenden</button>
        : <div role="group" aria-label="Wieder verwenden">
          <p>Kingfisher verwendet die Frage dann wieder; was früher daraus folgte, bestätigst du einzeln neu.</p>
          <button className="primary-action" type="button" disabled={changing} onClick={() => void reopen()}>Ja, wieder verwenden</button>
          <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmReopen(false)}>Abbrechen</button>
        </div>}
    </div> : null}
    {data.correction_id ? <div><p>Du hast den Wortlaut berichtigt; es gilt deine Fassung.</p><ProfileSource kind="episode" id={data.correction_id} label="Deine Fassung ansehen" allowDismiss={!readOnly} readOnly={readOnly} onChange={onChange} /></div> : null}
    {reopenError ? <p role="alert">{reopenError}</p> : null}
    {reopened && data.state !== "ignored" ? <p role="status">Kingfisher verwendet die Frage wieder.</p> : null}
    <details className="quelle-technik">
      <summary>Für Techniker</summary>
      <p>Gespeicherte Quelle · keine bestätigte Aussage</p>
      {data.memory_status ? <p>{data.memory_status.label}</p> : null}
      {korrekturUngueltig ? <p>Der Quellenbezug dieser Berichtigung hat sich verändert. Sie wird nicht für Antworten verwendet.</p> : null}
      {data.state !== "ignored" ? <SourceCategories key={id} id={id} readOnly={readOnly} /> : null}
      {data.state !== "ignored" ? <SourceBezuege key={`bezuege:${id}`} id={id} readOnly={readOnly} /> : null}
      {verwerfen}
      {data.state !== "ignored" && !readOnly && !korrekturUngueltig ? <SourceProject key={id} id={id} projectId={data.project_id ?? null} /> : null}
      {data.provenance?.source_type === "manual_correction" ? <p>Herkunft: Deine Berichtigung</p> : data.provenance?.source_ref ? <p>Herkunft: {data.provenance.source_type === "chat" ? "Dein Gespräch mit Kingfisher" : data.provenance.source_ref}</p> : null}
    </details>
  </> : null;
  return <div className="task-source">
    <button className={quiet ? "quiet-source-toggle" : "secondary-action"} type="button" aria-expanded={open} disabled={changing} onClick={() => setOpen(value => !value)}>{open ? "Inhalt schließen" : label}</button>
    {open && <section aria-label="Profilquelle">
      {!data && !error && <p role="status">Inhalt wird geladen …</p>}
      {error && <p role="alert">Dieser Inhalt ist nicht verfügbar. <button type="button" onClick={() => setRevision(value => value + 1)}>Erneut versuchen</button></p>}
      {data && eigeneFrage && schlicht ? schlicht : null}
      {data && !(eigeneFrage && schlicht) && <><h3>{data.title}</h3><p>{kind === "episode" ? "Gespeicherte Quelle · keine bestätigte Aussage" : `Arbeitsnotiz · Revision ${data.revision ?? "—"}`}</p>
        {kind === "episode" && data.memory_status && <p role="status">{data.memory_status.label}</p>}
        {kind === "episode" && data.state !== "ignored" && <SourceCategories key={id} id={id} readOnly={readOnly} />}
        {kind === "episode" && data.state !== "ignored" && <SourceBezuege key={`bezuege:${id}`} id={id} readOnly={readOnly} />}
        {data.state === "ignored" && <p role="status">Diese Quelle wurde ausgeschlossen und darf nicht als Wissensbeleg verwendet werden.</p>}
        {data.provenance?.source_type === "manual_correction" && data.correction_current === false && <p role="status">Der Quellenbezug dieser Berichtigung hat sich verändert. Sie wird nicht für Antworten verwendet.</p>}
        {kind === "episode" && data.state !== "ignored" && allowDismiss && !readOnly && !(data.provenance?.source_type === "manual_correction" && data.correction_current === false) && <div>
          <SourceCorrection key={id} id={id} onChange={berichtigt} />
          {verwerfen}
        </div>}
        {kind === "episode" && data.state !== "ignored" && mayIgnore && !(data.provenance?.source_type === "manual_correction" && data.correction_current === false) && <div>
          {!confirmIgnore && <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmIgnore(true)}>Quelle ausschließen</button>}
          {confirmIgnore && <div role="group" aria-label="Quelle ausschließen">
            <p>Diese Quelle wird nicht weiter als Beleg verwendet. Davon abhängige Angaben und Gesprächsantworten werden nicht mehr verwendet. Das Original bleibt gespeichert.</p>
            <button type="button" className="primary-action" disabled={changing} onClick={() => void ignore()}>Ausschluss bestätigen</button>
            <button type="button" className="secondary-action" disabled={changing} onClick={() => setConfirmIgnore(false)}>Abbrechen</button>
          </div>}
        </div>}
        {kind === "episode" && data.correction_id && <div><p>Zu dieser Quelle gibt es eine eigene Berichtigung. Das Original bleibt ausgeschlossen.</p><ProfileSource kind="episode" id={data.correction_id} label="Berichtigung öffnen" allowDismiss={!readOnly} readOnly={readOnly} onChange={onChange} /></div>}
        {kind === "episode" && data.state === "ignored" && !data.correction_id && !reopenBlocked && !readOnly && !(data.provenance?.source_type === "manual_correction" && data.correction_current === false) && <div>
          {!confirmReopen && <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmReopen(true)}>Quelle wieder zulassen</button>}
          {confirmReopen && <div role="group" aria-label="Quelle wieder zulassen">
            <p>Der gespeicherte Inhalt wird erneut zur Prüfung zugelassen. Frühere Aussagen bleiben fraglich und müssen einzeln bestätigt werden.</p>
            <button className="primary-action" type="button" disabled={changing} onClick={() => void reopen()}>Wiederzulassung bestätigen</button>
            <button className="secondary-action" type="button" disabled={changing} onClick={() => setConfirmReopen(false)}>Abbrechen</button>
          </div>}
        </div>}
        {reopenError && <p role="alert">{reopenError}</p>}
        {reopened && data.state !== "ignored" && <p role="status">Die Quelle ist wieder zur Prüfung zugelassen. Frühere Aussagen wurden nicht bestätigt.</p>}
        {kind === "episode" && data.state !== "ignored" && !readOnly && !(data.provenance?.source_type === "manual_correction" && data.correction_current === false) && <SourceProject key={id} id={id} projectId={data.project_id ?? null} />}
        <Herkunft provenance={data.provenance} />
        <div className="task-source-body">{data.body.slice(0, 20000)}</div>
        {data.body.length > 20000 && <p>Auszug: Die Quelle ist länger als die angezeigten 20.000 Zeichen.</p>}
      </>}
    </section>}
  </div>;
}
