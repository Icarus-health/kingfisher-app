// Der leere Zustand im Gedächtnis sagt, woher Einträge kommen, und führt mit einem Klick dorthin (Fremdprobe, Befund 28).
// Ein Satz, ein Verweis; überall derselbe, damit Menschen, Projekte, Orte und Themen nicht je eigene Wege erklären.

export const LEER_SATZ = "Einträge entstehen aus deinen Quellen: aus Mails, Terminen und Dokumenten, die du verbindest.";
export const LEER_ZIEL = "/settings#zugaenge";

export function GedaechtnisLeer({ satz = LEER_SATZ }: { satz?: string }) {
  return <p className="gedaechtnis-leer">{satz} <a className="text-action" href={LEER_ZIEL}>Quellen verbinden →</a></p>;
}
