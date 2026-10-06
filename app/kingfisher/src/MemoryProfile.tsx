import { useEffect, useMemo, useState } from "react";

import { api, type PersonProfile as PersonProfileData, type ProjectProfile as ProjectProfileData, type Task, type RegistryProfile as RegistryProfileData } from "./api";
import { ClaimEvidence } from "./ClaimEvidence";
import { ClaimControls } from "./ClaimControls";
import { DecisionControls } from "./DecisionControls";
import { ProfileSource } from "./ProfileSource";
import { TaskSource } from "./TaskSource";
import { IdentityControls } from "./IdentityControls";
import { displayLabel } from "./displayIdentity";
import { PersonDigest } from "./PersonDigest";
import { Chronik, MappeDetails } from "./MappeDetails";
import { AkteAnsicht } from "./AkteAbschnitte";
import { GeburtstagKarte, KreisKarte } from "./KreisKarten";
import { kontakteText, kreisSache } from "./kreis";
import { Sidebar } from "./chrome";
import { navigate } from "./ui";

type ProfileKind = "person" | "project";
type PersonTab = "overview" | "projects" | "conversations" | "documents" | "notes";
type ProjectTab = "overview" | "tasks" | "documents" | "decisions" | "team";

function profileDate(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(value)).replace(".", "");
}

function sourceLabel(value: string) {
  return ({user_stated: "Eigene Angabe", chat: "Gespräch", email: "E-Mail", calendar: "Kalender", document: "Dokument", web: "Webseite", tool_output: "Werkzeugausgabe", inference: "Abgeleitete Angabe", manual_correction: "Eigene Korrektur"} as Record<string, string>)[value] ?? "Weitere Quelle";
}

function noteLabel(value: unknown) {
  return ({meeting: "Besprechungsnotiz", research: "Recherche", idea: "Idee", decision: "Entscheidungsnotiz", reference: "Referenznotiz"} as Record<string, string>)[String(value)] ?? "Notiz";
}

function field(profile: Record<string, unknown>, key: string) {
  const value = profile[key];
  return typeof value === "string" && value ? value : "—";
}

function EmptyProfileSection({ children }: { children: string }) {
  return <p className="profile-empty">{children}</p>;
}

function ClaimList({ claims, history }: { claims: Array<Record<string, unknown>>; history: Array<Record<string, unknown>> }) {
  return <div className="profile-claims">
    {claims.length ? claims.map((claim) => <article key={String(claim.id)}><strong>{String(claim.statement ?? "")}</strong><small>Bestätigter Stand</small><details><summary>Belege ansehen</summary><ClaimEvidence claim={claim} /></details></article>) : <EmptyProfileSection>Noch keine bestätigte Aussage.</EmptyProfileSection>}
    {history.length ? <details><summary>Frühere Stände ({history.length})</summary>{history.map((claim) => <article key={String(claim.id)}><p>{String(claim.statement ?? "")}</p><details><summary>Belege ansehen</summary><ClaimEvidence claim={claim} /></details></article>)}</details> : null}
  </div>;
}

/** Kreis und was ansteht, in jeder Personenakte, auch ohne Adresse und ohne Vorschlag (Fremdprobe 2, Befunde 19 und 20).
 * Mit Adresse stehen beide Karten schon in der Akte (AkteAnsicht); hier nur, wenn es keine solche Akte gibt. */
function PersonKarten({ person }: { person: PersonProfileData["person"] }) {
  const sache = kreisSache(person);
  if (!sache) return null;
  return <section className="profile-card profile-wide mappe"><KreisKarte sache={sache} /><GeburtstagKarte sache={sache} /></section>;
}

