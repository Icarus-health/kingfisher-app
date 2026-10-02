import { useEffect, useRef, useState } from "react";
import { ApiError, api, type UebernehmenErgebnis, type UebernehmenVorschau, type UebernehmenVorschlag } from "./api";
import { ergebnisText, saetzeText, vorgabeWahl, vorgeschlagenText } from "./uebernehmen";
import { navigate } from "./ui";
import "./Uebernehmen.css";

type Entscheidung = "angenommen" | "abgelehnt" | "fehler";

/**
 * „In die Akte übernehmen“ unter einer Antwort in Sätzen, neben „Stimmt nicht?“. Ebenso zurückhaltend: ein stiller Link,
 * erst nach dem Klick eine Rückfrage in einem Satz (welche Sätze, in welche Akte, eine Notiz). „Vorschlagen“ legt nur
 * Vorschläge an; wissen wird ein Satz erst, wenn der Mensch auf der Karte „Bestätigen“ drückt.
 */
export function InDieAkte({ conversationId, messageId }: { conversationId: string; messageId: string }) {
  const [offen, setOffen] = useState(false);
  const [vorschau, setVorschau] = useState<UebernehmenVorschau | null>(null);
  const [wahl, setWahl] = useState<number[]>([]);
  const [sache, setSache] = useState<string | null>(null);
  const [notiz, setNotiz] = useState("");
  const [sendet, setSendet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [ergebnisse, setErgebnisse] = useState<UebernehmenErgebnis[] | null>(null);
  const [bisher, setBisher] = useState<UebernehmenVorschlag[]>([]);
  const [name, setName] = useState("");
  const [entschieden, setEntschieden] = useState<Record<string, Entscheidung>>({});
  const [arbeitet, setArbeitet] = useState("");
  const erste = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!offen || vorschau) return;
    let aktiv = true;
    api.uebernehmenVorschau(conversationId, messageId)
      .then(daten => {
        if (!aktiv) return;
        setVorschau(daten); setSache(daten.sache); setWahl(vorgabeWahl(daten.saetze, daten.bisher));
        setBisher(daten.bisher); setName(daten.ziele.find(z => z.sache === daten.sache)?.name ?? "");
        setFehler("");
      })
      .catch(e => { if (aktiv) setFehler(e instanceof ApiError && e.detail ? e.detail : "Das ließ sich gerade nicht laden. Bitte noch einmal versuchen."); });
    return () => { aktiv = false; };
  }, [offen, vorschau, conversationId, messageId]);
  useEffect(() => { if (vorschau) erste.current?.focus(); }, [vorschau]);

  function schalten(nr: number) {
    setWahl(alt => alt.includes(nr) ? alt.filter(n => n !== nr) : [...alt, nr].sort((a, b) => a - b));
  }

  async function vorschlagen() {
    if (!wahl.length) return;
    setSendet(true); setFehler("");
    try {
      const antwort = await api.uebernehmenVorschlagen({ conversation_id: conversationId, message_id: messageId, saetze: wahl, sache, notiz: notiz.trim() });
      setErgebnisse(antwort.ergebnisse); setName(antwort.name); setOffen(false);
      // Die neuen Vorschläge zu den schon bekannten: Was noch zur Entscheidung steht, bleibt sichtbar.
      const neu = antwort.ergebnisse.flatMap(e => (e.vorschlag ? [e.vorschlag] : []));
      setBisher(alt => [...alt.filter(v => !neu.some(n => n.id === v.id)), ...neu]);
    } catch (e) {
      setFehler(e instanceof ApiError && e.detail ? e.detail : "Das ließ sich gerade nicht vorschlagen. Bitte noch einmal versuchen.");
    } finally {
      setSendet(false);
    }
  }

  async function entscheiden(id: string, wie: "annehmen" | "ablehnen") {
    setArbeitet(id); setFehler("");
    try {
      if (wie === "annehmen") await api.wissenAnnehmen(id); else await api.wissenAblehnen(id);
      setEntschieden(alt => ({ ...alt, [id]: wie === "annehmen" ? "angenommen" : "abgelehnt" }));
    } catch (e) {
      setFehler(e instanceof ApiError && e.detail ? e.detail : "Das ließ sich gerade nicht entscheiden. Bitte noch einmal versuchen.");
    } finally {
      setArbeitet("");
    }
  }

  const sacheAnzeige = (ziel: string | null) => vorschau?.ziele.find(z => z.sache === ziel)?.name ?? name;
  // Vorschläge, über die noch zu entscheiden ist oder die schon entschieden sind: die eben gemachten, sonst die früheren dieser Antwort.
  const karten: UebernehmenVorschlag[] = offen ? [] : bisher;
  const nebenbei = ergebnisse?.filter(e => !e.vorschlag) ?? [];

  const karte = (v: UebernehmenVorschlag, hinweise: string[]) => {
    const stand = entschieden[v.id] ?? (v.state === "accepted" ? "angenommen" : v.state === "rejected" ? "abgelehnt" : null);
    return <section className="memory-candidate uebernehmen-karte" key={v.id} aria-label="Gedächtnisvorschlag">
      <span>GEDÄCHTNISVORSCHLAG FÜR DIE AKTE</span>
      <strong>{v.statement}</strong>
      {v.evidence[0] ? <p className="memory-source">Beleg: „{v.evidence[0].quote}“</p> : null}
      {hinweise.map(h => <p className="memory-notice" key={h}>{h}</p>)}
      {stand === "angenommen" ? <p className="memory-decision" role="status">In der Akte{sacheAnzeige(v.subject_ref) ? ` von ${sacheAnzeige(v.subject_ref)}` : ""}.</p> : null}
      {stand === "abgelehnt" ? <p className="memory-decision" role="status">Nicht gespeichert.</p> : null}
      <div className="memory-actions">
        {stand === null && v.state === "pending" ? <>
          <button className="memory-confirm" type="button" disabled={arbeitet !== ""} onClick={() => void entscheiden(v.id, "annehmen")}>Bestätigen</button>
          <button className="memory-reject" type="button" disabled={arbeitet !== ""} onClick={() => void entscheiden(v.id, "ablehnen")}>Nicht speichern</button>
        </> : null}
        {stand === "angenommen" ? <button className="memory-reject" type="button" onClick={() => navigate(`/memory/akte/${encodeURIComponent(v.subject_ref)}`)}>Akte öffnen</button> : null}
      </div>
    </section>;
  };

  if (!offen) {
    return <>
      <button className="stimmt-nicht-link" type="button" onClick={() => { setVorschau(null); setErgebnisse(null); setOffen(true); }}>In die Akte übernehmen</button>
      {karten.length || nebenbei.length || fehler ? <div className="uebernehmen-stand">
        {ergebnisse ? <p className="uebernehmen-ok" role="status">{vorgeschlagenText(ergebnisse)}</p> : null}
        {karten.map(v => karte(v, ergebnisse?.find(e => e.vorschlag?.id === v.id)?.hinweise ?? []))}
        {nebenbei.map(e => <p className="uebernehmen-nebenbei" key={e.nr}>„{e.text}“: {ergebnisText(e)}</p>)}
        {fehler ? <p className="uebernehmen-fehler" role="alert">{fehler}</p> : null}
      </div> : null}
    </>;
  }

  const ziele = vorschau?.ziele ?? [];
  return <form className="uebernehmen" aria-label="In die Akte übernehmen" onSubmit={event => { event.preventDefault(); void vorschlagen(); }}>
    {!vorschau && !fehler ? <p>Wird geladen …</p> : null}
    {vorschau && !ziele.length ? <p>Zu dieser Antwort gibt es keine Akte, in die sie passt.</p> : null}
    {vorschau && bisher.length ? <div className="uebernehmen-stand">
      <p>Schon vorgeschlagen:</p>
      {bisher.map(v => karte(v, []))}
    </div> : null}
    {vorschau && ziele.length ? <>
      <p id={`uebernehmen-${messageId}`}>{ziele.length === 1 ? `Welche Sätze sollen in die Akte von ${ziele[0].name}?` : "Welche Sätze sollen in die Akte, und in welche?"}</p>
      <ul className="uebernehmen-saetze" aria-labelledby={`uebernehmen-${messageId}`}>
        {vorschau.saetze.map((satz, index) => <li key={satz.nr}>
          <label>
            <input type="checkbox" ref={index === 0 ? erste : undefined} checked={wahl.includes(satz.nr)} disabled={sendet}
              onChange={() => schalten(satz.nr)} />
            <span>{satz.text}</span>
          </label>
          {satz.steht_schon ? <small>Steht schon in der Akte.</small> : null}
          {!satz.steht_schon && bisher.some(v => v.statement === satz.text && v.state === "pending") ? <small>Liegt schon zur Entscheidung vor.</small> : null}
          {satz.hinweise.map(h => <small className="uebernehmen-hinweis" key={h}>{h}</small>)}
        </li>)}
      </ul>
      {ziele.length > 1 ? <div className="stimmt-nicht-arten uebernehmen-ziele" role="group" aria-label="Akte">
        {ziele.map(z => <button key={z.sache} type="button" aria-pressed={sache === z.sache} disabled={sendet}
          onClick={() => setSache(z.sache)}>{z.name}<small>{z.art_text}</small></button>)}
      </div> : null}
      <label className="stimmt-nicht-feld">Notiz <small>(freiwillig)</small>
        <input type="text" value={notiz} maxLength={500} autoComplete="off" disabled={sendet} onChange={event => setNotiz(event.target.value)} />
      </label>
    </> : null}
    {fehler ? <p className="stimmt-nicht-fehler" role="alert">{fehler}</p> : null}
    <div className="stimmt-nicht-aktionen">
      {vorschau && ziele.length ? <button className="secondary-action" type="submit" disabled={!wahl.length || sendet}>{wahl.length > 1 ? `${saetzeText(wahl.length)} vorschlagen` : "Vorschlagen"}</button> : null}
      <button className="stimmt-nicht-link" type="button" disabled={sendet} onClick={() => { setOffen(false); setFehler(""); }}>Abbrechen</button>
    </div>
  </form>;
}
