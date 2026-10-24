import type { ComponentProps, ReactNode } from "react";
import { InterfaceIcon } from "../InterfaceIcon";

type Zeichen = ComponentProps<typeof InterfaceIcon>["name"];

/** Leer: der leere Zustand. Ein Zeichen, ein Satz, höchstens ein Knopf, mittig. Keine leeren Gruppen, keine Nullen. */
export function Leer({ satz, zeichen, aktion, className }: {
  /** Genau ein Satz, etwa „Nichts wartet auf dich.“ */
  satz: ReactNode;
  zeichen?: Zeichen;
  /** Höchstens ein Knopf. */
  aktion?: ReactNode;
  className?: string;
}) {
  return <div className={["g-leer", className].filter(Boolean).join(" ")}>
    {zeichen ? <span className="g-leer-zeichen" aria-hidden="true"><InterfaceIcon name={zeichen} /></span> : null}
    <p className="g-leer-satz">{satz}</p>
    {aktion ? <div className="g-leer-aktion">{aktion}</div> : null}
  </div>;
}
