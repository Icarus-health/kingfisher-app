import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { ApiError, api, type Akte, type AkteLage, type AkteZeile } from "./api";
import { displayLabel } from "./displayIdentity";
import { ArtKarte, GeburtstagKarte, KreisKarte } from "./Kreis";
import { WiederkehrendKarte } from "./Wiederkehrendes";
import { ProfileSource } from "./ProfileSource";
import { Sidebar } from "./chrome";
import { navigate } from "./ui";
import "./AkteAbschnitte.css";

const TAG = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric" });
const TAG_ZEIT = new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

const ERSTELLT = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit", hour12: false });

function tag(value: string | null | undefined) {
  if (!value) return "";
  // Ein reines Datum („2026-11-12“) ist ein Kalendertag, keine Uhrzeit in UTC.
  const zeit = /^\d{4}-\d{2}-\d{2}$/.test(value) ? new Date(`${value}T12:00:00`) : new Date(value);
  return Number.isNaN(zeit.getTime()) ? "" : TAG.format(zeit);
}

function datum(zeile: AkteZeile) {
  return zeile.occurred_at ? tag(zeile.occurred_at) : `erfasst ${tag(zeile.recorded_at)}`;
}

function Quelle({ zeile }: { zeile: { episode_id: string; titel: string } }) {
  return <ProfileSource kind="episode" id={zeile.episode_id} label={zeile.titel ? `Quelle: ${zeile.titel}` : "Quelle öffnen"} quiet />;
}

function Zeile({ zeile, zusatz }: { zeile: AkteZeile; zusatz?: ReactNode }) {
  return <article>
    <small>{zeile.art} · {datum(zeile)}{zeile.participants.length ? ` · ${displayLabel(zeile.participants[0]).name}` : ""}{zusatz ? ` · ${zusatz}` : ""}</small>
    <blockquote>{zeile.text}</blockquote>
    <Quelle zeile={zeile} />
  </article>;
}

const GRUND: Record<string, string> = { erledigt: "Später als erledigt gemeldet", absage: "Später abgesagt", aufgabe_erledigt: "Aufgabe erledigt", aufgabe_verworfen: "Aufgabe fallengelassen" };
const GRUNDLAGE: Record<string, string> = { anker: "Adresse oder Zuordnung", modell: "Im Text erkannt", nutzer: "Von dir" };

function Teil({ titel, kind, children }: { titel: string; kind?: string; children: ReactNode }) {
  return <section className={`mappe-teil akte-teil${kind ? ` akte-${kind}` : ""}`}><h3>{titel}</h3>{children}</section>;
}

function Gesamt({ gezeigt, gesamt, wo }: { gezeigt: number; gesamt: number; wo?: string }) {
  // Keine stille Grenze: Was nicht gezeigt wird, wird gezählt.
  return gesamt > gezeigt ? <p className="mappe-mehr">{gezeigt} von {gesamt}{wo ? ` · ${wo}` : ""}</p> : null;
}

/** Die Lage (Ebene 3): das Wichtigste in zwei, drei Sätzen. Jeder Satz nennt seine Quellen; ein Klick öffnet das Original. */
function Lage({ lage }: { lage: AkteLage }) {
  const erstellt = new Date(lage.erstellt_am);
  return <section className="mappe-teil akte-teil akte-lage" aria-label="Lage">
    <h3>Lage</h3>
    <ol>
      {lage.saetze.map((satz, index) => <li key={index}>
        <p>{satz.text}</p>
        <div className="akte-belege"><small>Belege</small>
          {satz.belege.map(b => <ProfileSource key={`${b.nummer}:${b.episode_id}`} kind="episode" id={b.episode_id} label={b.titel || "Quelle öffnen"} quiet />)}
        </div>
      </li>)}
    </ol>
    <p className="mappe-hinweis">
      {lage.veraltet ? "Stand vom" : "Erstellt"} {Number.isNaN(erstellt.getTime()) ? "" : `${lage.veraltet ? "" : "am "}${ERSTELLT.format(erstellt)} `}· aus {lage.quellen === 1 ? "einer Quelle" : `${lage.quellen} Quellen`}
      {" "}· von einem lokalen Modell geschrieben, Satz für Satz gegen die Quellen geprüft{lage.verworfen ? ` (${lage.verworfen === 1 ? "ein Satz" : `${lage.verworfen} Sätze`} ohne ausreichenden Beleg verworfen)` : ""}.
    </p>
    {lage.wird_aktualisiert ? <p className="mappe-hinweis akte-lage-alt" role="status">Die Akte hat sich seitdem geändert. Die Lage wird aktualisiert; bis dahin stehen hier nur Sätze, die eine neuere Meldung nicht überholt haben.</p> : null}
  </section>;
}

