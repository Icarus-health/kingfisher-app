import { Sidebar } from "./chrome";
import { WorldControls } from "./WorldControls";
import { Seitenkopf } from "./grundlage";
import "./Gedaechtnis.css";

/** Öffentliches Wissen: großer Titel, eine Zeile, dann die neue Quelle und deine Quellen als Gruppen. */
export function WorldPage({ recentConversation }: { recentConversation: string | null }) {
  return <div className="shell tasks-shell">
    <Sidebar active="Gedächtnis" recentConversation={recentConversation} />
    <main className="tasks-page development-page welt-page">
      <Seitenkopf titel="Öffentliches Wissen" zeile="Seiten, die du selbst eingetragen hast, mit Abrufzeit und Herkunft."
        aktionen={<a className="g-knopf-schlicht" href="/settings#technik-quellen">Einstellungen</a>} />
      <WorldControls initiallyOpen seite />
    </main>
  </div>;
}
