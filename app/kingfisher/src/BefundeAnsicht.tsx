import { useEffect, useRef, useState } from "react";
import { api, type Befund, type BefundZusammenfassung } from "./api";
import { ergebnisSatz, gruppieren, waehlbar, wahlTexte, zaehlSatz } from "./befunde";
import { navigate } from "./ui";
import { ProfileSource } from "./ProfileSource";
import "./Befunde.css";

// „Was Kingfisher aufgefallen ist“ hinter Einstellungen → Für Techniker: die Befunde des Lint über alle Akten
// (sidecar: lint.py, lint_routes.py). Je Befund ein Satz, die beteiligten Akten als Links, bei Widersprüchen
// zwei Klicks (der Wert selbst steht auf dem Knopf), sonst „Erledigt“ und „Ignorieren“. Keine neue Seite:
// Die Liste nimmt Entscheidungen ab, statt eine Ansicht hinzuzufügen (docs/17-stabschef.md).

export type BefundMitQuellen = Befund;

function tag(value?: string | null) {
  if (!value) return "";
  const kalenderdatum = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  const zeit = kalenderdatum
    ? new Date(Number(kalenderdatum[1]), Number(kalenderdatum[2]) - 1, Number(kalenderdatum[3]))
    : new Date(value);
  return Number.isNaN(zeit.getTime()) ? "" : zeit.toLocaleDateString("de-DE", { day: "numeric", month: "numeric", year: "numeric" });
}

export function BefundZeile({ befund, arbeitet, onAktion }: {
  befund: BefundMitQuellen; arbeitet: boolean; onAktion: (befund: BefundMitQuellen, aktion: "neu" | "alt" | "erledigt" | "abgewiesen") => void;
}) {
  const wahl = waehlbar(befund);
  const knoepfe = wahlTexte(befund);
  return <li className={befund.schwere === "wichtig" ? "befund befund-wichtig" : "befund"}>
    <p className="befund-text">{befund.text}</p>
    <small className="befund-kopf">{befund.art_text}{tag(befund.gefunden_am) ? ` · aufgefallen am ${tag(befund.gefunden_am)}` : ""}</small>
    {befund.sachen.length ? <div className="befund-akten" aria-label="Beteiligte Akten">
      {befund.sachen.map(s => <button key={s.sache} type="button" className="text-action"
        onClick={() => navigate(`/memory/akte/${encodeURIComponent(s.sache)}`)} aria-label={`Akte öffnen: ${s.name}`}>{s.name}</button>)}
    </div> : null}
    {befund.belege.length ? <div className="befund-belege" aria-label="Quellen, keine bestätigte Aussage">
      <p className="befund-hinweis">Quellenaussagen · keine bestätigten Fakten</p>
      {befund.belege.map((beleg, index) => <div className="befund-beleg" key={`${beleg.episode_id}:${index}`}>
        <blockquote>{beleg.zitat || "Originalzitat nicht verfügbar."}</blockquote>
        <small className="befund-kopf">{tag(beleg.datum) ? `Quellenzeit: ${tag(beleg.datum)}` : <><strong>Quellenzeit unbekannt</strong></>}
          {tag(beleg.recorded_at) ? ` · Erfasst: ${tag(beleg.recorded_at)}` : ""}</small>
        <ProfileSource kind="episode" id={beleg.episode_id} label="Originalquelle prüfen" readOnly />
      </div>)}
    </div> : null}
    {wahl ? <p className="befund-hinweis">Ein Vorschlag: Erst dein Klick macht daraus Wissen. Die Quellen bleiben, wie sie sind.</p> : null}
    <div className="befund-aktionen">
      {wahl ? <>
        <button type="button" className="primary-action" disabled={arbeitet} onClick={() => onAktion(befund, "neu")}>{knoepfe.neu}</button>
        <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => onAktion(befund, "alt")}>{knoepfe.alt}</button>
      </> : <button type="button" className="secondary-action" disabled={arbeitet} onClick={() => onAktion(befund, "erledigt")}>Erledigt</button>}
      <button type="button" className="text-action" disabled={arbeitet} onClick={() => onAktion(befund, "abgewiesen")}>Ignorieren</button>
    </div>
  </li>;
}

