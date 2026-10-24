import { useCallback, useState } from "react";
import { Sidebar } from "./chrome";
import { KnowledgeQuestions } from "./KnowledgeQuestions";
import { WasAufgefallenIst } from "./BefundeAnsicht";
import { Gruppe, Seitenkopf, Zeile } from "./grundlage";
import { InterfaceIcon } from "./InterfaceIcon";
import "./Gedaechtnis.css";

/** Full-page home for durable knowledge questions and source-backed file findings. Leere Abschnitte stehen nicht da;
 * ist alles leer, sagt ein Satz das. Die seltenen Prüfwege stehen als eine leise Zeile darunter. */
export function ReviewPage({recentConversation}: {recentConversation: string | null}) {
  const [leer, setLeer] = useState<{klaerungen: boolean; befunde: boolean}>({klaerungen: false, befunde: false});
  const klaerungenLeer = useCallback((wert: boolean) => setLeer(alt => alt.klaerungen === wert ? alt : {...alt, klaerungen: wert}), []);
  const befundeLeer = useCallback((wert: boolean) => setLeer(alt => alt.befunde === wert ? alt : {...alt, befunde: wert}), []);
  return <div className="shell tasks-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="tasks-page review-page">
      <Seitenkopf titel="Prüfen und entscheiden" />
      {leer.klaerungen && leer.befunde ? <div className="g-leer review-leer-flaeche">
        <span className="g-leer-zeichen" aria-hidden="true"><InterfaceIcon name="check" /></span>
        <p className="review-leer g-leer-satz" role="status">Nichts zu prüfen.</p>
      </div> : null}
      <KnowledgeQuestions active leerAusblenden onLeer={klaerungenLeer} />
      <WasAufgefallenIst active leerAusblenden onLeer={befundeLeer} />
      {/* Die seltenen Prüfwege: eine Gruppe ganzer Zeilen statt einer Zeile kleiner Verweise. */}
      <Gruppe titel="Außerdem prüfen" className="review-weitere">
        <Zeile href="/memory?people=review" symbol={<InterfaceIcon name="people" />} titel="Unklare Personen" />
        <Zeile href="/vorhaben?pruefen=1" symbol={<InterfaceIcon name="check" />} titel="Aufgabenvorschläge" />
        <Zeile href="/memory?view=support" symbol={<InterfaceIcon name="brain" />} titel="Gespeicherte Angaben" />
      </Gruppe>
    </main>
  </div>;
}
