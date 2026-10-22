import { useEffect, useRef, useState } from "react";
import { api, type AufgabenPostVorschlag, type Task } from "./api";
import { ProfileSource } from "./ProfileSource";
import { angenommenText, annehmenText } from "./aufgabenPost";

// Aufgaben folgen der Post: „Erledigt?“ und „Wieder bei dir?“ dort, wo auch die erkannten Aufgaben stehen. Ein Klick
// nimmt an (dieselbe Änderung wie der Durchlauf, mit Grund und Rückgängig in der Liste), einer verwirft (Aufgabe und
// Mail bleiben getrennt). Nichts davon ist ein Fakt im Bestand; der Sidecar schlägt nur vor (`aufgaben_post.py`).

const DATUM = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "long" });

export function AufgabenPostVorschlaege({ onChanged }: { onChanged: (task: Task | null) => void }) {
  const [items, setItems] = useState<AufgabenPostVorschlag[] | null>(null);
  const [fehler, setFehler] = useState(false);
  const [meldung, setMeldung] = useState("");
  const [arbeitet, setArbeitet] = useState<string | null>(null);
  const version = useRef(0);

  function laden() {
    const eigene = ++version.current;
    api.aufgabenPostVorschlaege().then(antwort => {
      if (eigene !== version.current) return;
      setItems(antwort.items); setFehler(false);
    }).catch(() => { if (eigene === version.current) setFehler(true); });
  }
  useEffect(() => { laden(); window.addEventListener("focus", laden); return () => { version.current++; window.removeEventListener("focus", laden); }; }, []);

  async function entscheiden(v: AufgabenPostVorschlag, annehmen: boolean) {
    if (arbeitet) return;
    setArbeitet(v.id); setMeldung("");
    try {
      const task = annehmen ? await api.aufgabenPostAnnehmen(v.id) : (await api.aufgabenPostVerwerfen(v.id), null);
      setItems(current => (current ?? []).filter(item => item.id !== v.id));
      setMeldung(annehmen ? angenommenText(v) : "Verworfen. Diese Mail gilt für die Aufgabe nicht mehr als Antwort.");
      onChanged(task);
    } catch {
      setMeldung("Das ließ sich gerade nicht merken. Bitte neu laden und noch einmal versuchen.");
      laden();
    } finally {
      setArbeitet(null);
    }
  }

  if (!meldung && !fehler && (!items || items.length === 0)) return null;
  return <section className="task-source aufgaben-post" aria-label="Aus deiner Post">
    <h2>Aus deiner Post{items && items.length ? ` · ${items.length}` : ""}</h2>
    <p>Eine Mail passt zu einer Aufgabe, aber nicht sicher genug, um sie von selbst abzulegen. Ein Klick entscheidet; nichts geht nach draußen.</p>
    {meldung ? <p role="status">{meldung}</p> : null}
    {fehler ? <p role="alert">Die Vorschläge sind gerade nicht erreichbar. <button type="button" onClick={laden}>Erneut laden</button></p> : null}
    {items?.map(v => <article key={v.id} className="aufgaben-post-vorschlag" aria-busy={arbeitet === v.id}>
      <strong>{v.statement}</strong>
      <small>{v.satz}</small>
      <div className="task-suggestion-actions">
        <button type="button" className="primary-action" disabled={arbeitet !== null} onClick={() => void entscheiden(v, true)}>{annehmenText(v)}</button>
        <button type="button" className="secondary-action" disabled={arbeitet !== null} onClick={() => void entscheiden(v, false)}>Nein</button>
        <ProfileSource kind="episode" id={v.mail.episode_id} label={`Mail öffnen: ${v.mail.titel || "(kein Betreff)"} vom ${DATUM.format(new Date(v.mail.datum))}`} quiet readOnly allowIgnore={false} />
      </div>
    </article>)}
  </section>;
}
