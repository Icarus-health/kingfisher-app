import { GedaechtnisLeer } from "./GedaechtnisLeer";
import { useEffect, useRef, useState } from "react";
import { api, type AkteSachen, type AkteSachenArt } from "./api";
import { navigate } from "./ui";
import { memoryReturnPath } from "./profileReturn";
import "./MemoryDirectory.css";
import { OrganisationGroups } from "./OrganisationGroups";
import { MemoryPlaces } from "./MemoryPlaces";
import { WorkspaceAvatar } from "./MemoryAvatar";
import { Gruppe, Leer } from "./grundlage";
import { InterfaceIcon } from "./InterfaceIcon";

const SEITE = 50;
const TEXTE: Record<AkteSachenArt, { titel: string; suche: string; leer: string }> = {
  person: { titel: "Menschen", suche: "Name oder E-Mail suchen", leer: "Sobald Quellen mit Personen vorliegen, erscheinen sie hier." },
  organisation: { titel: "Organisationen", suche: "Organisation suchen", leer: "Organisationen erkennt Kingfisher an der Domäne einer Adresse und an Erwähnungen im Text." },
  projekt: { titel: "Projekte", suche: "Projekt suchen", leer: "Sobald Quellen einem Projekt zugeordnet sind, erscheint es hier." },
  ort: { titel: "Orte", suche: "Ort suchen", leer: "Orte kommen aus Terminen und aus Erwähnungen im Text." },
  thema: { titel: "Themen", suche: "Thema suchen", leer: "Themen erscheinen, sobald Quellen thematisch sortiert sind." },
};

function tag(value: string | null) {
  const zeit = value ? new Date(value) : null;
  return zeit && !Number.isNaN(zeit.getTime()) ? new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric" }).format(zeit) : "";
}

/** Sachen einer Art mit ihrer Akte: eine Zeile je Sache, Anzahl der Quellen und letzte Aktivität. */
export function SachenListe({ art, query: restoredQuery, page: restoredPage, onQueryChange, onPageChange }: {
  art: AkteSachenArt; query?: string; page?: number; onQueryChange?: (query: string) => void; onPageChange?: (page: number) => void;
}) {
  const [data, setData] = useState<AkteSachen | null>(null);
  const [fehler, setFehler] = useState(false);
  const [localQuery, setLocalQuery] = useState("");
  const [localPage, setLocalPage] = useState(0);
  const suche = restoredQuery ?? localQuery;
  const seite = restoredPage === undefined ? localPage : restoredPage - 1;
  const setSuche = (value: string) => { setLocalQuery(value); onQueryChange?.(value); };
  const setSeite = (value: number) => { setLocalPage(value); onPageChange?.(value + 1); };
  const [neu, setNeu] = useState(0);
  const version = useRef(0);
  useEffect(() => { setLocalPage(0); setLocalQuery(""); setData(null); }, [art]);
  useEffect(() => {
    const eigene = ++version.current;
    setFehler(false);
    // Suchen wartet kurz, statt bei jedem Buchstaben zu fragen.
    const timer = window.setTimeout(() => {
      api.akteSachen(art, seite * SEITE, suche.trim()).then(result => { if (eigene === version.current) setData(result); })
        .catch(() => { if (eigene === version.current) setFehler(true); });
    }, suche ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [art, seite, suche, neu]);
  // Wird noch berechnet, still nachladen.
  const offen = data?.berechnung.offen ?? 0;
  useEffect(() => {
    if (!offen) return;
    const timer = window.setTimeout(() => setNeu(value => value + 1), 3000);
    return () => window.clearTimeout(timer);
  }, [offen, data]);
  const text = TEXTE[art];
  const seiten = data ? Math.max(1, Math.ceil(data.gesamt / SEITE)) : 1;
  function openAkte(sache: string) {
    const query = new URLSearchParams(window.location.search);
    if (!query.has("tab")) query.set("tab", ({person: "people", organisation: "organizations", projekt: "projects", ort: "places", thema: "topics"} as Record<AkteSachenArt, string>)[art]);
    query.set("q", suche);
    query.set("page", String(seite + 1));
    const returnTo = memoryReturnPath(new URLSearchParams({ return_to: `/memory?${query}` }).toString());
    navigate(`/memory/akte/${encodeURIComponent(sache)}?${new URLSearchParams({return_to: returnTo})}`);
  }
  const anzahl = data ? `${data.gesamt} ${data.gesamt === 1 ? "Eintrag" : "Einträge"}${data.berechnung.offen ? ` · ${data.berechnung.offen} Quellen in Arbeit` : ""}` : "";
  return <section className="memory-directory gd-verzeichnis" data-memory-loading={!data && !fehler} aria-label={text.titel}>
    <header className="gd-verzeichnis-kopf"><h2 className="g-titel">{text.titel}</h2>
      <label className="directory-search"><span className="visually-hidden">{text.suche}</span>
        <input type="search" value={suche} onChange={event => { setSuche(event.target.value); setSeite(0); }} placeholder={`${text.suche} …`} />
      </label></header>
    {fehler ? <Leer zeichen="search" satz="Die Liste konnte gerade nicht geladen werden." aktion={<button type="button" className="g-knopf-getoent" onClick={() => setNeu(value => value + 1)}>Erneut laden</button>} /> : null}
    {!data && !fehler ? <p className="directory-count" aria-busy="true">Wird geladen …</p> : null}
    {data && data.sachen.length ? <Gruppe titel={<span className="directory-count" aria-live="polite">{anzahl}</span>}><ul className="directory-list gd-liste">{data.sachen.map(sache => <li key={sache.sache} data-memory-row={sache.sache}>
      <button type="button" className="g-zeile gd-zeile" onClick={() => openAkte(sache.sache)} aria-label={`Akte öffnen: ${sache.name}`}>
        {art === "ort" || art === "thema" ? <span className="g-zeile-symbol gd-zeichen" aria-hidden="true"><InterfaceIcon name={art === "ort" ? "pin" : "brain"} /></span> : <WorkspaceAvatar id={sache.sache} label={sache.name} />}
        <span className="g-zeile-text"><span className="g-zeile-titel">{sache.name}</span><span className="g-zeile-neben">{sache.quellen} {sache.quellen === 1 ? "Quelle" : "Quellen"}</span></span>
        {sache.letzte ? <span className="g-zeile-wert">{tag(sache.letzte)}</span> : null}
        <span className="g-zeile-pfeil" aria-hidden="true" />
      </button></li>)}</ul></Gruppe> : data && !fehler ? (suche ? <Leer zeichen="search" satz="Kein passender Eintrag." aktion={<button type="button" className="g-knopf-getoent" onClick={() => { setSuche(""); setSeite(0); }}>Suche zurücksetzen</button>} /> : <GedaechtnisLeer satz={text.leer} />) : null}
    {seiten > 1 ? <nav className="directory-pagination" aria-label="Aktenseiten">
      <button type="button" className="g-knopf-getoent g-kompakt" disabled={seite === 0} onClick={() => setSeite(seite - 1)}>Zurück</button>
      <span>Seite {seite + 1} von {seiten}</span>
      <button type="button" className="g-knopf-getoent g-kompakt" disabled={seite + 1 >= seiten} onClick={() => setSeite(seite + 1)}>Weiter</button>
    </nav> : null}
    {data && art === "organisation" && <OrganisationGroups entries={data.sachen.map(sache => ({id:sache.sache,name:sache.name}))} />}
    {data && art === "ort" && <MemoryPlaces entries={data.sachen.map(sache => ({id:sache.sache,name:sache.name}))} />}
  </section>;
}
