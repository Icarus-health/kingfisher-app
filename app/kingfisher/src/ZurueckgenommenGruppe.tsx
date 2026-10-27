import { useEffect, useRef, useState } from "react";
import { api, type ZurueckgenommeneAufgabe } from "./api";
import { Gruppe, Zeile, zeigeHinweis, zitat } from "./grundlage";
import { ANLAGE_ZURUECK, zurueckgenommenNeben } from "./aufgabenVonSelbst";

/**
 * „Zurückgenommen“ unter „Erledigt“ (Persona-Prüfung, Paket Z2): Was Kingfisher selbst angelegt und du zurückgenommen
 * hast, bleibt hier wiederherstellbar, auch Tage später, nicht nur die Sekunden des Hinweises. Keine neue Seite, eine
 * Gruppe in der bestehenden Liste; ohne Einträge steht nichts da.
 */
export function ZurueckgenommenGruppe({ revision, onChanged }: { revision: number; onChanged: () => void }) {
  const [eintraege, setEintraege] = useState<ZurueckgenommeneAufgabe[]>([]);
  const [arbeitet, setArbeitet] = useState<string | null>(null);
  const [fehler, setFehler] = useState("");
  const [stand, setStand] = useState(0);
  const version = useRef(0);
  useEffect(() => {
    const eigene = ++version.current;
    api.aufgabenZurueckgenommen().then(antwort => { if (eigene === version.current) setEintraege(antwort.aufgaben); })
      .catch(() => { if (eigene === version.current) setEintraege([]); });
    return () => { version.current++; };
  }, [revision, stand]);
  if (!eintraege.length) return null;

  async function wiederherstellen(eintrag: ZurueckgenommeneAufgabe) {
    if (arbeitet) return;
    setArbeitet(eintrag.id); setFehler("");
    try {
      await api.aufgabeVonSelbstWiederherstellen(eintrag.id);
      setStand(n => n + 1); onChanged();
      zeigeHinweis({ text: `${zitat(eintrag.title)} ist wieder da.`, danach: ANLAGE_ZURUECK,
        rueckgaengig: async () => { await api.aufgabeVonSelbstZuruecknehmen(eintrag.id); setStand(n => n + 1); onChanged(); } });
    } catch {
      setFehler("Das ließ sich gerade nicht wiederherstellen. Bitte erneut versuchen.");
    } finally {
      setArbeitet(null);
    }
  }

  return <Gruppe className="workspace-task-group task-zurueckgenommen" titel="Zurückgenommen" stufe={3}>
    {fehler ? <p className="tasks-error" role="alert">{fehler}</p> : null}
    {eintraege.map(eintrag => <Zeile key={eintrag.id} titel={eintrag.title} neben={zurueckgenommenNeben(eintrag)}
      zusatz={<button type="button" className="g-knopf-schlicht g-kompakt" disabled={arbeitet !== null}
        aria-label={`Wiederherstellen: ${eintrag.title}`} onClick={() => void wiederherstellen(eintrag)}>Wiederherstellen</button>} />)}
  </Gruppe>;
}