export function WasAufgefallenIst({ active }: { active: boolean }) {
  const [befunde, setBefunde] = useState<BefundMitQuellen[] | null>(null);
  const [zaehlung, setZaehlung] = useState<BefundZusammenfassung | null>(null);
  const [arbeitet, setArbeitet] = useState("");
  const [fehler, setFehler] = useState("");
  const [meldung, setMeldung] = useState("");
  const aktivRef = useRef(false);
  const ladeVersion = useRef(0);
  const aktionLock = useRef("");

  async function laden() {
    const version = ++ladeVersion.current;
    setBefunde(null);
    const daten = await api.lintBefunde();
    if (!aktivRef.current || version !== ladeVersion.current) return;
    setBefunde(daten.befunde); setZaehlung(daten.zusammenfassung); setFehler("");
  }

  useEffect(() => {
    if (!active) return;
    let aktiv = true;
    aktivRef.current = true;
    const version = ++ladeVersion.current;
    api.lintBefunde()
      .then(daten => { if (aktiv && version === ladeVersion.current) { setBefunde(daten.befunde); setZaehlung(daten.zusammenfassung); setFehler(""); } })
      .catch(() => { if (aktiv && version === ladeVersion.current) setFehler("Die Liste konnte nicht geladen werden."); });
    return () => { aktiv = false; aktivRef.current = false; ladeVersion.current++; };
  }, [active]);

  async function aktion(befund: BefundMitQuellen, was: "neu" | "alt" | "erledigt" | "abgewiesen") {
    if (!aktivRef.current || aktionLock.current) return;
    aktionLock.current = befund.id;
    setArbeitet(befund.id); setFehler(""); setMeldung("");
    try {
      const entscheiden = api.lintEntscheiden as (id: string, wahl: "alt" | "neu", stand?: string) => ReturnType<typeof api.lintEntscheiden>;
      const antwort = was === "neu" || was === "alt" ? await entscheiden(befund.id, was, befund.stand) : await api.lintStatus(befund.id, was, befund.stand);
      if (!aktivRef.current) return;
      setBefunde(alt => (alt ?? []).filter(b => b.id !== befund.id));
      setZaehlung(antwort.zusammenfassung);
      setMeldung(ergebnisSatz(was, befund));
    } catch {
      if (aktivRef.current) {
        setFehler("Das ließ sich gerade nicht speichern. Vielleicht hat sich die Quelle geändert; die Liste wird neu geladen.");
        await laden().catch(() => undefined);
      }
    } finally {
      aktionLock.current = "";
      if (aktivRef.current) setArbeitet("");
    }
  }

  async function pruefen() {
    if (!aktivRef.current || aktionLock.current) return;
    aktionLock.current = "pruefen";
    setArbeitet("pruefen"); setFehler(""); setMeldung("");
    try {
      const antwort = await api.lintAnstossen();
      await laden();
      setMeldung(antwort.lauf.laeuft ? "Die Prüfung läuft schon im Hintergrund." :
        `Geprüft. ${antwort.lauf.neu ? `${antwort.lauf.neu} neu aufgefallen.` : "Nichts Neues aufgefallen."}`);
    } catch { setFehler("Die Prüfung ließ sich gerade nicht starten. Bitte noch einmal versuchen."); }
    finally { aktionLock.current = ""; if (aktivRef.current) setArbeitet(""); }
  }

  const { oben, ruhend } = gruppieren(befunde ?? []);
  return <section className="source-section befunde" aria-label="Was Kingfisher aufgefallen ist">
    <h2>Was Kingfisher aufgefallen ist</h2>
    <p>Kingfisher prüft seine Akten regelmäßig gegen sich selbst: Nennen zwei Akten verschiedene Fristen, widerspricht eine neue Mail
      etwas, das du angenommen hattest, oder hängt eine Quelle an keiner Akte, steht es hier. Geändert wird nichts ohne deinen Klick.</p>
    {befunde === null && !fehler ? <p>Wird geladen …</p> : null}
    {befunde !== null && zaehlung ? <p className="befunde-zahl" role="status">{zaehlSatz(zaehlung)}</p> : null}
    {oben.length ? <ul className="befunde-liste" aria-label="Aufgefallene Punkte">
      {oben.map(b => <BefundZeile key={b.id} befund={b} arbeitet={arbeitet !== ""} onAktion={(x, a) => void aktion(x, a)} />)}
    </ul> : null}
    {ruhend.length ? <details className="befunde-ruhend">
      <summary>{ruhend.length === 1 ? "1 Akte ruht" : `${ruhend.length} Akten ruhen`} seit über einem Jahr</summary>
      <ul className="befunde-liste">
        {ruhend.map(b => <BefundZeile key={b.id} befund={b} arbeitet={arbeitet !== ""} onAktion={(x, a) => void aktion(x, a)} />)}
      </ul>
    </details> : null}
    <div className="befunde-pruefen">
      <button type="button" className="secondary-action" disabled={arbeitet !== ""} onClick={() => void pruefen()}>
        {arbeitet === "pruefen" ? "Wird geprüft …" : "Jetzt prüfen"}</button>
      {zaehlung?.letzter_lauf ? <small>Zuletzt geprüft am {tag(zaehlung.letzter_lauf)}.</small> : null}
    </div>
    {meldung ? <p className="source-hint" role="status">{meldung}</p> : null}
    {fehler ? <p className="partial-error" role="alert">{fehler}</p> : null}
  </section>;
}
