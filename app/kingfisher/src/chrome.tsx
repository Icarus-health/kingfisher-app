import { ASSET, NAV, navigate, type NavigationLabel } from "./ui";
import { InterfaceIcon } from "./InterfaceIcon";
import { LiveClock } from "./LiveClock";

export function Sidebar({ active, briefingOpen = false, onToday, recentConversation, navigationDisabled = false }: {
  active: NavigationLabel | "Einstellungen";
  briefingOpen?: boolean;
  onToday?: () => void;
  recentConversation: string | null;
  navigationDisabled?: boolean;
}) {
  function activate(label: NavigationLabel) {
    if (label === "Heute") {
      if (active === "Heute" && onToday) onToday();
      else navigate("/today");
    }
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
      <nav aria-label="Hauptnavigation">
        {NAV.map(([label, image]) => {
          const available = label === "Kalender" || label === "Heute" || label === "Gedächtnis" || label === "Gespräche" || label === "Aufgaben" || label === "Nachrichten";
          return (
            <button
              aria-expanded={label === "Heute" && active === "Heute" ? briefingOpen : undefined}
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
        <button className={`nav-item ${active === "Einstellungen" ? "active" : ""}`} disabled={navigationDisabled} onClick={() => navigate("/settings")} type="button">
          <InterfaceIcon name="settings" />
          <span>Einstellungen</span>
        </button>
      </div>
    </aside>
  );
}
