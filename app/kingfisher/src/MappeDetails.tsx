import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type MappeEinzelheiten, type MappeListe, type MappeZitat } from "./api";
import { displayLabel } from "./displayIdentity";
import { ProfileSource } from "./ProfileSource";
import "./MappeDetails.css";

function zeitpunkt(value: string | null | undefined) {
  if (!value) return null;
  const time = Date.parse(value);
  return Number.isNaN(time) ? null : new Date(time);
}

function tag(value: string | null | undefined) {
  const date = zeitpunkt(value);
  return date ? new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric" }).format(date) : "";
}

function termin(value: string, ganztags?: boolean) {
  const date = zeitpunkt(value);
  if (!date) return value;
  // Ganztägiges hat keine Uhrzeit; sonst stünde 02:00 da.
  if (ganztags) return `${new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "numeric", timeZone: "UTC" }).format(date)} · ganztägig`;
  return new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }).format(date);
}

function Mehr({ liste, alle, onAlle, wo }: { liste: MappeListe<unknown>; alle: boolean; onAlle: () => void; wo?: string }) {
  // Keine stille Grenze: Was nicht gezeigt wird, wird gezählt.
  const archiv = liste.archiviert ? <p className="mappe-mehr">{liste.archiviert === 1 ? "Ein Eintrag stammt aus verdichteten Monaten und wird" : `${liste.archiviert} Einträge stammen aus verdichteten Monaten und werden`} hier nicht aufgeführt.</p> : null;
  if (liste.gesamt <= liste.eintraege.length) return archiv;
  const zahl = `${liste.eintraege.length} von ${liste.ungefaehr ? "bis zu " : ""}${liste.gesamt}`;
  return <>
    <p className="mappe-mehr">{zahl}{wo ? ` · ${wo}` : ""}</p>
    {!alle && !wo ? <button className="chronik-mehr" onClick={onAlle} type="button">Alle zeigen</button> : null}
    {archiv}
  </>;
}

function Zitate({ titel, liste, alle, onAlle }: { titel: string; liste: MappeListe<MappeZitat>; alle: boolean; onAlle: () => void }) {
  if (!liste.eintraege.length) return liste.archiviert || liste.gesamt ? <section className="mappe-teil"><h3>{titel}</h3>{liste.gesamt ? <p className="mappe-mehr">Bis zu {liste.gesamt} Einträge sind noch nicht geprüft.</p> : null}<Mehr liste={{ ...liste, gesamt: 0 }} alle={alle} onAlle={onAlle} /></section> : null;
  return <section className="mappe-teil"><h3>{titel}</h3>
    {liste.eintraege.map((eintrag, index) => <article key={`${index}:${eintrag.episode_id}`}>
      <small>{eintrag.art} · {eintrag.occurred_at ? tag(eintrag.occurred_at) : `erfasst ${tag(eintrag.recorded_at)}`}{eintrag.participants.length ? ` · ${displayLabel(eintrag.participants[0]).name}` : ""}</small>
      <blockquote>{eintrag.text}</blockquote>
      <ProfileSource kind="episode" id={eintrag.episode_id} label={eintrag.titel ? `Quelle: ${eintrag.titel}` : "Quelle öffnen"} quiet />
    </article>)}
    <Mehr liste={liste} alle={alle} onAlle={onAlle} />
  </section>;
}

