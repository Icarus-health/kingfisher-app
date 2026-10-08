import { Sidebar } from './chrome';
import { GoalControls } from './GoalControls';
import { HabitControls } from './HabitControls';

/** A single working surface over the existing goals, habits and learning stores. */
export function DevelopmentPage({recentConversation}: {recentConversation: string | null}) {
  return <div className="shell tasks-shell">
    <Sidebar active="Aufgaben" recentConversation={recentConversation} />
    <main className="tasks-page development-page">
      <header className="tasks-heading"><div><p className="eyebrow">DEIN ALLTAG</p><h1>Persönliche Entwicklung</h1></div></header>
      <p>Was dir wichtig ist, was du festhältst und was du daraus lernen möchtest.</p>
      <nav className="development-links" aria-label="Persönlicher Arbeitsbereich">
        <a className="today-text-link" href="/today">Zurück zu Heute →</a>
        <a className="today-text-link" href="/vorhaben">Nächste Schritte als Aufgaben →</a>
        <a className="today-text-link" href="/memory?area=health">Gesundheitsquellen →</a>
        <a className="today-text-link" href="/review">Offene Angaben prüfen →</a>
      </nav>
      <GoalControls />
      <HabitControls initiallyOpen />
    </main>
  </div>;
}
