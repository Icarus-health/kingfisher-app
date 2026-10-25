import { useEffect, useRef, useState } from "react";
import { api, type AufgabenPostVorschlag, type Task } from "./api";
import { ProfileSource } from "./ProfileSource";
import { angenommenText, annehmenText } from "./aufgabenPost";
import { Gruppe, zeigeHinweis } from "./grundlage";
import { POST_ZURUECK } from "./aufgabenHinweis";

// Aufgaben folgen der Post: „Erledigt?“ und „Wieder bei dir?“ dort, wo auch die erkannten Aufgaben stehen. Ein Klick
// nimmt an (dieselbe Änderung wie der Durchlauf, mit Grund und Rückgängig in der Liste); der Hinweis unten sagt es und
// nimmt mit „Rückgängig“ über `/tasks/{id}/rueckgaengig` zurück. Einer verwirft (Aufgabe und Mail bleiben getrennt);
// dafür gibt es kein Zurück, der Hinweis sagt nur, was passiert ist. Nichts davon ist ein Fakt im Bestand; der Sidecar schlägt nur vor (`aufgaben_post.py`).

const DATUM = new Intl.DateTimeFormat("de-DE", { day: "numeric", month: "long" });

export function AufgabenPostVorschlaege({ onChanged }: { onChanged: (task: Task | null) => void }) {
  const [items, setItems] = useState<AufgabenPostVorschlag[] | null>(null);
  const [fehler, setFehler] = useState(false);
  const [meldung, setMeldung] = useState("");  // nur noch für Fehler: Sie gehören an die Gruppe, nicht nach unten.
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
      onChanged(task);
      zeigeHinweis(annehmen && task ? { text: angenommenText(v), danach: POST_ZURUECK,
        rueckgaengig: async () => { await api.taskRueckgaengig(task.id); onChanged(null); laden(); } }
        : { text: "Verworfen. Diese Mail gilt für die Aufgabe nicht mehr als Antwort." });
    } catch {
      setMeldung("Das ließ sich gerade nicht merken. Bitte neu laden und noch einmal versuchen.");
      laden();
    } finally {
      setArbeitet(null);
    }
  }

  if (!meldung && !fehler && (!items || items.length === 0)) return null;
  // Eine Gruppe wie die Liste darunter: klein die Überschrift, je Vorschlag eine Zeile mit Satz und zwei Antworten,
  // darunter als Fußnote der eine Satz, der zusichert, dass nichts nach draußen geht.
  return <Gruppe className="aufgaben-post" titel={<>Aus deiner Post{items && items.length ? <span className="aufgaben-post-zahl">{items.length}</span> : null}</>}
    fussnote="Nicht sicher genug, um es selbst abzulegen. Nichts geht nach draußen.">
    {meldung ? <p className="aufgaben-post-satz" role="status">{meldung}</p> : null}
    {fehler ? <p className="aufgaben-post-satz aufgaben-post-fehler" role="alert">Die Vorschläge sind gerade nicht erreichbar. <button type="button" className="text-action" onClick={laden}>Erneut laden</button></p> : null}
    {items?.map(v => <article key={v.id} className="aufgaben-post-vorschlag" aria-busy={arbeitet === v.id}>
      <strong>{v.statement}</strong>
      <small>{v.satz}</small>
      <div className="task-suggestion-actions">
        <button type="button" className="secondary-action g-kompakt" disabled={arbeitet !== null} onClick={() => void entscheiden(v, true)}>{annehmenText(v)}</button>
        <button type="button" className="text-action" disabled={arbeitet !== null} onClick={() => void entscheiden(v, false)}>Nein</button>
        <ProfileSource kind="episode" id={v.mail.episode_id} label={`Mail öffnen: ${v.mail.titel || "(kein Betreff)"} vom ${DATUM.format(new Date(v.mail.datum))}`} quiet readOnly allowIgnore={false} />
      </div>
    </article>)}
  </Gruppe>;
}
