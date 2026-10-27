import { ASSET, NAV, navigate, type NavigationLabel } from "./ui";
import { InterfaceIcon } from "./InterfaceIcon";
import { LiveClock } from "./LiveClock";
import { HandyLeiste } from "./HandyLeiste";

// Heute ist das Briefing (Paket U, H1): „Heute“ führt immer nach Heute; keine Schublade, die die Leiste sperrt.
// navigationDisabled sperrt die Leiste, solange eine Seite etwas speichert, das nicht verloren gehen darf (Gedächtnis).
//
// Zwei Gestalten derselben Navigation, je Breite genau eine sichtbar (Seitenbreite.css): breit die Seitenleiste (ab 701 px,
// bis 900 px als Streifen oben), am Handy die feste Leiste unten mit vier Zielen und „Mehr“ (Paket H, H2; `HandyLeiste.tsx`).
// Die jeweils andere ist `display: none` und damit auch für Vorleser und Tab nicht da.
export function Sidebar({ active, navigationDisabled = false }: {
  active: NavigationLabel | "Einstellungen";
  recentConversation: string | null;
  navigationDisabled?: boolean;
}) {
  function activate(label: NavigationLabel) {
    if (label === "Heute") navigate("/today");
    if (label === "Gespräche") navigate("/conversations");
    if (label === "Aufgaben") navigate("/vorhaben");
    if (label === "Gedächtnis") navigate("/memory");
    if (label === "Kalender") navigate("/calendar");
    if (label === "Nachrichten") navigate("/nachrichten");
  }

  return (
    <aside className="sidebar">
      <img className="brand-lockup" src={ASSET.brand} alt="Kingfisher" />
      <LiveClock />
      <nav aria-label="Hauptnavigation" className="seiten-navigation">
        {NAV.map(([label, image]) => {
          const available = label === "Kalender" || label === "Heute" || label === "Gedächtnis" || label === "Gespräche" || label === "Aufgaben" || label === "Nachrichten";
          return (
            <button
              aria-current={active === label ? "page" : undefined}
              className={`nav-item ${active === label ? "active" : ""}`}
              disabled={!available || navigationDisabled}
              key={label}
              onClick={() => activate(label)}
              type="button"
            >
              <InterfaceIcon name={image} />
              <span>{label}</span>
            </button>
          );
        })}
      </nav>
      <div className="sidebar-foot">
        <button aria-current={active === "Einstellungen" ? "page" : undefined} className={`nav-item ${active === "Einstellungen" ? "active" : ""}`} disabled={navigationDisabled} onClick={() => navigate("/settings")} type="button">
          <InterfaceIcon name="settings" />
          <span>Einstellungen</span>
        </button>
      </div>
      <HandyLeiste active={active} gesperrt={navigationDisabled} />
    </aside>
  );
}
