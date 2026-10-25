// Bausteine der Gestaltungsgrundlage (docs/16-gestaltung.md „Grundlage vom 23.10.2026“). Nur Darstellung, keine
// Seitenlogik; die Stile stehen in src/Grundlage.css. Knöpfe sind Klassen: g-knopf, g-knopf-getoent, g-knopf-schlicht.
export { Seitenkopf } from "./Seitenkopf";
export { Gruppe } from "./Gruppe";
export { Zeile } from "./Zeile";
export { Segmente, raenderMarkieren, type Segment } from "./Segmente";
export { Leer } from "./Leer";
export { Aufklapper } from "./Aufklapper";
export { Schalter } from "./Schalter";
export { Unterkopf } from "./Unterkopf";
export { Bestaetigung } from "./Bestaetigung";
export { segmentNachTaste, segmentImFokus } from "./segmentTasten.ts";
export { HinweisAnzeige } from "./Hinweis";
export { zeigeHinweis, zitat, hinweise, HinweisOrt, type HinweisDaten } from "./hinweisOrt.ts";
