import { Sidebar } from "./chrome";
import { KnowledgeQuestions } from "./KnowledgeQuestions";
import { WasAufgefallenIst } from "./BefundeAnsicht";

/** Full-page home for durable knowledge questions and source-backed file findings. */
export function ReviewPage({recentConversation}: {recentConversation: string | null}) {
  return <div className="shell tasks-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="tasks-page review-page">
      <header className="tasks-heading">
        <p className="eyebrow">GEDÄCHTNIS</p>
        <h1>Prüfen und entscheiden</h1>
      </header>
      <p>Hier stehen offene Fragen zu gespeicherten Angaben und Hinweise aus den Akten. Jede Entscheidung bleibt an den sichtbaren Quellenstand gebunden.</p>
      <p><a className="today-text-link" href="/today">Zurück zu Heute →</a> · <a className="today-text-link" href="/memory?people=review">Unklare Personen prüfen →</a> · <a className="today-text-link" href="/vorhaben?pruefen=1">Aufgabenvorschläge prüfen →</a></p>
      <KnowledgeQuestions active />
      <WasAufgefallenIst active />
    </main>
  </div>;
}
