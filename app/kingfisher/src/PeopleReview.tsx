import { useEffect, useState } from "react";

import { ApiError, api, type GraphNode, type MemoryGraph, type PersonMerge, type PersonMergePreview } from "./api";
import { navigate } from "./ui";
import { PersonDigest } from "./PersonDigest";
import { PeopleMentions } from "./PeopleMentions";
import { nichtMehrZuordenbar } from "./personMergeLost";
import { isPerson, quality, duplicateIds } from "./peopleQuality";
export { personNodes, type PersonFilter } from "./peopleQuality";
import "./PeopleReview.css";

function openPerson(node: GraphNode) {
  if (node.attributes.identity_resolution === "confirmed_group") navigate("/memory?people=review");
  else if (node.attributes.identity_resolution === "explicit_registry") navigate(`/memory/registry/${encodeURIComponent(node.id)}`);
  else navigate(`/memory/people/${encodeURIComponent(node.label)}`);
}

function MergeCandidate({ members, onChanged }: { members: GraphNode[]; onChanged: () => Promise<void> }) {
  const [selected, setSelected] = useState(() => new Set(members.map(member => member.id)));
  const [label, setLabel] = useState(members[0]?.label ?? "");
  const [preview, setPreview] = useState<PersonMergePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedIds = members.filter(member => selected.has(member.id)).map(member => member.id);
  const ready = selectedIds.length >= 2 && label.trim().length > 0;
  const memberSignature = members.map(member => `${member.id}:${member.label}`).join("|");
  const edited = () => { setPreview(null); setError(""); };
  useEffect(() => { setPreview(null); setError(""); }, [memberSignature]);

  async function showPreview() {
    if (!ready || busy) return;
    setBusy(true); setError("");
    try { setPreview(await api.previewPersonMerge(selectedIds, label.trim())); }
    catch { setError("Die Vorschau konnte nicht geladen werden. Bitte erneut versuchen."); }
    finally { setBusy(false); }
  }
  async function confirm() {
    if (!preview || busy) return;
    setBusy(true); setError("");
    try { await api.confirmPersonMerge(preview.member_ids, preview.label, preview.preview_token); await onChanged(); }
    catch (cause) {
      setError(cause instanceof ApiError && cause.status === 409
        ? "Die Daten haben sich geändert. Bitte lade eine neue Vorschau."
        : "Die Zusammenführung konnte nicht gespeichert werden. Bitte erneut versuchen.");
      setPreview(null);
    } finally { setBusy(false); }
  }

  return <article className="people-review-group">
    <h3>Mögliche Duplikate</h3><p>Wähle mindestens zwei Akten und vergleiche ihre Quellen.</p>
    <fieldset disabled={busy}><legend className="sr-only">Akten auswählen</legend>
      {members.map(member => <label className="people-review-choice" key={member.id}>
        <input type="checkbox" checked={selected.has(member.id)} disabled={!selected.has(member.id) && selected.size >= 20} onChange={event => {
          setSelected(current => { const next = new Set(current); event.target.checked ? next.add(member.id) : next.delete(member.id); return next; }); edited();
        }} />
        <span><button type="button" className="people-review-link" onClick={() => openPerson(member)}>{member.label}</button><small>{member.attributes.duplicate_reason === "same_mailbox" ? "Gleiche Mailbox" : "Gleicher Name"}</small></span>
      </label>)}
      <label className="people-review-label">Gemeinsamer Name<input maxLength={500} value={label} onChange={event => { setLabel(event.target.value); edited(); }} /></label>
    </fieldset>
    {selectedIds.length < 2 ? <p className="people-review-hint">Bitte mindestens zwei Akten auswählen.</p> : null}
    {!preview ? <button className="people-review-action" type="button" disabled={!ready || busy} onClick={() => void showPreview()}>{busy ? "Vorschau wird geladen …" : "Vorschau anzeigen"}</button>
      : <section className="people-review-preview" aria-label="Vorschau der Zusammenführung">
        <h4>{preview.label}</h4><ul>{preview.members.map(member => <li key={member.id}><button type="button" className="people-review-link" onClick={() => openPerson(member)}>{member.label}</button></li>)}</ul>
        <p>{preview.evidence_count} {preview.evidence_count === 1 ? "Beleg" : "Belege"} werden gemeinsam angezeigt.</p>
        <p>Die ursprünglichen Akten und ihre Quellen bleiben unverändert. Nur die Ansicht zeigt sie gemeinsam.</p>
        <button className="people-review-action" type="button" disabled={busy} onClick={() => void confirm()}>{busy ? "Wird gespeichert …" : "Zusammenführung bestätigen"}</button>
      </section>}
    {error ? <p className="people-review-error" role="alert">{error}</p> : null}
  </article>;
}

