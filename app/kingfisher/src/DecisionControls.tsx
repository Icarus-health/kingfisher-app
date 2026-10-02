import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { api, type Decision, type DecisionBasis } from "./api";
import "./DecisionControls.css";

function sourceLabel(kind: string) {
  const labels: Record<string, string> = {
    assertion: "Aussage",
    claim: "Bestätigtes Wissen",
    self: "Aussage",
    knowledge: "Bestätigtes Wissen",
    episode: "Episode",
    message: "Nachricht",
  };
  return (labels[kind.toLowerCase()] ?? kind) || "Quelle";
}

function stateLabel(status: string) {
  return ({ active: "Aktiv", current: "Aktuell", disputed: "Strittig", superseded: "Ersetzt", retracted: "Widerrufen", expired: "Abgelaufen", redacted: "Inhalt entfernt" }[status] ?? status);
}

function basisParts(id: string) {
  if (id.startsWith("assertion:")) return { source: "assertion", id: id.slice("assertion:".length) };
  if (id.startsWith("claim:")) return { source: "claim", id: id.slice("claim:".length) };
  return { source: "derived", id };
}

function decisionStatus(decision: Decision) {
  if (decision.status === "retracted" || decision.status === "zurückgenommen" || decision.status === "withdrawn") return "Zurückgenommen";
  if (decision.erschuettert) return "Grundlage prüfen";
  if (decision.ohne_grundlage) return "Ohne hinterlegte Grundlage";
  return decision.status === "active" ? "Grundlage unverändert" : stateLabel(decision.status);
}

function formatDate(value: string | null | undefined) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("de-DE", { dateStyle: "medium" }).format(date);
}

