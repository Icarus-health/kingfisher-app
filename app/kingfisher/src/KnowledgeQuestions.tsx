import {useEffect, useRef, useState} from "react";
import {api, type MemoryQuestion} from "./api";
import {ProfileSource} from './ProfileSource';
import { questionRelationLabel, questionTitle } from "./questionLabels";

const FIRST_PAGE = 5;
const MAX_QUESTIONS = 50;

export function visibleMemoryQuestions(items: MemoryQuestion[], limit = FIRST_PAGE) {
  return items.slice(0, Math.min(MAX_QUESTIONS, Math.max(0, limit)));
}

export function canKeepCurrent(question: MemoryQuestion) {
  return question.active_claims.length > 0;
}

function timeLabel(value: string | null) {
  if (!value) return "unbekannt";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "unbekannt";
  return new Intl.DateTimeFormat("de-DE", {dateStyle: "medium", timeStyle: "short"}).format(date);
}

export function shouldShowRecordedAt(source: MemoryQuestion["candidates"][number]["sources"][number]) {
  if (!source.recorded_at) return false;
  const recorded = new Date(source.recorded_at).getTime();
  if (Number.isNaN(recorded)) return false;
  if (!source.occurred_at) return true;
  const occurred = new Date(source.occurred_at).getTime();
  return Number.isNaN(occurred) || occurred !== recorded;
}

function SourceEvidence({source}: {source: MemoryQuestion["candidates"][number]["sources"][number]}) {
  return <div className="memory-question-source">
    <strong>{source.title}</strong>
    <blockquote>{source.quote}</blockquote>
    <p>Quelldatum: {timeLabel(source.occurred_at)}</p>
    {shouldShowRecordedAt(source) && <p>Erfasst: {timeLabel(source.recorded_at)}</p>}
    <ProfileSource kind="episode" id={source.episode_id} label="Originalquelle prüfen" readOnly />
  </div>;
}

