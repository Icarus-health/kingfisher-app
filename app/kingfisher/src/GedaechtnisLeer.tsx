// Der leere Zustand im Gedächtnis sagt, woher Einträge kommen, und führt mit einem Klick dorthin (Fremdprobe, Befund 28).
// Ein Satz, ein Verweis; überall derselbe, damit Menschen, Projekte, Orte und Themen nicht je eigene Wege erklären.
// Gestalt wie der Baustein `Leer` (Zeichen, ein Satz, ein Knopf), dazu der Verweis als getönter Knopf.
import { InterfaceIcon } from "./InterfaceIcon";

export const LEER_SATZ = "Einträge entstehen aus deinen Quellen: aus Mails, Terminen und Dokumenten, die du verbindest.";
export const LEER_ZIEL = "/settings#zugaenge";

export function GedaechtnisLeer({ satz = LEER_SATZ }: { satz?: string }) {
  return <div className="g-leer gedaechtnis-leer">
    <span className="g-leer-zeichen" aria-hidden="true"><InterfaceIcon name="brain" /></span>
    <p className="g-leer-satz">{satz}</p>
    <a className="g-knopf-getoent g-leer-aktion" href={LEER_ZIEL}>Quellen verbinden</a>
  </div>;
}