export function DecisionControls({ projectId }: { projectId: string }) {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [bases, setBases] = useState<DecisionBasis[]>([]);
  const [statement, setStatement] = useState("");
  const [selectedBases, setSelectedBases] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const [reloadVersion, setReloadVersion] = useState(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    setLoading(true);
    setError(null);
    Promise.all([api.decisions(), api.decisionBasis()])
      .then(([decisionResult, basisResult]) => {
        if (version !== requestVersion.current) return;
        setDecisions(decisionResult.items);
        setBases(basisResult.items);
        setSelectedBases(current => current.filter(id => basisResult.items.some(item => item.id === id)));
      })
      .catch(() => {
        if (version === requestVersion.current) setError("Entscheidungen konnten nicht geladen werden. Bitte erneut versuchen.");
      })
      .finally(() => {
        if (version === requestVersion.current) setLoading(false);
      });
    return () => { requestVersion.current++; };
  }, [projectId, reloadVersion]);

  const visibleDecisions = useMemo(
    () => projectId ? decisions.filter((decision) => decision.project_id === projectId) : decisions,
    [decisions, projectId],
  );

  function clearForm() {
    setCreating(false);
    setStatement("");
    setSelectedBases([]);
  }

  function toggleBasis(id: string) {
    setSelectedBases((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id]);
  }

  async function saveDecision(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanStatement = statement.trim();
    if (!cleanStatement || busy) return;
    const derivedFrom: string[] = [];
    const claimIds: string[] = [];
    selectedBases.forEach((basisId) => {
      const basis = basisParts(basisId);
      if (basis.source === "claim") claimIds.push(basis.id);
      else derivedFrom.push(basis.id);
    });
    setBusy(true);
    setError(null);
    try {
      const decision = await api.addDecision({
        statement: cleanStatement,
        derived_from: derivedFrom,
        claim_ids: claimIds,
        ...(projectId ? { project_id: projectId } : {}),
      });
      setDecisions((current) => [decision, ...current.filter((item) => item.id !== decision.id)]);
      clearForm();
    } catch {
      setError("Die Entscheidung konnte nicht gespeichert werden. Bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  async function retractDecision(id: string) {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const decision = await api.retractDecision(id);
      setDecisions((current) => current.map((item) => item.id === decision.id ? decision : item));
      setConfirmingId(null);
    } catch {
      setError("Die Entscheidung konnte nicht zurückgenommen werden. Bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-label="Entscheidungen" className="decision-controls">
      <div className="decision-controls-heading">
        <div>
          <h2>Entscheidungen</h2>
          <p>Festgehaltene Entscheidungen mit ihrer Grundlage und ihrem aktuellen Zustand.</p>
        </div>
        <button aria-expanded={creating} className="secondary-action" disabled={busy || loading} onClick={() => { setError(null); setCreating((open) => !open); }} type="button">+ Entscheidung</button>
      </div>

      {creating ? (
        <form aria-label="Entscheidung festhalten" className="decision-create-form" onSubmit={saveDecision}>
          <label>
            Entscheidung
            <textarea autoFocus disabled={busy || loading} onChange={(event) => setStatement(event.target.value)} placeholder="Was gilt ab jetzt?" required value={statement} />
          </label>
          <fieldset disabled={busy || loading}>
            <legend>Grundlage <small>(optional)</small></legend>
            {bases.length ? bases.map((basis) => {
              const parsed = basisParts(basis.id);
              return <label className="decision-basis-option" key={basis.id}><input checked={selectedBases.includes(basis.id)} onChange={() => toggleBasis(basis.id)} type="checkbox" /><span><strong>{sourceLabel(parsed.source)}</strong> {basis.statement}</span></label>;
            }) : <p className="decision-muted">Keine Grundlage verfügbar. Die Entscheidung kann trotzdem ausdrücklich festgehalten werden.</p>}
          </fieldset>
          <div className="decision-form-actions">
            <button className="secondary-action" disabled={busy || loading} onClick={clearForm} type="button">Abbrechen</button>
            <button className="primary-action" disabled={busy || !statement.trim()} type="submit">{busy ? "Wird gespeichert …" : "Entscheidung speichern"}</button>
          </div>
        </form>
      ) : null}

      {loading ? <p className="decision-muted" role="status">Entscheidungen werden geladen …</p> : null}
      {!loading && !error && !visibleDecisions.length ? <p className="decision-muted">Noch keine Entscheidung für dieses Projekt.</p> : null}
      <div className="decision-list">
        {visibleDecisions.map((decision) => {
          const date = formatDate(decision.getroffen_am);
          return <article className={`decision-row ${decision.status === "retracted" || decision.status === "zurückgenommen" || decision.status === "withdrawn" ? "is-retracted" : ""}`} key={decision.id}>
            <div className="decision-row-main">
              <div className="decision-row-meta"><span className="decision-status">{decisionStatus(decision)}</span>{date ? <time dateTime={decision.getroffen_am}>{date}</time> : null}</div>
              <p className="decision-statement">{decision.satz}</p>
              {decision.grundlage?.length ? <div className="decision-basis"><span>Grundlage</span>{decision.grundlage.map((basis) => <p key={basis.id}><strong>{stateLabel(basis.status)}</strong> {basis.satz}</p>)}</div> : <p className="decision-no-basis">Keine Grundlage hinterlegt. Änderungen an Annahmen können hier nicht geprüft werden.</p>}
              {decision.wackler?.length ? <div className="decision-wackler"><span>Veränderte Annahmen</span>{decision.wackler.map((wackler) => <p key={wackler.annahme_id || wackler.annahme}><strong>{stateLabel(wackler.status)}{wackler.strittig ? " · strittig" : ""}</strong> {wackler.annahme}{wackler.ersetzt_durch ? ` → ${wackler.ersetzt_durch}` : ""}</p>)}</div> : null}
            </div>
            {(decision.status === "active" || decision.status === "disputed") ? <div className="decision-retract">
              {confirmingId === decision.id ? <><span>Wirklich zurücknehmen?</span><button className="secondary-action decision-confirm" disabled={busy || loading} onClick={() => void retractDecision(decision.id)} type="button">Bestätigen</button><button className="text-action" disabled={busy || loading} onClick={() => setConfirmingId(null)} type="button">Abbrechen</button></> : <button className="text-action" disabled={busy || loading} onClick={() => setConfirmingId(decision.id)} type="button">Entscheidung zurücknehmen</button>}
            </div> : null}
          </article>;
        })}
      </div>
      {error ? <p aria-live="polite" className="decision-controls-error" role="alert">{error} <button type="button" disabled={busy || loading} onClick={() => setReloadVersion(value => value + 1)}>Neu laden</button></p> : null}
    </section>
  );
}
