import './TaskRetryReview.css';

import { Sidebar } from './chrome';
import { GoalControls } from './GoalControls';
import { HabitControls } from './HabitControls';
import { Gruppe, Seitenkopf, Zeile } from './grundlage';

/** Eine Arbeitsfläche über Zielen, Gewohnheiten und Lernen: großer Titel, eine Zeile, die Ziele, Gewohnheiten und
 * Lernen offen, am Ende leise die Wege weiter (Aufgaben, Gesundheit, Prüfen). Heute steht in der Seitenleiste. */
export function DevelopmentPage({recentConversation}: {recentConversation: string | null}) {
  return <div className="shell tasks-shell">
    <Sidebar active="Aufgaben" recentConversation={recentConversation} />
    <main className="tasks-page development-page aufgaben">
      <Seitenkopf className="tasks-heading" titel="Persönliche Entwicklung" zeile="Was dir wichtig ist, was du festhältst und was du daraus lernst." />
      <GoalControls />
      <HabitControls initiallyOpen />
      <Gruppe className="development-weiter" titel="Weiter">
        <Zeile href="/vorhaben" titel="Nächste Schritte als Aufgaben" />
        <Zeile href="/wellbeing" titel="Gesundheit" />
        <Zeile href="/review" titel="Offene Angaben prüfen" />
      </Gruppe>
    </main>
  </div>;
}
