import { useEffect, useRef, useState } from "react";
import { ApiError, api, type Rueckmeldung, type RueckmeldungArt, type RueckmeldungZaehlung } from "./api";
import { ARTEN, GEMELDET, kurz, zaehlSatz } from "./rueckmeldung";
import { Verweis } from "./Verweis";
import "./Rueckmeldung.css";

/**
 * „Stimmt nicht?“ unter einer Antwort (Rückkanal für Fehler). Zurückhaltend: ein stiller Text, erst nach dem Klick
 * eine Frage in einem Satz mit den Arten zur Auswahl und einem freien Feld. Die Meldung bleibt auf diesem Rechner,
 * schreibt nichts ins Gedächtnis und sendet nichts; unter „Für Techniker“ lässt sie sich als Prüffrage speichern (Messlatte).
 */
export function StimmtNicht({ conversationId, messageId }: { conversationId: string; messageId: string }) {
  const [offen, setOffen] = useState(false);
  const [art, setArt] = useState<RueckmeldungArt | null>(null);
  const [richtig, setRichtig] = useState("");
  const [sendet, setSendet] = useState(false);
  const [gemerkt, setGemerkt] = useState(false);
  const [fehler, setFehler] = useState("");
  const erste = useRef<HTMLButtonElement>(null);
  useEffect(() => { if (offen) erste.current?.focus(); }, [offen]);

  async function senden() {
    if (!art) return;
    setSendet(true); setFehler("");
    try {
      await api.rueckmeldungMelden({ conversation_id: conversationId, message_id: messageId, art, richtig: richtig.trim() });
      setGemerkt(true); setOffen(false);
    } catch (e) {
      setFehler(e instanceof ApiError && e.detail ? e.detail : "Das ließ sich gerade nicht merken. Bitte noch einmal versuchen.");
    } finally {
      setSendet(false);
    }
  }

  if (gemerkt) return <p className="stimmt-nicht-gemerkt" role="status">{GEMELDET} <Verweis ziel="technik-rueckmeldungen" />.</p>;
  if (!offen) return <button className="stimmt-nicht-link" type="button" onClick={() => setOffen(true)}>Stimmt nicht?</button>;
  return <form className="stimmt-nicht" aria-label="Antwort melden" onSubmit={event => { event.preventDefault(); void senden(); }}>
    <p id={`stimmt-nicht-${messageId}`}>Was stimmt an dieser Antwort nicht?</p>
    <div className="stimmt-nicht-arten" role="group" aria-labelledby={`stimmt-nicht-${messageId}`}>
      {ARTEN.map((eintrag, index) => <button key={eintrag.id} type="button" ref={index === 0 ? erste : undefined}
        aria-pressed={art === eintrag.id} disabled={sendet} onClick={() => setArt(eintrag.id)}>{eintrag.text}</button>)}
    </div>
    <label className="stimmt-nicht-feld">Richtig wäre … <small>(freiwillig, kurz, zum Beispiel ein Datum oder ein Name)</small>
      <input type="text" value={richtig} maxLength={2000} autoComplete="off" disabled={sendet} onChange={event => setRichtig(event.target.value)} />
    </label>
    {fehler ? <p className="stimmt-nicht-fehler" role="alert">{fehler}</p> : null}
    <div className="stimmt-nicht-aktionen">
      <button className="secondary-action" type="submit" disabled={!art || sendet}>Melden</button>
      <button className="stimmt-nicht-link" type="button" disabled={sendet} onClick={() => { setOffen(false); setFehler(""); }}>Abbrechen</button>
    </div>
  </form>;
}

function tag(wert: string) {
  const zeit = new Date(wert);
  return Number.isNaN(zeit.getTime()) ? "" : zeit.toLocaleDateString("de-DE", { day: "numeric", month: "numeric", year: "numeric" });
}

