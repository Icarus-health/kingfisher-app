import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, request } from "./api";

type Area = "mail" | "planning" | "analysis";
type Category = "communication" | "planning" | "research" | "maintenance" | "other";
type Procedure = {
  id: string; name: string; title: string; description: string; area: Area; version: number;
  base_version?: number; state: "pending" | "active" | "rejected" | "revoked" | "superseded";
  current: boolean; positive: string; negative: string; triggers: string[];
  category?: Category; contexts?: string[];
  checks: { structure: boolean; routing_examples: boolean; human_review_required: boolean };
};
type Detail = Procedure & { steps: string[]; markdown: string; sources: Record<string, string> };
type Catalog = { items: Procedure[]; core: { id: string; name: string; title: string; category: string; purpose?: Category; area: string; description: string }[] };
type Spec = { name: string; title: string; description: string; area: Area; category?: Category; contexts: string[]; triggers: string[]; steps: string[]; positive: string; negative: string };
type Save = (spec: Spec, sources: string[]) => Promise<boolean>;
const AREAS: Record<Area, string> = { mail: "E-Mails", planning: "Planung", analysis: "Analysen" };
const CATEGORIES: Record<Category, string> = { research: "Suchen & Prüfen", communication: "Kommunikation", planning: "Planung & Arbeit", maintenance: "Gedächtnispflege", other: "Sonstiges" };
const DEFAULT_CATEGORY: Record<Area, Category> = { mail: "communication", planning: "planning", analysis: "research" };
const categoryOf = (item: Procedure) => item.category || DEFAULT_CATEGORY[item.area];
const STATES: Record<Procedure["state"], string> = { pending: "Vorgeschlagen", active: "Übernommen", rejected: "Nicht übernommen", revoked: "Zurückgenommen", superseded: "Ersetzt" };
const path = (id: string) => `/api/v1/procedures/${encodeURIComponent(id)}`;
const lines = (text: string) => text.split("\n").map(value => value.trim()).filter(Boolean);
const errorText = (error: unknown, fallback: string) => error instanceof ApiError && error.detail ? error.detail : fallback;

function ProcedureForm({ detail, busy, onSave, onCancel }: { detail?: Detail; busy: boolean; onSave: Save; onCancel?: () => void }) {
  const [name, setName] = useState(detail?.name || "");
  const [title, setTitle] = useState(detail?.title || "");
  const [description, setDescription] = useState(detail?.description || "");
  const [area, setArea] = useState<Area>(detail?.area || "mail");
  const [category, setCategory] = useState<Category | "">(detail?.category || "");
  const [contexts, setContexts] = useState(detail?.contexts?.join("\n") || "");
  const [triggers, setTriggers] = useState(detail?.triggers.join("\n") || "");
  const [steps, setSteps] = useState(detail?.steps.join("\n") || "");
  const [positive, setPositive] = useState(detail?.positive || "");
  const [negative, setNegative] = useState(detail?.negative || "");
  const [sources, setSources] = useState(Object.keys(detail?.sources || {}).join("\n"));
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    const triggerField = event.currentTarget.elements.namedItem("triggers") as HTMLTextAreaElement;
    const triggerLines = lines(triggers);
    triggerField.setCustomValidity(triggerLines.length > 8 || triggerLines.some(value => value.length < 2 || value.length > 60)
      ? "Bitte höchstens 8 Auslöser mit je 2 bis 60 Zeichen angeben." : "");
    if (!event.currentTarget.reportValidity()) return;
    const saved = await onSave({ name: name.trim(), title: title.trim(), description: description.trim(), area,
      category: category || DEFAULT_CATEGORY[area], contexts: lines(contexts),
      triggers: triggerLines, steps: lines(steps), positive: positive.trim(), negative: negative.trim() }, lines(sources));
    if (saved && mounted.current) {
      if (onCancel) onCancel();
      else { setName(""); setTitle(""); setDescription(""); setCategory(""); setContexts(""); setTriggers(""); setSteps(""); setPositive(""); setNegative(""); setSources(""); }
    }
  }
  return <form onSubmit={event => void submit(event)}>
    {detail ? <p className="source-hint">Neue Fassung von Version {detail.version}. Die bisherige Fassung bleibt bis zur Übernahme bestehen.</p> : null}
    <fieldset className="source-form" disabled={busy}>
      <label>Kurzname (Kleinbuchstaben und Bindestriche)<input required minLength={3} maxLength={64} pattern={"[a-z][a-z0-9\\-]{2,63}"} value={name} readOnly={Boolean(detail)} onChange={event => setName(event.target.value)} /></label>
      <label>Titel<input required minLength={3} maxLength={100} value={title} onChange={event => setTitle(event.target.value)} /></label>
      <label>Zweck<textarea required minLength={10} maxLength={400} value={description} onChange={event => setDescription(event.target.value)} /></label>
      <label>Bereich<select value={area} onChange={event => setArea(event.target.value as Area)}>{Object.entries(AREAS).map(([key, value]) => <option key={key} value={key}>{value}</option>)}</select></label>
      <details className="quiet-details"><summary>Einordnung anpassen</summary>
        <label>Kategorie<select value={category} onChange={event => setCategory(event.target.value as Category | "")}>
          <option value="">Automatisch nach Aufgabenbereich</option>{Object.entries(CATEGORIES).map(([key, value]) => <option key={key} value={key}>{value}</option>)}
        </select></label>
        <label>Besonderer Anwendungskontext (optional, einer je Zeile)<textarea maxLength={243} value={contexts} onChange={event => setContexts(event.target.value)} /></label>
        <p className="source-hint">Leer gilt allgemein. Bis zu vier konkrete Kontexte, etwa Zunft. Ein Kontext muss ausdrücklich in der Anfrage stehen. Personen und Projekte werden weiterhin über ihre Akten geklärt.</p>
      </details>
      <label>Wann passt der Ablauf? Bis zu 8 Ausdrücke mit je 2 bis 60 Zeichen, einer je Zeile<textarea name="triggers" required maxLength={487} value={triggers} onChange={event => { event.currentTarget.setCustomValidity(""); setTriggers(event.target.value); }} /></label>
      <label>Schritte, einer je Zeile<textarea required maxLength={12000} value={steps} onChange={event => setSteps(event.target.value)} /></label>
      <label>Passendes Beispiel<textarea required minLength={5} maxLength={400} value={positive} onChange={event => setPositive(event.target.value)} /></label>
      <label>Gegenbeispiel: Wann darf er nicht gewählt werden?<textarea required minLength={5} maxLength={400} value={negative} onChange={event => setNegative(event.target.value)} /></label>
      <label>Belegkennungen, eine je Zeile (optional)<textarea maxLength={6000} value={sources} onChange={event => setSources(event.target.value)} /></label>
      <div className="source-form-actions"><button type="submit" className="primary-action">Als Vorschlag speichern</button>{onCancel ? <button type="button" className="secondary-action" onClick={onCancel}>Abbrechen</button> : null}</div>
    </fieldset>
  </form>;
}

