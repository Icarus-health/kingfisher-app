import { useCallback, useEffect, useRef, useState } from "react";
import { api, type QuellenBezuege } from "./api";
import {MemoryEntityLink} from "./MemoryEntityLink";
import { zeigeHinweis } from "./grundlage";

const GRUNDLAGE: Record<string, string> = { anker: "aus Adresse oder Zuordnung", modell: "im Text erkannt", nutzer: "von dir" };

/** Wozu gehört diese Quelle? Die Sachen (Personen, Organisationen, Projekte, Orte, Themen), mit Grundlage und Korrektur mit einem Klick. */
export function SourceBezuege({ id, readOnly = false }: { id: string; readOnly?: boolean }) {
  const [data, setData] = useState<QuellenBezuege | null>(null);
  const [fehler, setFehler] = useState(false);
  const [beschaeftigt, setBeschaeftigt] = useState(false);
  const version = useRef(0);
  const laden = useCallback(async () => {
    const eigene = ++version.current;
    try {
      const next = await api.quellenBezuege(id);
      if (eigene === version.current) { setData(next); setFehler(false); }
    } catch { if (eigene === version.current) setFehler(true); }
  }, [id]);
  useEffect(() => { setData(null); setFehler(false); void laden(); }, [laden]);
  // Noch nicht berechnet: einmal still nachladen.
  useEffect(() => {
    if (!data || data.berechnet) return;
    const timer = window.setTimeout(() => void laden(), 3000);
    return () => window.clearTimeout(timer);
  }, [data, laden]);

  // Jede Korrektur antwortet mit dem Hinweis unten; „Rückgängig“ geht über die Gegenroute (setzen ↔ entfernen) zurück
  // auf den Stand vor dem Klick (V4).
  async function aendern(aufgabe: () => Promise<QuellenBezuege>, satz: string, zurueck: () => Promise<QuellenBezuege>) {
    if (readOnly || beschaeftigt) return;
    setBeschaeftigt(true); setFehler(false);
    try {
      setData(await aufgabe());
      zeigeHinweis({ text: satz, rueckgaengig: async () => { setData(await zurueck()); } });
    } catch { setFehler(true); } finally { setBeschaeftigt(false); }
  }

  if (fehler && !data) return <section aria-label="Bezüge"><h4>Wozu die Quelle gehört</h4><p role="alert">Die Bezüge konnten gerade nicht geladen werden.</p></section>;
  if (!data) return <section aria-label="Bezüge"><h4>Wozu die Quelle gehört</h4><p role="status">Wird geladen …</p></section>;
  const leer = !data.bezuege.length && !data.offen.length && !data.abgelehnt.length;
  return <section aria-label="Bezüge">
    <h4>Wozu die Quelle gehört</h4>
    {fehler ? <p role="alert">Die Änderung konnte nicht gespeichert werden.</p> : null}
    {leer ? <p>{data.berechnet ? "Zu dieser Quelle ist noch nichts zugeordnet." : "Wird noch berechnet …"}</p> : null}
    {data.bezuege.length ? <ul>{data.bezuege.map(bezug => <li key={bezug.sache}>
      <MemoryEntityLink className="text-action" href={`/memory/akte/${encodeURIComponent(bezug.sache)}`}>{bezug.name}</MemoryEntityLink>
      {" · "}{bezug.art_text} · {bezug.grundlagen.map(g => GRUNDLAGE[g] ?? g).join(", ")}
      {bezug.zitate.map((zitat, index) => <blockquote key={index}>{zitat}</blockquote>)}
      {!readOnly ? <>{" "}<button type="button" className="text-action" disabled={beschaeftigt} onClick={() => void aendern(() => api.bezugSetzen(id, bezug.sache, "nicht"), `${bezug.name} gehört nicht mehr dazu.`,
        () => bezug.grundlagen.includes("nutzer") ? api.bezugSetzen(id, bezug.sache, "zu") : api.bezugEntfernen(id, bezug.sache))}>Gehört nicht dazu</button></> : null}
    </li>)}</ul> : null}
    {data.offen.length ? <ul>{data.offen.map((offen, index) => <li key={index}>
      <strong>Wer ist gemeint?</strong> {offen.art_text}{offen.zitat ? <> „{offen.zitat}“</> : null} passt zu mehreren Einträgen.
      {!readOnly ? <div>{offen.kandidaten.map(kandidat => <button key={kandidat.sache} type="button" className="text-action" disabled={beschaeftigt} onClick={() => void aendern(() => api.bezugSetzen(id, kandidat.sache, "zu"), `${kandidat.name} zugeordnet.`, () => api.bezugEntfernen(id, kandidat.sache))}>{kandidat.name}</button>)}</div> : null}
    </li>)}</ul> : null}
    {data.abgelehnt.length ? <ul>{data.abgelehnt.map(abgelehnt => <li key={abgelehnt.sache}>
      <s>{abgelehnt.name}</s> · von dir ausgeschlossen
      {!readOnly ? <button type="button" className="text-action" disabled={beschaeftigt} onClick={() => void aendern(() => api.bezugEntfernen(id, abgelehnt.sache), `${abgelehnt.name}: nicht mehr ausgeschlossen.`, () => api.bezugSetzen(id, abgelehnt.sache, "nicht"))}>Doch zuordnen</button> : null}
    </li>)}</ul> : null}
    {data.veraltet.length ? <p role="status">Eine frühere Zuordnung von dir gilt nicht mehr, weil sich die Quelle geändert hat.</p> : null}
  </section>;
}