/** Die ruhige Liste der Meldungen in den Einstellungen: Anzahl, offene, je Meldung Frage und Art, „Erledigt“. */
export function RueckmeldungenListe({ active }: { active: boolean }) {
  const [meldungen, setMeldungen] = useState<Rueckmeldung[] | null>(null);
  const [zaehlung, setZaehlung] = useState<RueckmeldungZaehlung>({ gesamt: 0, offen: 0, erledigt: 0 });
  const [arbeitet, setArbeitet] = useState("");
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");

  useEffect(() => {
    if (!active) return;
    let aktiv = true;
    api.rueckmeldungen()
      .then(daten => { if (aktiv) { setMeldungen(daten.meldungen); setZaehlung(daten.zaehlung); setFehler(""); } })
      .catch(() => { if (aktiv) setFehler("Die Meldungen konnten nicht geladen werden."); });
    return () => { aktiv = false; };
  }, [active]);

  async function erledigt(id: string) {
    setArbeitet(id); setFehler(""); setGespeichert("");
    try {
      const antwort = await api.rueckmeldungErledigt(id);
      setMeldungen(alt => (alt ?? []).map(m => (m.id === id ? antwort.meldung : m)));
      setZaehlung({ gesamt: antwort.gesamt, offen: antwort.offen, erledigt: antwort.erledigt });
    } catch { setFehler("Das ließ sich gerade nicht abhaken. Bitte noch einmal versuchen."); }
    finally { setArbeitet(""); }
  }

  async function speichern() {
    setArbeitet("faelle"); setFehler(""); setGespeichert("");
    try {
      const text = await api.rueckmeldungFaelle();
      const link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
      link.download = "rueckmeldungen-faelle.json";
      document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(link.href), 10000);
      setGespeichert("Gespeichert als rueckmeldungen-faelle.json. Die Datei enthält deine Fragen und Antworten: Sie bleibt auf diesem Rechner.");
    } catch { setFehler("Die Datei ließ sich nicht erzeugen. Bitte noch einmal versuchen."); }
    finally { setArbeitet(""); }
  }

  return <section className="source-section rueckmeldungen" aria-label="Rückmeldungen">
    <h2>Was du gemeldet hast</h2>
    <p>Sagt Kingfisher etwas Falsches oder Unvollständiges, meldest du das mit „Stimmt nicht?“ unter der Antwort. Die Meldung bleibt auf diesem Rechner, schreibt nichts ins Gedächtnis und sendet nichts.</p>
    {/* Was aus einer Meldung wird, in Worten; der Befehl dazu steht in docs/38-rueckkanal.md, nicht hier (Fremdprobe, Befund 16). */}
    <p className="rueckmeldungen-wohin">Was daraus wird: Jede Meldung wird eine Prüffrage. Jede neue Fassung von Kingfisher muss sie bestehen, bis derselbe Fehler nicht mehr vorkommt.</p>
    {meldungen === null && !fehler ? <p>Wird geladen …</p> : <>
      <p className="rueckmeldungen-zahl" role="status">{zaehlSatz(zaehlung)}</p>
      {meldungen && meldungen.length > 0 ? <ul className="rueckmeldungen-liste" aria-label="Meldungen">
        {meldungen.map(m => <li key={m.id} className={m.status === "erledigt" ? "rueckmeldung-erledigt" : undefined}>
          <div>
            <strong>{kurz(m.frage)}</strong>
            <small>{m.art_text}{tag(m.erstellt) ? ` · ${tag(m.erstellt)}` : ""}{m.status === "erledigt" ? " · erledigt" : ""}</small>
            {m.richtig ? <small>Richtig wäre: {kurz(m.richtig, 140)}</small> : null}
          </div>
          {m.status === "offen" ? <button className="secondary-action" type="button" disabled={arbeitet !== ""} onClick={() => void erledigt(m.id)}>Erledigt</button> : null}
        </li>)}
      </ul> : null}
      {meldungen && meldungen.length > 0 ? <div className="rueckmeldungen-export">
        <button className="secondary-action" type="button" disabled={arbeitet !== ""} onClick={() => void speichern()}>Als Prüffragen speichern</button>
        <small>Die Datei braucht nur, wer Kingfisher für dich einrichtet oder weiterentwickelt. Erledigte Meldungen bleiben darin: Sie zeigen, dass der Fehler nicht wiederkommt.</small>
      </div> : null}
    </>}
    {fehler ? <p className="partial-error" role="alert">{fehler}</p> : null}
    {gespeichert ? <p className="source-hint" role="status">{gespeichert}</p> : null}
  </section>;
}
