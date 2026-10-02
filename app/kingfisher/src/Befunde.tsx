import { useEffect, useState } from "react";
import { api, type Befund, type BefundZusammenfassung } from "./api";
import { ergebnisSatz, gruppieren, waehlbar, wahlTexte, zaehlSatz } from "./befunde";
import { navigate } from "./ui";
import "./Befunde.css";

// „Was Kingfisher aufgefallen ist“ hinter Einstellungen → Für Techniker: die Befunde des Lint über alle Akten
// (sidecar: lint.py, lint_routes.py). Je Befund ein Satz, die beteiligten Akten als Links, bei Widersprüchen
// zwei Klicks (der Wert selbst steht auf dem Knopf), sonst „Erledigt“ und „Ignorieren“. Keine neue Seite:
// Die Liste nimmt Entscheidungen ab, statt eine Ansicht hinzuzufügen (docs/17-stabschef.md).

function tag(value: string) {
  const zeit = new Date(value);
  return Number.isNaN(zeit.getTime()) ? "" : zeit.toLocaleDateString("de-DE", { day: "numeric", month: "numeric", year: "numeric" });
}

function BefundZeile({ befund, arbeitet, onAktion }: {
  befund: Befund; arbeitet: boolean; onAktion: (befund: Befund, aktion: "neu" | "alt" | "erledigt" | "abgewiesen") => void;
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
  const [befunde, setBefunde] = useState<Befund[] | null>(null);
  const [zaehlung, setZaehlung] = useState<BefundZusammenfassung | null>(null);
  const [arbeitet, setArbeitet] = useState("");
  const [fehler, setFehler] = useState("");
  const [meldung, setMeldung] = useState("");

  async function laden() {
    const daten = await api.lintBefunde();
    setBefunde(daten.befunde); setZaehlung(daten.zusammenfassung); setFehler("");
  }

  useEffect(() => {
    if (!active) return;
    let aktiv = true;
    api.lintBefunde()
      .then(daten => { if (aktiv) { setBefunde(daten.befunde); setZaehlung(daten.zusammenfassung); setFehler(""); } })
      .catch(() => { if (aktiv) setFehler("Die Liste konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, [active]);

  async function aktion(befund: Befund, was: "neu" | "alt" | "erledigt" | "abgewiesen") {
    setArbeitet(befund.id); setFehler(""); setMeldung("");
    try {
      const antwort = was === "neu" || was === "alt" ? await api.lintEntscheiden(befund.id, was) : await api.lintStatus(befund.id, was);
      setBefunde(alt => (alt ?? []).filter(b => b.id !== befund.id));
      setZaehlung(antwort.zusammenfassung);
      setMeldung(ergebnisSatz(was, befund));
    } catch {
      setFehler("Das ließ sich gerade nicht speichern. Vielleicht hat sich die Quelle geändert; die Liste wird neu geladen.");
      void laden().catch(() => undefined);
    } finally { setArbeitet(""); }
  }

  async function pruefen() {
    setArbeitet("pruefen"); setFehler(""); setMeldung("");
    try {
      const antwort = await api.lintAnstossen();
      await laden();
      setMeldung(antwort.lauf.laeuft ? "Die Prüfung läuft schon im Hintergrund." :
        `Geprüft. ${antwort.lauf.neu ? `${antwort.lauf.neu} neu aufgefallen.` : "Nichts Neues aufgefallen."}`);
    } catch { setFehler("Die Prüfung ließ sich gerade nicht starten. Bitte noch einmal versuchen."); }
    finally { setArbeitet(""); }
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