function PersonProfile({ data, tab, setTab }: { data: PersonProfileData; tab: PersonTab; setTab: (tab: PersonTab) => void }) {
  const person = data.person;
  const documents = data.interactions.filter(item => item.kind === "document");
  const conversations = data.interactions.filter(item => item.kind !== "document");
  const tabs: Array<[PersonTab, string]> = [["overview", "Übersicht"], ["projects", "Projekte"], ["conversations", "Gespräche"], ["documents", "Dokumente"], ["notes", "Notizen"]];
  return <>
    <header className="profile-heading"><p className="eyebrow">PERSONENPROFIL</p><h1>{person.anzeige ?? displayLabel(person.name).name}</h1>{(person.adressen?.length ?? 0) > 0 ? <p>{person.adressen!.join(", ")}</p> : displayLabel(person.name).detail && <p>{displayLabel(person.name).detail}</p>}{(person.namen?.length ?? 0) > 1 && <p>Auch bekannt als: {person.namen!.slice(1).join(", ")}</p>}{(person.offen_mit?.length ?? 0) > 0 && <p>Nicht eindeutig zuzuordnen: passt zu {person.offen_mit!.join(" oder ")}.</p>}<span>{person.nur_von_aussen ? "Nur aus fremden Quellen bekannt" : kontakteText(person)}</span></header>
    <nav aria-label="Personenprofilbereiche" className="profile-tabs">{tabs.map(([id, label]) => <button aria-pressed={tab === id} className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)} type="button">{label}</button>)}</nav>
    {tab === "overview" ? <div className="profile-grid">
      {(person.adressen ?? []).length ? (person.adressen ?? []).slice(0, 3).map((adresse, index) => <AkteAnsicht key={adresse} sache={`person:a:${adresse.toLowerCase()}`} fallback={index === 0 ? <><PersonKarten person={person} /><MappeDetails kind="person" id={person.verweis ?? person.name} /></> : null} />) : <><PersonKarten person={person} /><MappeDetails kind="person" id={person.verweis ?? person.name} /></>}
      <PersonDigest personId={data.id} />
      <section className="profile-card"><h2>Zusammenfassung</h2><p>{person.kontakt_text ? `Letzter Kontakt ${person.kontakt_text}.` : "Noch kein Kontaktdatum belegt."}</p><p>{person.herkuenfte.length ? `Quellen: ${person.herkuenfte.map(sourceLabel).join(", ")}.` : "Keine Quelle angegeben."}</p></section>
      <section className="profile-card"><h2>Aktuelles</h2><p>{person.offene_aufgaben.length ? `${person.offene_aufgaben.length} offene Aufgabe${person.offene_aufgaben.length === 1 ? "" : "n"} wartet auf Bearbeitung.` : "Keine offene Aufgabe ist dieser Person zugeordnet."}</p></section>
      <section className="profile-metrics"><div><strong>{data.contexts.length}</strong><span>Projekte</span></div><div><strong>{person.themen.length}</strong><span>Themen</span></div><div><strong>{person.kontakte ?? data.interactions.length}</strong><span>Kontakte</span></div><div><strong>{profileDate(person.letzter_kontakt)}</strong><span>Letzter Kontakt</span></div></section>
      <section className="profile-card profile-wide"><h2>Verbindungen</h2>{person.themen.length ? <div className="profile-list">{person.themen.map((topic) => <p key={topic}>{topic}</p>)}</div> : <EmptyProfileSection>Noch keine belegten Themen.</EmptyProfileSection>}</section>
      <section className="profile-card profile-wide"><h2>Bestätigter Wissensstand</h2><ClaimList claims={data.claims} history={data.claim_history} /></section>
    </div> : null}
    {tab === "projects" ? <section className="profile-card profile-list-card"><h2>Projekte</h2>{data.contexts.length ? data.contexts.map((context) => <article key={String(context.project.id)}><a href={`/memory/projects/${encodeURIComponent(String(context.project.id))}`}><strong>{field(context.project, "name")}</strong></a><small>Letzter Kontakt {profileDate(context.last_interaction)} · {context.evidence_refs.length} {context.evidence_refs.length === 1 ? "Beleg" : "Belege"}</small></article>) : <EmptyProfileSection>Noch keine belegten Projekte.</EmptyProfileSection>}</section> : null}
    {tab === "conversations" ? <section className="profile-card"><h2>Gespräche</h2><Chronik eintraege={conversations} leer="Noch keine belegten Gespräche." quelle={sourceLabel} /></section> : null}
    {tab === "documents" ? <section className="profile-card"><h2>Dokumente</h2><Chronik eintraege={documents} leer="Noch keine zugeordneten Dokumente." quelle={sourceLabel} /></section> : null}
    {tab === "notes" ? <section className="profile-card profile-list-card"><h2>Notizen</h2><EmptyProfileSection>Notizen werden angezeigt, sobald sie dieser Person ausdrücklich zugeordnet sind.</EmptyProfileSection></section> : null}
  </>;
}

