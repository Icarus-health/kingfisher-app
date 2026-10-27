import { useEffect, useRef, useState } from "react";
import { navigate, type NavigationLabel } from "./ui";
import { InterfaceIcon, type ZeichenName } from "./InterfaceIcon";
import { LEISTE, MEHR, aktivUnterMehr } from "./handyZiele";

/**
 * Am Handy: eine feste Leiste unten (über `safe-area-inset-bottom`), jedes Ziel mit Zeichen und Namen, mindestens
 * 44 × 44 px. „Mehr“ klappt darüber die übrigen drei auf (Nachrichten, Gedächtnis, Einstellungen), je mit einem Satz.
 * Escape oder ein Tipp daneben klappt zu, der Fokus kehrt auf „Mehr“ zurück. Steht die Seite selbst unter „Mehr“,
 * trägt „Mehr“ die Markierung und nennt sie für Vorleser.
 */
export function HandyLeiste({ active, gesperrt }: { active: NavigationLabel | "Einstellungen"; gesperrt: boolean }) {
  const [offen, setOffen] = useState(false);
  const mehrKnopf = useRef<HTMLButtonElement | null>(null);
  const leiste = useRef<HTMLElement | null>(null);
  const unterMehr = aktivUnterMehr(active);
  useEffect(() => {
    if (!offen || typeof document === "undefined") return;
    const daneben = (e: PointerEvent) => { if (!leiste.current?.contains(e.target as Node)) setOffen(false); };
    const taste = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      e.preventDefault();
      setOffen(false);
      mehrKnopf.current?.focus();
    };
    document.addEventListener("pointerdown", daneben, true);
    document.addEventListener("keydown", taste);
    return () => { document.removeEventListener("pointerdown", daneben, true); document.removeEventListener("keydown", taste); };
  }, [offen]);
  function gehe(pfad: string) {
    setOffen(false);
    navigate(pfad);
  }
  return (
    <nav aria-label="Hauptnavigation" className="handy-leiste" ref={leiste}>
      {LEISTE.map(ziel => (
        <button key={ziel.label} type="button" className={`handy-ziel${active === ziel.label ? " aktiv" : ""}`}
          aria-current={active === ziel.label ? "page" : undefined} disabled={gesperrt} onClick={() => gehe(ziel.pfad)}>
          <InterfaceIcon name={ziel.zeichen as ZeichenName} />
          <span>{ziel.label}</span>
        </button>
      ))}
      <button ref={mehrKnopf} type="button" className={`handy-ziel${unterMehr ? " aktiv" : ""}`} aria-expanded={offen}
        aria-controls="handy-mehr" disabled={gesperrt} onClick={() => setOffen(o => !o)}>
        <InterfaceIcon name="mehr" />
        <span>Mehr</span>
        {unterMehr ? <span className="visually-hidden">{`, gerade ${unterMehr.label}`}</span> : null}
      </button>
      <div id="handy-mehr" className="handy-mehr" hidden={!offen}>
        {MEHR.map(ziel => (
          <button key={ziel.label} type="button" className={`handy-mehr-ziel${active === ziel.label ? " aktiv" : ""}`}
            aria-current={active === ziel.label ? "page" : undefined} disabled={gesperrt} onClick={() => gehe(ziel.pfad)}>
            <InterfaceIcon name={ziel.zeichen as ZeichenName} />
            <span className="handy-mehr-text"><strong>{ziel.label}</strong><small>{ziel.satz}</small></span>
          </button>
        ))}
      </div>
    </nav>
  );
}
