import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { BefundZeile, type BefundMitQuellen } from "./BefundeAnsicht";
import { ergebnisSatz } from "./befunde";
import "./Befunde.css";

type Antwort = Awaited<ReturnType<typeof api.lintBefunde>>;

function prioritaet(a: BefundMitQuellen, b: BefundMitQuellen) {
  const rang = (befund: BefundMitQuellen) =>
    befund.schwere === "wichtig" ? 0 : befund.art === "waise" || befund.sachen.length === 0 ? 1 : 2;
  return rang(a) - rang(b);
}

function todayBefunde(befunde: BefundMitQuellen[]) {
  return befunde.filter(befund => !(befund.art === "waise" && befund.unterart === "ruhend"))
    .sort(prioritaet);
}

/** Kleine, handlungsfähige Auswahl offener Gedächtnisfragen für „Heute“. */
export function MemoryQuestions({ active, onOpenAll }: { active: boolean; onOpenAll: () => void }) {
  const [befunde, setBefunde] = useState<BefundMitQuellen[] | null>(null);
  const [fehler, setFehler] = useState("");
  const [aktionFehler, setAktionFehler] = useState("");
  const [meldung, setMeldung] = useState("");
  const [arbeitet, setArbeitet] = useState("");
  const aktivRef = useRef(false);
  const ladeVersion = useRef(0);
  const aktionLock = useRef("");

  const laden = useCallback(async () => {
    const version = ++ladeVersion.current;
    setBefunde(null);
    const daten: Antwort = await api.lintBefunde("offen");
    if (!aktivRef.current || version !== ladeVersion.current) return;
    setBefunde(todayBefunde(daten.befunde as BefundMitQuellen[]));
    setFehler("");
  }, []);

  useEffect(() => {
    if (!active) return;
    let mounted = true;
    aktivRef.current = true;
    const version = ++ladeVersion.current;
    setBefunde(null);
    api.lintBefunde("offen")
      .then(daten => {
        if (mounted && version === ladeVersion.current) {
          setBefunde(todayBefunde(daten.befunde as BefundMitQuellen[]));
          setFehler("");
        }
      })
      .catch(() => {
        if (mounted && version === ladeVersion.current) setFehler("Die Gedächtnisfragen konnten nicht geladen werden.");
      });
    const refresh = () => {if (!aktionLock.current) void laden().catch(() => {if (mounted) setFehler('Die Gedächtnisfragen konnten nicht geladen werden.');});};
    window.addEventListener('focus', refresh);
    return () => { mounted = false; aktivRef.current = false; ladeVersion.current++; window.removeEventListener('focus', refresh); };
  }, [active]);

  async function neuLaden() {
    setFehler("");
    try { await laden(); }
    catch { if (aktivRef.current) setFehler("Die Gedächtnisfragen konnten nicht geladen werden. Bitte erneut versuchen."); }
  }

  async function aktion(befund: BefundMitQuellen, was: "neu" | "alt" | "erledigt" | "abgewiesen") {
    if (!aktivRef.current || aktionLock.current) return;
    aktionLock.current = befund.id;
    setArbeitet(befund.id); setAktionFehler(""); setMeldung("");
    try {
      const entscheiden = api.lintEntscheiden as (id: string, wahl: "alt" | "neu", stand?: string) => ReturnType<typeof api.lintEntscheiden>;
      const antwort = was === "neu" || was === "alt"
        ? await entscheiden(befund.id, was, befund.stand)
        : await api.lintStatus(befund.id, was, befund.stand);
      if (!aktivRef.current) return;
      setBefunde(alt => (alt ?? []).filter(punkt => punkt.id !== befund.id));
      setMeldung(ergebnisSatz(was, befund));
    } catch {
      if (aktivRef.current) {
        setAktionFehler("Das ließ sich gerade nicht speichern. Die Liste wird aktualisiert; bitte prüfe den Punkt erneut.");
        await neuLaden();
      }
    } finally {
      aktionLock.current = "";
      if (aktivRef.current) setArbeitet("");
    }
  }

  const auswahl = (befunde ?? []).slice(0, 5);
  if (!active) return null;
  return <section className="source-section befunde memory-questions" aria-label="Gedächtnisfragen">
    <div className="memory-questions-kopf">
      <div><h2>Gedächtnisfragen</h2><p>Wichtige offene Punkte mit ihren Quellen. Erst deine Entscheidung macht daraus Wissen.</p></div>
      <button type="button" className="text-action" onClick={onOpenAll}>Alle öffnen</button>
    </div>
    {befunde === null && !fehler ? <p role="status">Wird geladen …</p> : null}
    {fehler ? <p role="alert">{fehler} <button type="button" className="text-action" onClick={() => void neuLaden()}>Erneut laden</button></p> : null}
    {befunde?.length === 0 ? <p role="status">Keine offenen Gedächtnisfragen.</p> : null}
    {auswahl.length > 0 ? <ul className="befunde-liste" aria-label="Offene Gedächtnisfragen">
      {auswahl.map(befund => <BefundZeile key={befund.id} befund={befund} arbeitet={arbeitet !== ""} onAktion={(punkt, was) => void aktion(punkt, was)} />)}
    </ul> : null}
    {befunde && befunde.length > 5 ? <button type="button" className="text-action" onClick={onOpenAll}>
      Weitere {befunde.length - 5} Gedächtnisfragen öffnen
    </button> : null}
    {meldung ? <p className="source-hint" role="status">{meldung}</p> : null}
    {aktionFehler ? <p className="partial-error" role="alert">{aktionFehler} <button type="button" className="text-action" onClick={() => void neuLaden()}>Erneut laden</button></p> : null}
  </section>;
}
