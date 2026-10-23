import { useCallback, useState } from "react";
import { Sidebar } from "./chrome";
import { KnowledgeQuestions } from "./KnowledgeQuestions";
import { WasAufgefallenIst } from "./BefundeAnsicht";

/** Full-page home for durable knowledge questions and source-backed file findings. Leere Abschnitte stehen nicht da;
 * ist alles leer, sagt ein Satz das. Die seltenen Prüfwege stehen als eine leise Zeile darunter. */
export function ReviewPage({recentConversation}: {recentConversation: string | null}) {
  const [leer, setLeer] = useState<{klaerungen: boolean; befunde: boolean}>({klaerungen: false, befunde: false});
  const klaerungenLeer = useCallback((wert: boolean) => setLeer(alt => alt.klaerungen === wert ? alt : {...alt, klaerungen: wert}), []);
  const befundeLeer = useCallback((wert: boolean) => setLeer(alt => alt.befunde === wert ? alt : {...alt, befunde: wert}), []);
  return <div className="shell tasks-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="tasks-page review-page">
      <header className="tasks-heading">
        <p className="eyebrow">GEDÄCHTNIS</p>
        <h1>Prüfen und entscheiden</h1>
      </header>
      {leer.klaerungen && leer.befunde ? <p className="review-leer" role="status">Nichts zu prüfen.</p> : null}
      <KnowledgeQuestions active leerAusblenden onLeer={klaerungenLeer} />
      <WasAufgefallenIst active leerAusblenden onLeer={befundeLeer} />
      <p className="review-weitere">Außerdem prüfen: <a className="today-text-link" href="/memory?people=review">Unklare Personen</a> · <a className="today-text-link" href="/vorhaben?pruefen=1">Aufgabenvorschläge</a> · <a className="today-text-link" href="/memory?view=support">Gespeicherte Angaben</a></p>
    </main>
  </div>;
}