function download(detail: Detail) {
  const url = URL.createObjectURL(new Blob([detail.markdown], { type: "text/markdown;charset=utf-8" }));
  const link = document.createElement("a");
  link.href = url; link.download = `${detail.name.replace(/[^a-z0-9_-]/gi, "-")}-v${detail.version}.md`;
  document.body.append(link); link.click(); link.remove();
  URL.revokeObjectURL(url);
}

function ProcedureRow({ item, busy, onAction, onSave, targeted = false }: { item: Procedure; busy: boolean; targeted?: boolean;
  onAction: (id: string, action: "accept" | "reject" | "revoke") => Promise<void>; onSave: Save }) {
  const [opened, setOpened] = useState(targeted);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [editing, setEditing] = useState(false);
  const generation = useRef(0);
  const summary = useRef<HTMLElement>(null);
  useEffect(() => {
    setOpened(targeted);
    if (!targeted) return;
    // Erst nach dem übergeordneten Einstellungsabschnitt ins Ziel springen.
    const frame = requestAnimationFrame(() => {
      summary.current?.focus({ preventScroll: true });
      summary.current?.scrollIntoView({ block: "start" });
    });
    return () => cancelAnimationFrame(frame);
  }, [targeted]);
  useEffect(() => {
    if (!opened) return;
    const current = ++generation.current;
    setError(""); setDetail(null);
    request<Detail>(path(item.id)).then(value => { if (generation.current === current) setDetail(value); })
      .catch(error => { if (generation.current === current) setError(errorText(error, "Die Fassung konnte nicht geladen werden.")); });
    return () => { generation.current++; };
  }, [opened, item.id, attempt, targeted]);
  // Eine Listenzeile ist keine vollständige Prüfung: Übernehmen erst nach dem Lesen der aktuellen Fassung.
  const canAccept = Boolean(detail && detail.state === "pending" && detail.current && detail.checks.structure === true && detail.checks.routing_examples === true);
  return <details className="quiet-details" open={opened} onToggle={event => { if (event.target === event.currentTarget) setOpened(event.currentTarget.open); }}>
    <summary ref={summary}>{item.title} · Version {item.version} · {STATES[item.state]}{!item.current ? " · Grundlage verändert" : ""}</summary>
    {opened ? <>
      <p className="source-hint">{item.description}</p>
      {error ? <p role="alert">{error} <button type="button" className="secondary-action" disabled={busy} onClick={() => setAttempt(value => value + 1)}>Erneut laden</button></p> : null}
      {!detail && !error ? <p role="status">Fassung wird gelesen …</p> : null}
      {detail ? <>
        <p>{AREAS[detail.area]} · Version {detail.version}{detail.base_version !== undefined ? ` · auf Basis von Version ${detail.base_version}` : ""} · {STATES[detail.state]}</p>
        <p>{CATEGORIES[categoryOf(detail)]} · Bei Bedarf · {detail.contexts?.length ? detail.contexts.join(" / ") : "Allgemeiner Ablauf"}</p>
        {!detail.current ? <p role="status">Die Beleggrundlage hat sich verändert. Diese Fassung kann nicht übernommen werden. Prüfe die Quellen und schlage eine neue Fassung vor.</p> : null}
        <p>Strukturprüfung: {detail.checks.structure === true ? "bestanden" : "nicht bestanden"}. Auswahlbeispiele: {detail.checks.routing_examples === true ? "bestanden" : "nicht bestanden"}. Ob die Schritte fachlich passen, prüfst du selbst vor dem Übernehmen.</p>
        <p><strong>Passend bei:</strong> {detail.triggers.join("; ")}</p>
        <ol>{detail.steps.map((step, index) => <li key={index}>{step}</li>)}</ol>
        <details className="quiet-details"><summary>Beispiele und Herkunft</summary>
          <p><strong>Passendes Beispiel:</strong> {detail.positive}</p>
          <p><strong>Gegenbeispiel:</strong> {detail.negative}</p>
          {Object.keys(detail.sources).length ? <dl>{Object.entries(detail.sources).map(([id, source]) => <div key={id}><dt>{id}</dt><dd>{source}</dd></div>)}</dl> : <p>Ohne zusätzliche Quellenbelege; manuell vorgeschlagen.</p>}
        </details>
        <div className="source-form-actions">
          {detail.state === "pending" ? <><button type="button" className="primary-action" disabled={busy || !canAccept} onClick={() => void onAction(detail.id, "accept")}>Geprüft übernehmen</button>
            <button type="button" className="secondary-action" disabled={busy} onClick={() => void onAction(detail.id, "reject")}>Nicht übernehmen</button></> : null}
          {detail.state === "active" ? <button type="button" className="secondary-action" disabled={busy} onClick={() => void onAction(detail.id, "revoke")}>Zurücknehmen</button> : null}
          <button type="button" className="secondary-action" disabled={busy} onClick={() => setEditing(value => !value)}>Neue Fassung</button>
          <button type="button" className="secondary-action" disabled={busy} onClick={() => download(detail)}>Als Markdown sichern</button>
        </div>
        {editing ? <ProcedureForm detail={detail} busy={busy} onSave={onSave} onCancel={() => setEditing(false)} /> : null}
      </> : null}
    </> : null}
  </details>;
}

