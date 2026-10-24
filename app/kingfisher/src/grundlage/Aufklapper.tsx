import type { ReactNode } from "react";

/** Aufklapper: nur für echtes Nebenwissen. Der Pfeil dreht sich beim Öffnen (Grundlage.css, „details > summary“);
 * rechts optional eine leise Angabe wie eine Anzahl. */
export function Aufklapper({ titel, neben, offen, onToggle, children, className }: {
  titel: ReactNode;
  neben?: ReactNode;
  /** Anfangs offen. */
  offen?: boolean;
  onToggle?: (offen: boolean) => void;
  children: ReactNode;
  className?: string;
}) {
  return <details className={["g-aufklapper", className].filter(Boolean).join(" ")} open={offen}
    onToggle={onToggle ? e => onToggle(e.currentTarget.open) : undefined}>
    <summary>
      <span className="g-aufklapper-titel">{titel}</span>
      {neben ? <span className="g-aufklapper-neben">{neben}</span> : null}
    </summary>
    <div className="g-aufklapper-inhalt">{children}</div>
  </details>;
}