/** Die Akte einer Sache (Ebene 2): Stand, Offen, Fristen, Termine, Beteiligte, Verlauf. Jede Zeile führt zur Quelle. */
export function AkteAnsicht({ sache, fallback, mitKopf = false }: { sache: string; fallback?: ReactNode | null; mitKopf?: boolean }) {
  const [data, setData] = useState<Akte | null>(null);
  const [zustand, setZustand] = useState<"laedt" | "keine" | "fehler" | "ok">("laedt");
  const [alle, setAlle] = useState(false);
  const version = useRef(0);
  const versuche = useRef(0);
  const lageVersuche = useRef(0);
  const laden = useCallback(async (mitAllen: boolean) => {
    const eigene = ++version.current;
    try {
      const next = await api.akte(sache, mitAllen);
      // Eine verspätete Antwort für eine andere Sache überschreibt nichts.
      if (eigene === version.current) { setData(next); setZustand("ok"); }
    } catch (cause) {
      if (eigene === version.current) setZustand(cause instanceof ApiError && cause.status === 404 ? "keine" : "fehler");
    }
  }, [sache]);
  useEffect(() => { setData(null); setZustand("laedt"); setAlle(false); versuche.current = 0; lageVersuche.current = 0; void laden(false); }, [laden]);
  // Sind die Bezüge noch nicht fertig berechnet, still nachladen (höchstens sechsmal).
  const offen = data?.berechnung.offen ?? 0;
  useEffect(() => {
    if ((zustand !== "keine" && offen === 0) || versuche.current >= 6) return;
    versuche.current += 1;
    const timer = window.setTimeout(() => void laden(alle), 3000);
    return () => window.clearTimeout(timer);
  }, [zustand, offen, laden, alle, data]);

  // Eine veraltete Lage wird im Hintergrund neu geschrieben (das dauert): gelegentlich still nachsehen, höchstens sechsmal.
  const lageAlt = (data?.lage?.wird_aktualisiert ?? false) || (data?.lage_wird_aktualisiert ?? false);
  useEffect(() => {
    if (!lageAlt || lageVersuche.current >= 6) return;
    lageVersuche.current += 1;
    const timer = window.setTimeout(() => void laden(alle), 20000);
    return () => window.clearTimeout(timer);
  }, [lageAlt, laden, alle, data]);

  if (zustand === "keine") return fallback !== undefined ? <>{fallback}</> : <section className="profile-card profile-wide mappe"><h2>Akte</h2><p className="profile-empty">Zu dieser Sache gibt es (noch) keine Quellen.</p></section>;
  if (zustand === "fehler") return <section className="profile-card profile-wide mappe" role="status"><h2>Akte</h2><p className="profile-empty">Die Akte konnte gerade nicht geladen werden.</p><button className="chronik-mehr" onClick={() => void laden(alle)} type="button">Erneut laden</button></section>;
  if (!data) return <section className="profile-card profile-wide mappe" aria-busy="true"><h2>Akte</h2><p className="profile-empty">Wird zusammengestellt …</p></section>;

  const zeigeAlle = () => { setAlle(true); void laden(true); };
  const f = data.fristen;
  const stand = data.stand_der_dinge;
  return <section className="profile-card profile-wide mappe akte">
    <h2>{mitKopf ? data.name : "Akte"}</h2>
    <p className="mappe-hinweis">
      {mitKopf ? `${data.art_text} · ` : ""}Aus {data.quellen.gesamt === 1 ? "einer Quelle" : `${data.quellen.gesamt} Quellen`} zusammengestellt. Jede Zeile führt zur Quelle.
      {data.quellen.begrenzt ? ` Ausgewertet sind die jüngsten ${data.quellen.beruecksichtigt}.` : ""}
      {data.berechnung.offen ? ` Für ${data.berechnung.offen} weitere Quellen wird noch berechnet, wozu sie gehören.` : ""}
    </p>

    {data.art === "person" ? <KreisKarte sache={data.sache} /> : null}
    {data.art === "person" ? <GeburtstagKarte sache={data.sache} /> : null}
    {data.art === "organisation" ? <ArtKarte sache={data.sache} /> : null}
    {data.art === "person" || data.art === "organisation" || data.art === "thema" ? <WiederkehrendKarte sache={data.sache} /> : null}

    {data.lage ? <Lage lage={data.lage} /> : null}

    {data.aussagen?.eintraege.length ? <Teil titel="Angenommen" kind="angenommen">
      <p className="mappe-hinweis">Aussagen, die du aus einer Antwort übernommen und bestätigt hast. Jede nennt ihren Beleg; ändert eine jüngere Quelle den Gegenstand, steht es dabei.</p>
      {data.aussagen.eintraege.map(a => <article key={a.id} className={a.ueberholt ? "akte-aussage-ueberholt" : undefined}>
        <strong>{a.text}</strong>
        <small>Angenommen am {tag(a.angenommen)}</small>
        {a.ueberholt ? <p className="akte-ueberholt-hinweis" role="note">Möglicherweise überholt: „{a.ueberholt.text}“ ({tag(a.ueberholt.datum)}). Die Aussage gilt weiter, bis du sie widerrufst. <Quelle zeile={a.ueberholt} /></p> : null}
        {a.belege.map(b => <div key={b.episode_id}><blockquote>{b.zitat}</blockquote><Quelle zeile={b} /></div>)}
      </article>)}
      <Gesamt gezeigt={data.aussagen.eintraege.length} gesamt={data.aussagen.gesamt} />
    </Teil> : null}

    {stand.aktuell ? <Teil titel="Stand" kind="stand">
      <Zeile zeile={stand.aktuell} />
      {stand.vorher.length ? <details><summary>Vorher ({stand.vorher_gesamt})</summary>{stand.vorher.map((z, index) => <Zeile key={`${index}:${z.episode_id}`} zeile={z} />)}</details> : null}
      {stand.weitere.length ? <details><summary>Weitere Stände ({stand.weitere_gesamt})</summary>{stand.weitere.map((g, index) => <Zeile key={`${index}:${g.aktuell.episode_id}`} zeile={g.aktuell} zusatz={g.vorher_gesamt ? `vorher ${g.vorher_gesamt}×` : undefined} />)}</details> : null}
    </Teil> : null}

    {data.offen.eintraege.length || data.offen.erledigt.gesamt ? <Teil titel="Vermutlich offen" kind="offen">
      {data.offen.eintraege.length ? <p className="mappe-hinweis">Keine spätere Erledigung oder Absage gefunden. Ob es wirklich offen ist, steht in den Quellen nicht.</p> : <p className="profile-empty">Nichts mehr offen, soweit die Quellen es zeigen.</p>}
      {data.offen.eintraege.map((e, index) => <Zeile key={`${index}:${e.episode_id}`} zeile={e} zusatz={e.aufgabe ? `Aufgabe: ${e.aufgabe.title}` : undefined} />)}
      {data.offen.eintraege.map((e, index) => e.danach_geaendert ? <p className="mappe-mehr" key={`d${index}`}>Danach geändert: „{e.danach_geaendert.text}“ ({datum(e.danach_geaendert)})</p> : null)}
      <Gesamt gezeigt={data.offen.eintraege.length} gesamt={data.offen.gesamt} />
      {data.offen.erledigt.gesamt ? <details><summary>Vermutlich erledigt oder abgesagt ({data.offen.erledigt.gesamt})</summary>
        {data.offen.erledigt.eintraege.map((e, index) => <div key={`${index}:${e.episode_id}`}><Zeile zeile={e} zusatz={GRUND[e.grund] ?? e.grund} />{e.durch ? <p className="mappe-mehr">Laut: „{e.durch.text}“ ({datum(e.durch)}) <Quelle zeile={e.durch} /></p> : null}</div>)}
      </details> : null}
    </Teil> : null}

    {f.kommend.length || f.verstrichen.length || f.ersetzt.length || f.ohne_datum.gesamt ? <Teil titel="Fristen" kind="fristen">
      {f.kommend.map((e, index) => <article key={`k${index}:${e.episode_id}:${e.datum}`}>
        <strong>{tag(e.datum)}</strong>
        <small>{e.ausdruck ? `„${e.ausdruck}“ · ` : ""}{e.art} vom {datum(e)}</small>
        <blockquote>{e.text}</blockquote><Quelle zeile={e} />
      </article>)}
      <Gesamt gezeigt={f.kommend.length} gesamt={f.gesamt.kommend} wo="kommende Fristen" />
      {f.verstrichen.length ? <details><summary>Verstrichen ({f.gesamt.verstrichen})</summary>{f.verstrichen.map((e, index) => <article key={`v${index}:${e.episode_id}:${e.datum}`}>
        <strong>{tag(e.datum)}</strong><small>{e.ausdruck ? `„${e.ausdruck}“ · ` : ""}{e.art} vom {datum(e)}</small><blockquote>{e.text}</blockquote><Quelle zeile={e} /></article>)}</details> : null}
      {f.ersetzt.length ? <details><summary>Überholt ({f.gesamt.ersetzt})</summary>{f.ersetzt.map((e, index) => <article key={`e${index}:${e.episode_id}:${e.datum}`}>
        <strong className="akte-alt">{tag(e.datum)}</strong><small>ersetzt durch {tag(e.ersetzt_durch?.datum)}{e.ersetzt_durch?.ausdruck ? ` („${e.ersetzt_durch.ausdruck}“)` : ""}</small><blockquote>{e.text}</blockquote><Quelle zeile={e} /></article>)}</details> : null}
      {f.ohne_datum.gesamt ? <p className="mappe-mehr">Zeitangaben ohne festes Datum ({f.ohne_datum.gesamt}): {f.ohne_datum.eintraege.map(x => `„${x.ausdruck}“`).join(", ")}{f.ohne_datum.gesamt > f.ohne_datum.eintraege.length ? " …" : ""}</p> : null}
    </Teil> : null}

    {data.termine.kommend.length || data.termine.vergangen.length ? <Teil titel="Termine" kind="termine">
      {data.termine.kommend.map(t => <article key={`k:${t.episode_id}`}><strong>{t.titel}</strong><small>{TAG_ZEIT.format(new Date(t.start))}{t.ort ? ` · ${t.ort}` : ""}</small>{t.vermutlich_abgesagt ? <p className="mappe-mehr">Vermutlich abgesagt laut „{t.vermutlich_abgesagt.text}“ ({datum(t.vermutlich_abgesagt)}). Der Kalendereintrag steht noch. <Quelle zeile={t.vermutlich_abgesagt} /></p> : null}<Quelle zeile={t} /></article>)}
      <Gesamt gezeigt={data.termine.kommend.length} gesamt={data.termine.gesamt.kommend} wo="kommende Termine" />
      {data.termine.vergangen.length ? <details><summary>Vergangen ({data.termine.gesamt.vergangen})</summary>{data.termine.vergangen.map(t => <article key={`v:${t.episode_id}`}><strong>{t.titel}</strong><small>{TAG_ZEIT.format(new Date(t.start))}{t.ort ? ` · ${t.ort}` : ""}{t.vermutlich_abgesagt ? " · vermutlich abgesagt" : ""}</small><Quelle zeile={t} /></article>)}</details> : null}
    </Teil> : null}

    {data.aufgaben.eintraege.length ? <Teil titel="Aufgaben" kind="aufgaben">
      {data.aufgaben.eintraege.map(a => <article key={a.id}><strong>{a.title}</strong><small className={a.overdue ? "mappe-ueberfaellig" : undefined}>{a.due ? `${a.overdue ? "Überfällig seit" : "Fällig"} ${tag(a.due)}` : "Ohne Termin"}{a.wartet_auf ? ` · wartet auf ${displayLabel(a.wartet_auf).name}` : ""}</small></article>)}
      <Gesamt gezeigt={data.aufgaben.eintraege.length} gesamt={data.aufgaben.gesamt} />
    </Teil> : null}

    {data.beteiligte.eintraege.length ? <Teil titel="Beteiligte" kind="beteiligte">
      <ul className="akte-beteiligte">{data.beteiligte.eintraege.map(b => <li key={b.sache}>
        <button type="button" onClick={() => navigate(`/memory/akte/${encodeURIComponent(b.sache)}`)} aria-label={`Akte öffnen: ${b.name}`}>{displayLabel(b.name).name}<small>{b.art === "person" ? "Person" : b.art === "organisation" ? "Organisation" : b.art === "projekt" ? "Projekt" : b.art === "ort" ? "Ort" : "Thema"} · {b.anzahl}×</small></button>
      </li>)}</ul>
      <Gesamt gezeigt={data.beteiligte.eintraege.length} gesamt={data.beteiligte.gesamt} wo="häufigste zuerst" />
    </Teil> : null}

    <Teil titel="Verlauf" kind="verlauf">
      {data.verlauf.eintraege.map((e, index) => <article key={`${index}:${e.episode_id}`}>
        <small>{tag(e.datum)}{e.art ? ` · ${e.art}` : ""}{e.archiviert ? " · verdichteter Monat" : ""} · {e.grundlagen.map(g => GRUNDLAGE[g] ?? g).join(", ")}</small>
        <strong>{e.titel}</strong>
        {e.text ? <blockquote>{e.text}</blockquote> : null}
        <Quelle zeile={e} />
      </article>)}
      <Gesamt gezeigt={data.verlauf.eintraege.length} gesamt={data.verlauf.gesamt} />
      {!alle && data.verlauf.gesamt > data.verlauf.eintraege.length ? <button className="chronik-mehr" onClick={zeigeAlle} type="button">Alle zeigen</button> : null}
    </Teil>
    {data.einordnung.offen ? <p className="mappe-mehr">{data.einordnung.offen === 1 ? "Eine Quelle wird noch sortiert und ist" : `${data.einordnung.offen} Quellen werden noch sortiert und sind`} hier nur mit Titel berücksichtigt.</p> : null}
  </section>;
}

/** Eigene Seite für die Akte irgendeiner Sache, erreichbar aus den Listen im Gedächtnis und aus „Beteiligte“. */
export function SachenAkte({ sache, recentConversation }: { sache: string; recentConversation: string | null }) {
  return <div className="shell profile-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="profile-page">
      <button className="profile-back" onClick={() => navigate("/memory")} type="button">← Gedächtnis</button>
      <AkteAnsicht key={sache} sache={sache} mitKopf />
    </main>
  </div>;
}