function ProjectProfile({ data, tab, setTab }: { data: ProjectProfileData; tab: ProjectTab; setTab: (tab: ProjectTab) => void }) {
  const project = data.project;
  const status = ({idea: "Idee", active: "In Arbeit", paused: "Pausiert", done: "Abgeschlossen", dropped: "Beendet"} as Record<string, string>)[field(project, "status")] ?? field(project, "status");
  const priority = ({high: "Hoch", medium: "Mittel", low: "Niedrig"} as Record<string, string>)[field(project, "priority")] ?? field(project, "priority");
  const tabs: Array<[ProjectTab, string]> = [["overview", "Übersicht"], ["tasks", "Aufgaben"], ["documents", "Dokumente"], ["decisions", "Entscheidungen"], ["team", "Team"]];
  return <>
    <header className="profile-heading"><p className="eyebrow">PROJEKTPROFIL</p><h1>{field(project, "name")}</h1><span>{status} · {field(project, "area")}</span></header>
    <nav aria-label="Projektprofilbereiche" className="profile-tabs">{tabs.map(([id, label]) => <button aria-pressed={tab === id} className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)} type="button">{label}</button>)}</nav>
    {tab === "overview" ? <div className="profile-grid">
      <section className="profile-card"><h2>Ziel</h2><p>{field(project, "description")}</p></section>
      <section className="profile-card"><h2>Status</h2><p>{status}</p><small>Priorität: {priority}</small></section>
      <AkteAnsicht sache={`projekt:${String(project.id)}`} fallback={<MappeDetails kind="project" id={String(project.id)} />} />
      <section className="profile-metrics"><div><strong>{data.tasks.filter((task) => task.status !== "done").length}</strong><span>Offene Aufgaben</span></div><div><strong>{data.people.length}</strong><span>Team</span></div><div><strong>{data.episodes.length}</strong><span>Belege</span></div><div><strong>{data.notes.length}</strong><span>Notizen</span></div></section>
      <section className="profile-card profile-wide"><h2>Bestätigter Wissensstand</h2><ClaimList claims={data.claims} history={data.claim_history} /></section>
    </div> : null}
    {tab === "tasks" ? <section className="profile-card profile-list-card"><h2>Aufgaben</h2>{data.tasks.length ? data.tasks.map((task: Task) => <article key={task.id}><a href={`/vorhaben?view=${task.status === "done" ? "done" : task.wartet_auf ? "waiting" : "mine"}&project=${encodeURIComponent(String(project.id))}`}><strong>{task.title}</strong></a><small>{task.status === "done" ? "Erledigt" : task.due ? `Fällig ${profileDate(task.due)}` : "Ohne Termin"}</small>{task.provenance?.source_ref?.startsWith("episode:") && <TaskSource taskId={task.id} />}</article>) : <EmptyProfileSection>Noch keine Aufgaben in diesem Projekt.</EmptyProfileSection>}</section> : null}
    {tab === "documents" && data.notes.length ? <section className="profile-card profile-list-card"><h2>Notizen</h2>{data.notes.map((note) => <article key={String(note.id)}><strong>{String(note.title ?? "")}</strong><small>Revision {String(note.revision ?? "—")} · {noteLabel(note.kind)}</small><ProfileSource kind="note" id={String(note.id)} /></article>)}</section> : null}
    {tab === "documents" ? <section className="profile-card profile-wide"><h2>Chronik</h2><Chronik eintraege={data.episodes} leer={data.notes.length ? "Noch keine Quellen in diesem Projekt." : "Noch keine Dokumente oder Quellen in diesem Projekt."} quelle={sourceLabel} /></section> : null}
    {tab === "decisions" ? <section className="profile-card profile-list-card"><DecisionControls key={String(project.id)} projectId={String(project.id)} /></section> : null}
    {tab === "team" ? <section className="profile-card profile-list-card"><h2>Team</h2>{data.people.length ? data.people.map((person) => <article key={`${person.identity_resolution}:${person.id}`}><a href={person.identity_resolution === "explicit_registry" ? `/memory/registry/${encodeURIComponent(person.id)}` : `/memory/people/${encodeURIComponent(person.name)}`}><strong>{person.name}</strong></a><small>{person.identity_resolution === "explicit_registry" ? "Bestätigter Projektbezug" : `Quellenkontakt · Letzter Kontakt ${profileDate(person.last_interaction)}`} · {person.evidence_refs.length} {person.evidence_refs.length === 1 ? "Beleg" : "Belege"}</small></article>) : <EmptyProfileSection>Noch keine belegten Personen im Projekt.</EmptyProfileSection>}</section> : null}
  </>;
}

