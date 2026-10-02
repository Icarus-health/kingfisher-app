import { GedaechtnisLeer } from "./GedaechtnisLeer";
import { useEffect, useRef, useState } from "react";
import { api, type AkteSachen, type AkteSachenArt } from "./api";
import { navigate } from "./ui";
import "./MemoryDirectory.css";

const SEITE = 50;
const TEXTE: Record<AkteSachenArt, { titel: string; suche: string; leer: string }> = {
  person: { titel: "Menschen", suche: "Name oder E-Mail suchen", leer: "Sobald Quellen mit Personen vorliegen, erscheinen sie hier." },
  organisation: { titel: "Organisationen", suche: "Organisation suchen", leer: "Organisationen erkennt Kingfisher an der Domäne einer Adresse und an Erwähnungen im Text." },
  projekt: { titel: "Projekte", suche: "Projekt suchen", leer: "Sobald Quellen einem Projekt zugeordnet sind, erscheint es hier." },
  ort: { titel: "Orte", suche: "Ort suchen", leer: "Orte kommen aus Terminen und aus Erwähnungen im Text." },
  thema: { titel: "Themenakten", suche: "Thema suchen", leer: "Themen erscheinen, sobald Quellen thematisch sortiert sind." },
};

function tag(value: string | null) {
  const zeit = value ? new Date(value) : null;
  return zeit && !Number.isNaN(zeit.getTime()) ? new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "numeric", year: "numeric" }).format(zeit) : "";
}

/** Sachen einer Art mit ihrer Akte: eine Zeile je Sache, Anzahl der Quellen und letzte Aktivität. */
export function SachenListe({ art }: { art: AkteSachenArt }) {
  const [data, setData] = useState<AkteSachen | null>(null);
  const [fehler, setFehler] = useState(false);
  const [suche, setSuche] = useState("");
  const [seite, setSeite] = useState(0);
  const [neu, setNeu] = useState(0);
  const version = useRef(0);
  useEffect(() => { setSeite(0); setSuche(""); setData(null); }, [art]);
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
  return <section className="memory-directory" aria-label={text.titel}>
    <header><p className="eyebrow">GEDÄCHTNIS</p><h1>{text.titel}</h1>
      <p>Eine Akte pro Eintrag, aus den Quellen abgeleitet. Jede Zeile in der Akte führt zur Quelle.</p></header>
    <label className="directory-search">{text.suche}
      <input type="search" value={suche} onChange={event => { setSuche(event.target.value); setSeite(0); }} placeholder="Suchen …" />
    </label>
    {fehler ? <div className="directory-empty" role="status"><p>Die Liste konnte gerade nicht geladen werden.</p><button type="button" onClick={() => setNeu(value => value + 1)}>Erneut laden</button></div> : null}
    {data ? <p className="directory-count" aria-live="polite">{data.gesamt} {data.gesamt === 1 ? "Eintrag" : "Einträge"}{data.berechnung.offen ? ` · für ${data.berechnung.offen} Quellen wird noch berechnet, wozu sie gehören` : ""}</p> : <p className="directory-count" aria-busy="true">Wird geladen …</p>}
    {data && data.sachen.length ? <ul className="directory-list">{data.sachen.map(sache => <li key={sache.sache}>
      <button type="button" onClick={() => navigate(`/memory/akte/${encodeURIComponent(sache.sache)}`)} aria-label={`Akte öffnen: ${sache.name}`}>
        <span className="directory-monogram" aria-hidden="true">{sache.name.slice(0, 1).toLocaleUpperCase("de")}</span>
        <span className="directory-label"><strong>{sache.name}</strong><small>{sache.quellen} {sache.quellen === 1 ? "Quelle" : "Quellen"}{sache.letzte ? ` · zuletzt ${tag(sache.letzte)}` : ""}</small></span>
        <span className="directory-open">Akte öffnen <span aria-hidden="true">→</span></span>
      </button></li>)}</ul> : data && !fehler ? <div className="directory-empty"><h2>{suche ? "Kein passender Eintrag" : "Hier ist noch Platz"}</h2>{suche ? <p>Versuche einen anderen Namen.</p> : <GedaechtnisLeer satz={text.leer} />}</div> : null}
    {seiten > 1 ? <nav className="directory-pagination" aria-label="Aktenseiten">
      <button type="button" disabled={seite === 0} onClick={() => setSeite(seite - 1)}>Zurück</button>
      <span>Seite {seite + 1} von {seiten}</span>
      <button type="button" disabled={seite + 1 >= seiten} onClick={() => setSeite(seite + 1)}>Weiter</button>
    </nav> : null}
  </section>;
}
