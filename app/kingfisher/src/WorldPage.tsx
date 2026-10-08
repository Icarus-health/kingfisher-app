import { Sidebar } from "./chrome";
import { WorldControls } from "./WorldControls";

export function WorldPage({ recentConversation }: { recentConversation: string | null }) {
  return <div className="shell tasks-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="tasks-page development-page">
      <header className="tasks-heading"><div><p className="eyebrow">ÖFFENTLICHE QUELLEN</p><h1>Öffentliches Wissen</h1></div></header>
      <p>Verwalte die Seiten, die du selbst eingetragen hast. Kingfisher zeigt den gespeicherten Auszug mit Abrufzeit und Herkunft. Diese Texte bleiben Quellenberichte und werden nicht automatisch als persönliche Angaben übernommen.</p>
      <nav className="development-links" aria-label="Öffentlicher Wissensbereich">
        <a className="today-text-link" href="/today">Zurück zu Heute →</a>
        <a className="today-text-link" href="/settings#technik-quellen">Einstellungen für Quellen öffnen →</a>
      </nav>
      <WorldControls initiallyOpen />
    </main>
  </div>;
}