function SavedMerge({ merge, onChanged, verloren = [] }: { merge: PersonMerge; onChanged: () => Promise<void>; verloren?: Array<{ id: string; label: string }> }) {
  const [confirming, setConfirming] = useState(false); const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  async function undo() {
    setBusy(true); setError(false);
    try { await api.undoPersonMerge(merge.id); await onChanged(); } catch { setError(true); } finally { setBusy(false); }
  }
  return <article className={`people-review-saved${merge.undone_at ? " undone" : ""}`}>
    <h3>{merge.label}</h3><p>{merge.undone_at ? "Aufgehoben" : "Gemeinsam angezeigt"} · {new Date(merge.created_at).toLocaleDateString("de-DE")}</p>
    <ul>{merge.members.map(member => <li key={member.id}><button type="button" className="people-review-link" onClick={() => openPerson(member)}>{member.label}</button></li>)}</ul>
    {!merge.undone_at && verloren.length ? <section className="people-review-verloren" aria-label="Nicht mehr zuordenbar">
      <h4>Nicht mehr zuordenbar</h4>
      <p>{verloren.length === 1 ? "Diese Akte gibt" : "Diese Akten geben"} es im Gedächtnis nicht mehr, zum Beispiel weil die Quelle entfernt wurde. Sie gehört{verloren.length === 1 ? "" : "en"} deshalb nicht mehr zu dieser Zusammenführung. Mit „Zusammenführung aufheben“ löst du sie ganz auf.</p>
      <ul>{verloren.map(eintrag => <li key={eintrag.id}>{eintrag.label}</li>)}</ul>
    </section> : null}
    {!merge.undone_at ? <PersonDigest personId={merge.id} /> : null}
    {!merge.undone_at && !confirming ? <button className="people-review-secondary" type="button" onClick={() => setConfirming(true)}>Zusammenführung aufheben</button> : null}
    {!merge.undone_at && confirming ? <div className="people-review-confirm" role="group" aria-label="Aufhebung bestätigen"><p>Die Akten wieder einzeln im Gedächtnis anzeigen?</p><button className="people-review-action" type="button" disabled={busy} onClick={() => void undo()}>{busy ? "Wird aufgehoben …" : "Ja, aufheben"}</button><button className="people-review-secondary" type="button" disabled={busy} onClick={() => setConfirming(false)}>Abbrechen</button></div> : null}
    {error ? <p className="people-review-error" role="alert">Die Zusammenführung konnte nicht aufgehoben werden. Bitte erneut versuchen.</p> : null}
  </article>;
}

export function PeopleReview({ graph, onGraphRefresh }: { graph: MemoryGraph; onGraphRefresh: () => Promise<void> }) {
  const [merges, setMerges] = useState<PersonMerge[]>([]); const [mergeError, setMergeError] = useState(false);
  const people = graph.nodes.filter(node => isPerson(node) && node.attributes.identity_resolution !== "confirmed_group");
  const byId = new Map(people.map(node => [node.id, node])); const duplicateGroups = new Map<string, GraphNode[]>();
  for (const node of people.filter(node => quality(node) !== "automated" && duplicateIds(node).length > 0)) {
    const ids = [node.id, ...duplicateIds(node)].filter(id => byId.has(id)).sort();
    if (ids.length >= 2) duplicateGroups.set(ids.join("|"), ids.map(id => byId.get(id)!));
  }
  const flagged = people.filter(node => quality(node) === "review" && duplicateIds(node).length === 0);
  async function loadMerges() { setMergeError(false); try { setMerges((await api.personMerges()).merges); } catch { setMergeError(true); } }
  async function refresh() { await Promise.all([loadMerges(), onGraphRefresh()]); }
  useEffect(() => { void loadMerges(); }, []);

  return <section className="people-review" aria-label="Personen prüfen">
    <p className="people-review-note">Mögliche Duplikate werden erst nach deiner Bestätigung gemeinsam angezeigt. Die ursprünglichen Akten und Quellen bleiben erhalten.</p>
    <PeopleMentions />
    {merges.length ? <section className="people-review-history" aria-label="Gespeicherte Zusammenführungen"><h2>Zusammengeführte Personen</h2>{merges.map(merge => <SavedMerge key={merge.id} merge={merge} onChanged={refresh} verloren={nichtMehrZuordenbar(graph, merge.id)} />)}</section> : null}
    {mergeError ? <p className="people-review-error" role="alert">Gespeicherte Zusammenführungen konnten nicht geladen werden. <button type="button" onClick={() => void loadMerges()}>Erneut laden</button></p> : null}
    {Array.from(duplicateGroups.values()).map(group => <MergeCandidate key={group.map(node => node.id).join("|")} members={group} onChanged={refresh} />)}
    {flagged.length ? <article className="people-review-group"><h3>Ungeklärte Personen</h3>{flagged.map(node => <p key={node.id}><button type="button" className="people-review-link" onClick={() => openPerson(node)}>{node.label}</button><small>{typeof node.attributes.quality_reason === "string" ? node.attributes.quality_reason : "Bitte prüfen"}</small></p>)}</article> : null}
    {!duplicateGroups.size && !flagged.length && !merges.length && !mergeError ? <p aria-live="polite">Keine Personen zur Prüfung.</p> : null}
  </section>;
}