export function MappeDetails({ kind, id }: { kind: "project" | "person"; id: string }) {
  const [data, setData] = useState<MappeEinzelheiten | null>(null);
  const [fehler, setFehler] = useState<"" | "weg" | "netz">("");
  const [alle, setAlle] = useState(false);
  const version = useRef(0);
  const nochmal = useRef(false);
  const load = useCallback(async (mitAllen: boolean) => {
    const eigene = ++version.current;
    setFehler("");
    try {
      const next = await (kind === "project" ? api.projectDetails(id, mitAllen) : api.personDetails(id, mitAllen));
      // Eine verspätete Antwort für eine andere Mappe überschreibt nichts.
      if (eigene === version.current) setData(next);
    } catch (cause) {
      if (eigene === version.current) setFehler(cause instanceof ApiError && cause.status === 404 ? "weg" : "netz");
    }
  }, [kind, id]);
  useEffect(() => { setData(null); setAlle(false); nochmal.current = false; void load(false); }, [load]);
  // Hat der Kalender nicht rechtzeitig geantwortet, einmal still nachladen:
  // Der Abruf läuft im Hintergrund weiter und steht dann bereit.
  useEffect(() => {
    if (data?.termine.kalender !== "nicht_erreichbar" || nochmal.current) return;
    nochmal.current = true;
    const timer = window.setTimeout(() => void load(alle), 4000);
    return () => window.clearTimeout(timer);
  }, [data, load, alle]);
  const zeigeAlle = () => { setAlle(true); void load(true); };

  const titel = <h2>Stand der Dinge</h2>;
  if (fehler === "weg") return <section className="profile-card profile-wide mappe" role="status">{titel}<p className="profile-empty">Zu dieser Mappe gibt es keine geltenden Quellen mehr, etwa weil sie ignoriert oder berichtigt wurden.</p></section>;
  if (fehler) return <section className="profile-card profile-wide mappe" role="status">{titel}<p className="profile-empty">Der Stand konnte gerade nicht geladen werden.</p><button className="chronik-mehr" onClick={() => void load(alle)} type="button">Erneut laden</button></section>;
  if (!data) return <section className="profile-card profile-wide mappe" aria-busy="true">{titel}<p className="profile-empty">Wird zusammengestellt …</p></section>;
  const leer = !data.bitten_und_zusagen.eintraege.length && !data.entwicklungen.eintraege.length
    && !data.angaben.eintraege.length && !data.aufgaben.eintraege.length && !data.termine.eintraege.length;
  return <section className="profile-card profile-wide mappe">
    {titel}
    <p className="mappe-hinweis">Aus den sortierten Quellen zusammengestellt, ohne neuen Modellaufruf. {kind === "person" ? "Berücksichtigt sind Quellen, an denen diese Person beteiligt ist. " : ""}Ob eine Bitte inzwischen erledigt ist, steht in der Quelle nicht; das Datum hilft beim Einschätzen.</p>
    {leer && !data.bitten_und_zusagen.archiviert && !data.entwicklungen.archiviert ? <p className="profile-empty">In den Quellen noch keine Bitten, Zusagen, Angaben, Aufgaben oder Termine.</p> : null}
    {data.aufgaben.eintraege.length ? <section className="mappe-teil"><h3>Aufgaben</h3>
      {data.aufgaben.eintraege.map(aufgabe => <article key={aufgabe.id}>
        <strong>{aufgabe.title}</strong>
        <small className={aufgabe.overdue ? "mappe-ueberfaellig" : undefined}>{aufgabe.due ? `${aufgabe.overdue ? "Überfällig seit" : "Fällig"} ${tag(aufgabe.due)}` : "Ohne Termin"}{aufgabe.wartet_auf ? ` · wartet auf ${displayLabel(aufgabe.wartet_auf).name}` : ""}</small>
      </article>)}
      <Mehr liste={data.aufgaben} alle={alle} onAlle={zeigeAlle} />
    </section> : null}
    {data.termine.eintraege.length ? <section className="mappe-teil"><h3>Nächste Termine</h3>
      {data.termine.eintraege.map((eintrag, index) => <article key={`${index}:${eintrag.uid ?? ""}`}><strong>{eintrag.titel}</strong><small>{termin(eintrag.start, eintrag.ganztags)}{eintrag.ort ? ` · ${eintrag.ort}` : ""}</small></article>)}
      <Mehr liste={data.termine} alle={alle} onAlle={zeigeAlle} />
    </section> : null}
    {data.termine.kalender === "nicht_erreichbar" ? <p className="mappe-mehr" role="status">Der Kalender hat gerade nicht rechtzeitig geantwortet; Termine fehlen hier noch.</p> : null}
    <Zitate titel="Bitten und Zusagen" liste={data.bitten_und_zusagen} alle={alle} onAlle={zeigeAlle} />
    <Zitate titel="Letzte Entwicklungen" liste={data.entwicklungen} alle={alle} onAlle={zeigeAlle} />
    <Zitate titel="Neueste Angaben" liste={data.angaben} alle={alle} onAlle={zeigeAlle} />
    {data.einordnung.offen ? <p className="mappe-mehr">{data.einordnung.offen === 1 ? "Eine Quelle wird noch sortiert und ist" : `${data.einordnung.offen} Quellen werden noch sortiert und sind`} hier noch nicht berücksichtigt.</p> : null}
    {data.einordnung.ausgeschlossen ? <p className="mappe-mehr">{data.einordnung.ausgeschlossen === 1 ? "Eine Quelle wird" : `${data.einordnung.ausgeschlossen} Quellen werden`} nicht sortiert (zu groß oder von dir ausgenommen).</p> : null}
  </section>;
}

type ChronikEintrag = { id: string; title: string; occurred_at: string | null; recorded_at?: string; source_type?: string };

const SEITE = 50;

function moment(eintrag: ChronikEintrag) {
  return zeitpunkt(eintrag.occurred_at) ?? zeitpunkt(eintrag.recorded_at);
}

export function Chronik({ eintraege, leer, quelle }: { eintraege: ChronikEintrag[]; leer: string; quelle: (value: string) => string }) {
  const [sichtbar, setSichtbar] = useState(SEITE);
  if (!eintraege.length) return <p className="profile-empty">{leer}</p>;
  // Nach Zeitpunkt, nicht nach Zeichenkette: Versätze können verschieden sein.
  const geordnet = [...eintraege].sort((a, b) => (moment(b)?.getTime() ?? -Infinity) - (moment(a)?.getTime() ?? -Infinity));
  const gruppen: Array<[string, ChronikEintrag[]]> = [];
  for (const eintrag of geordnet.slice(0, sichtbar)) {
    const zeit = moment(eintrag);
    const monat = zeit ? new Intl.DateTimeFormat("de-DE", { month: "long", year: "numeric" }).format(zeit) : "Ohne Datum";
    const letzte = gruppen[gruppen.length - 1];
    if (letzte && letzte[0] === monat) letzte[1].push(eintrag); else gruppen.push([monat, [eintrag]]);
  }
  const rest = geordnet.length - Math.min(sichtbar, geordnet.length);
  return <div className="chronik">
    {gruppen.map(([monat, liste], index) => <section key={`${index}:${monat}`}><h3>{monat}</h3>
      {liste.map(eintrag => <article key={eintrag.id}><strong>{eintrag.title}</strong><small>{zeitpunkt(eintrag.occurred_at) ? tag(eintrag.occurred_at) : `erfasst ${tag(eintrag.recorded_at)}`}{eintrag.source_type ? ` · ${quelle(eintrag.source_type)}` : ""}</small><ProfileSource kind="episode" id={eintrag.id} /></article>)}
    </section>)}
    {rest > 0 ? <button className="chronik-mehr" onClick={() => setSichtbar(value => value + SEITE)} type="button">Weitere {Math.min(SEITE, rest)} anzeigen (noch {rest})</button> : null}
  </div>;
}