/** Source-current, explicit decisions about durable knowledge conflicts. */
export function KnowledgeQuestions({active, onChanged}: {active: boolean; onChanged?: () => void}) {
  const [questions, setQuestions] = useState<MemoryQuestion[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [notice, setNotice] = useState("");
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null);
  const [visibleLimit, setVisibleLimit] = useState(FIRST_PAGE);
  const [revision, setRevision] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const activeRef = useRef(active);
  const lifecycle = useRef(0);
  const requestVersion = useRef(0);
  const pending = useRef(false);
  const actionVersion = useRef(0);

  useEffect(() => {
    const epoch = ++lifecycle.current;
    activeRef.current = active;
    if (!active) {
      requestVersion.current++;
      setQuestions(null);
      setLoading(false);
      setActionError("");
      setNotice("");
      return () => {if (lifecycle.current === epoch) lifecycle.current++;};
    }

    let mounted = true;
    const load = async () => {
      const version = ++requestVersion.current;
      setQuestions(null);
      setLoading(true);
      setLoadError("");
      try {
        const result = await api.memoryQuestions();
        if (!mounted || !activeRef.current || lifecycle.current !== epoch || requestVersion.current !== version) return;
        setQuestions(visibleMemoryQuestions(result.items, MAX_QUESTIONS));
        setTruncated(result.truncated);
        setVisibleLimit(FIRST_PAGE);
      } catch {
        if (!mounted || !activeRef.current || lifecycle.current !== epoch || requestVersion.current !== version) return;
        setQuestions(null);
        setLoadError("Die Wissensklärungen konnten nicht geladen werden.");
      } finally {
        if (mounted && activeRef.current && lifecycle.current === epoch && requestVersion.current === version) setLoading(false);
      }
    };

    void load();
    const onFocus = () => {
      if (pending.current) return;
      setNotice("");
      void load();
    };
    window.addEventListener("focus", onFocus);
    return () => {
      mounted = false;
      window.removeEventListener("focus", onFocus);
      if (lifecycle.current === epoch) lifecycle.current++;
      requestVersion.current++;
    };
  }, [active, revision]);

  async function decide(question: MemoryQuestion, proposalId: string | null) {
    if (!activeRef.current || pending.current) return;
    pending.current = true;
    const operation = ++actionVersion.current;
    const epoch = lifecycle.current;
    setPendingQuestion(question.id);
    setQuestions(null);
    setLoading(true);
    setActionError("");
    setNotice("");
    try {
      await api.resolveMemoryQuestion(question.id, {stand: question.stand, proposal_id: proposalId});
      if (activeRef.current && lifecycle.current === epoch) {
        setNotice(proposalId ? "Angabe bestätigt; die Prüfliste wird aktualisiert." : "Bestätigte Angabe beibehalten; Vorschläge werden aktualisiert.");
        onChanged?.();
      }
    } catch {
      if (activeRef.current && lifecycle.current === epoch) {
        setActionError("Die Klärung wurde nicht bestätigt. Der aktuelle Stand wird neu geladen; bitte prüfe die Quellen erneut.");
      }
    } finally {
      if (actionVersion.current === operation) pending.current = false;
      if (activeRef.current) {
        setPendingQuestion(null);
        setRevision(value => value + 1);
      }
    }
  }

  if (!active) return null;
  const displayed = visibleMemoryQuestions(questions ?? [], visibleLimit);
  const total = Math.min(questions?.length ?? 0, MAX_QUESTIONS);
  return <section className="task-source knowledge-questions" aria-label="Wissensklärungen">
    <h2>Wissensklärungen</h2>
    <p>Widersprüchliche Angaben bleiben offen, bis du eine ausdrücklich bestätigst oder eine bestehende bestätigte Angabe beibehältst.</p>
    {loading && questions === null && <p role="status">Wissensklärungen werden geladen …</p>}
    {loadError && <p role="alert">{loadError} <button type="button" className="secondary-action" onClick={() => setRevision(value => value + 1)}>Erneut laden</button></p>}
    {actionError && <p role="alert">{actionError}</p>}
    {notice && <p role="status">{notice}</p>}
    {truncated && <p role="note">Die ersten 50 Klärungen werden angezeigt. Nach einer Entscheidung wird die Auswahl aktualisiert.</p>}
    {questions && total === 0 && !actionError && <p role="status">Keine offenen Wissensklärungen.</p>}
    {displayed.map(question => <article className="mail-task-form" key={question.id}>
      {question.candidates.map(candidate => <section key={candidate.id} className="memory-question-candidate">
        <h3>{questionTitle(candidate.statement)}</h3>
        <p><strong>{questionRelationLabel(question.predicate)} · vorgeschlagen, noch nicht bestätigt</strong></p>
        <p>Vorgeschlagener Stand: {candidate.value}</p>
        {candidate.sources.map(source => <SourceEvidence key={`${source.episode_id}:${source.quote}`} source={source} />)}
        <details>
          <summary>Technische Zuordnung</summary>
          <p>Beziehung: {question.predicate}</p>
          <p>Zuordnung: {question.subject_ref}</p>
          {question.scope_ref ? <p>Kontextkennung: {question.scope_ref}</p> : null}
        </details>
        <button type="button" className="primary-action" disabled={pendingQuestion !== null || loading}
          onClick={() => void decide(question, candidate.id)}>
          {pendingQuestion === question.id ? "Wird gespeichert …" : "Diese Angabe bestätigen"}
        </button>
      </section>)}
      {question.active_claims.map(claim => <section key={claim.id} className="memory-question-current">
        <h3>Bestehende bestätigte Angabe</h3>
        <p>{claim.statement}</p>
        <p><strong>{questionRelationLabel(question.predicate)} · bestätigter bisheriger Stand</strong></p>
        <p>Bisheriger Stand: {claim.value}</p>
        <p>Diese Angabe bleibt als bestätigtes Wissen bestehen; die neuen Vorschläge werden verworfen.</p>
        {claim.sources.map(source => <SourceEvidence key={`${source.episode_id}:${source.quote}`} source={source} />)}
      </section>)}
      {canKeepCurrent(question) && <button type="button" className="secondary-action" disabled={pendingQuestion !== null || loading}
        onClick={() => void decide(question, null)}>
        {pendingQuestion === question.id ? "Wird gespeichert …" : "Bestätigte Angabe beibehalten"}
      </button>}
    </article>)}
    {questions && total > visibleLimit && <button type="button" className="secondary-action" disabled={loading}
      onClick={() => setVisibleLimit(value => Math.min(MAX_QUESTIONS, value + FIRST_PAGE))}>
      Weitere {Math.min(FIRST_PAGE, total - visibleLimit)} anzeigen
    </button>}
  </section>;
}