export function MemoryProfile({ kind, identifier, recentConversation }: { kind: ProfileKind; identifier: string; recentConversation: string | null }) {
  const [data, setData] = useState<PersonProfileData | ProjectProfileData | null>(null);
  const [error, setError] = useState(false);
  const [personTab, setPersonTab] = useState<PersonTab>("overview");
  const [projectTab, setProjectTab] = useState<ProjectTab>("overview");

  useEffect(() => {
    let active = true;
    setData(null);
    setError(false);
    const load = kind === "person" ? api.personProfile(identifier) : api.projectProfile(identifier);
    load.then((result) => active && setData(result)).catch(() => active && setError(true));
    return () => { active = false; };
  }, [kind, identifier]);

  const title = useMemo(() => kind === "person" ? "Personenprofil" : "Projektprofil", [kind]);
  return <div className="shell profile-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="profile-page">
      <button className="profile-back" onClick={() => navigate("/memory")} type="button">← Gedächtnis</button>
      {error ? <section className="profile-state"><h1>{title}</h1><p>Dieses Profil ist gerade nicht erreichbar oder nicht belegt.</p><button onClick={() => window.location.reload()} type="button">Wiederholen</button></section> : null}
      {!error && !data ? <section className="profile-state profile-loading" aria-label={`${title} wird geladen`}><i /><i /><i /></section> : null}
      {data && kind === "person" ? <PersonProfile data={data as PersonProfileData} setTab={setPersonTab} tab={personTab} /> : null}
      {data && kind === "project" ? <ProjectProfile data={data as ProjectProfileData} setTab={setProjectTab} tab={projectTab} /> : null}
    </main>
  </div>;
}


export function RegistryProfile({ identifier, recentConversation }: { identifier: string; recentConversation: string | null }) {
  const [data, setData] = useState<RegistryProfileData | null>(null);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setData(null);
    setError(false);
    api.registryProfile(identifier).then((result) => { if (active) setData(result); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [identifier, revision]);
  return <div className="shell profile-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="profile-page">
      <button className="profile-back" onClick={() => navigate("/memory")} type="button">← Gedächtnis</button>
      {error ? <section className="profile-state"><h1>Profil</h1><p>Dieses Profil ist gerade nicht erreichbar oder nicht belegt.</p><button onClick={() => window.location.reload()} type="button">Wiederholen</button></section> : null}
      {!error && !data ? <section className="profile-state profile-loading" aria-label="Profil wird geladen"><i /><i /><i /></section> : null}
      {data ? <>
        <header className="profile-heading"><p className="eyebrow">{({person: "PERSONENPROFIL", project: "PROJEKTPROFIL", organization: "ORGANISATION", topic: "THEMA", place: "ORT", document: "DOKUMENT"} as Record<string, string>)[data.entity.kind] || "PROFIL"}</p><h1>{data.entity.label}</h1><span>Ausdrücklich zugeordneter Wissensstand</span></header>
        {data.entity.kind === "person" ? <PersonDigest personId={data.entity.id} /> : null}
        <section className="profile-card"><h2>Bestätigte Beziehungen und Aussagen</h2><ClaimControls entities={data.related_entities ?? {}} claims={data.claims} history={data.claim_history} onChanged={() => setRevision(value => value + 1)} /></section>
        <IdentityControls key={identifier} data={data} onChanged={() => setRevision(value => value + 1)} />
      </> : null}
    </main>
  </div>;
}