export function ProcedureSettings() {
  const [target, setTarget] = useState(() => new URLSearchParams(window.location.search).get("ablauf"));
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [readback, setReadback] = useState(0);
  const [verified, setVerified] = useState(false);
  const [category, setCategory] = useState("");
  const [search, setSearch] = useState("");
  const mounted = useRef(false);
  const generation = useRef(0);
  const working = useRef(false);
  useEffect(() => {
    const readTarget = () => setTarget(new URLSearchParams(window.location.search).get("ablauf"));
    window.addEventListener("popstate", readTarget);
    window.addEventListener("hashchange", readTarget);
    return () => { window.removeEventListener("popstate", readTarget); window.removeEventListener("hashchange", readTarget); };
  }, []);
  async function load() {
    const current = ++generation.current;
    setVerified(false);
    try {
      const value = await request<Catalog>("/api/v1/procedures");
      if (mounted.current && current === generation.current) { setCatalog(value); setVerified(true); setReadback(value => value + 1); }
      return value;
    } catch (error) {
      if (mounted.current && current === generation.current) setError(errorText(error, "Die Abläufe konnten nicht geladen werden."));
      throw error;
    }
  }
  useEffect(() => {
    mounted.current = true; setError("");
    void load().catch(() => { /* Die jeweilige Ladegeneration meldet den Fehler. */ });
    return () => { mounted.current = false; generation.current++; };
  }, [attempt]);
  async function mutate(action: () => Promise<Detail>, success: string) {
    if (working.current) return false;
    working.current = true; setBusy(true); setError(""); setMessage("");
    try {
      const saved = await action();
      if (!mounted.current) return false;
      const observed = await load();
      const item = observed.items.find(item => item.id === saved.id);
      if (!item || item.version !== saved.version || item.state !== saved.state || (saved.state === "active" && !item.current)) {
        throw new Error("Der neu gelesene Stand stimmt nicht mit dem Speicherergebnis überein.");
      }
      if (mounted.current) setMessage(success);
      return mounted.current;
    } catch (error) {
      if (mounted.current) { setVerified(false); setError(errorText(error, "Der gespeicherte Stand konnte nicht bestätigt werden. Bitte erneut laden und prüfen.")); }
      return false;
    } finally {
      working.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  const save: Save = (spec, sources) => mutate(() => request<Detail>("/api/v1/procedures", {
    method: "POST", body: JSON.stringify({ spec, sources }),
  }), "Als Vorschlag gespeichert. Er wird erst nach deiner Prüfung und Übernahme verwendet.");
  async function act(id: string, action: "accept" | "reject" | "revoke") {
    await mutate(() => request<Detail>(`${path(id)}/${action}`, { method: "POST", body: "{}" }),
      action === "accept" ? "Übernommen. Kingfisher kann diesen Ablauf bei passenden Anfragen auswählen." : action === "reject" ? "Vorschlag nicht übernommen." : "Zurückgenommen. Der Ablauf wird nicht mehr ausgewählt.");
  }
  const active = catalog?.items.filter(item => item.state === "active" && item.current).length || 0;
  const pending = catalog?.items.filter(item => item.state === "pending").length || 0;
  const matches = (item: Procedure) => (!category || categoryOf(item) === category)
    && [item.title, item.description, ...item.triggers, ...(item.contexts || [])].join(" ").toLocaleLowerCase("de").includes(search.trim().toLocaleLowerCase("de"));
  const visible = catalog?.items.filter(item => item.id === target || matches(item)) || [];
  const outsideFilter = catalog?.items.some(item => item.id === target && !matches(item));
  return <section className="source-section compact-model" aria-label="Bewährte Abläufe">
    <p className="source-hint">Essenzielle Grundverfahren gelten immer. Passende übernommene Skills lädt Kingfisher bei Bedarf. Eigene Abläufe bleiben lokal und werden erst nach deiner Prüfung verwendet.</p>
    {catalog ? <p>{active} verwendbar · {pending} zur Prüfung</p> : !error ? <p role="status">Abläufe werden gelesen …</p> : null}
    {message ? <p role="status">{message}</p> : null}
    {error ? <p role="alert">{error} <button className="secondary-action" type="button" disabled={busy} onClick={() => setAttempt(value => value + 1)}>Stand erneut laden</button></p> : null}
    {verified && target && !catalog?.items.some(item => item.id === target) ? <p role="alert">Dieser Ablauf ist nicht mehr verfügbar. Du kannst einen anderen Eintrag in der Bibliothek öffnen.</p> : null}
    {catalog ? <>
      <div className="source-form">
        <label>Suche<input type="search" aria-label="Abläufe durchsuchen" value={search} onChange={event => setSearch(event.target.value)} placeholder="Titel, Anlass oder Kontext" /></label>
        <label>Kategorie<select aria-label="Abläufe nach Kategorie filtern" value={category} onChange={event => setCategory(event.target.value)}>
          <option value="">Alle Kategorien</option>{Object.entries(CATEGORIES).map(([key, value]) => <option key={key} value={key}>{value}</option>)}
        </select></label>
      </div>
      {outsideFilter ? <p role="status">Der angeforderte Ablauf bleibt unabhängig vom Filter zur Prüfung sichtbar.</p> : null}
      {visible.map(item => <ProcedureRow key={`${item.id}:${readback}`} item={item} targeted={item.id === target} busy={busy || !verified} onAction={act} onSave={save} />)}
      {!visible.length ? <p>{catalog.items.length ? "Keine passenden Abläufe. Passe Suche oder Kategorie an." : "Noch keine eigenen Abläufe vorgeschlagen. Im Gespräch kannst du „Lerne diesen Ablauf: …“ schreiben."}</p> : null}
      <details className="quiet-details"><summary>Eigenen Ablauf vorschlagen</summary><ProcedureForm busy={busy || !verified} onSave={save} /></details>
      <details className="quiet-details"><summary>Mitgelieferte Abläufe ({catalog.core.length})</summary>
        {(["essential", "contextual"] as const).map(tier => <div key={tier}>
          <h4>{tier === "essential" ? "Essenzielle Grundverfahren" : "Bei Bedarf"}</h4>
          {catalog.core.filter(item => item.category === tier && (!category || item.purpose === category)).map(item => <details className="quiet-details" key={item.id}>
            <summary>{item.title}{item.purpose ? ` · ${CATEGORIES[item.purpose]}` : ""}</summary><p>{item.description}</p>
          </details>)}
        </div>)}
      </details>
    </> : null}
  </section>;
}
