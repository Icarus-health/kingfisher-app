// Die Navigation am Handy (Persona-Prüfung, Paket H, H2, 27.10.2026): das Modell ohne Browser.
//
// Bis 1.0.29 war sie unter 700 px ein Streifen oben aus sieben Symbolen ohne Beschriftung (nur der aktive Bereich trug
// seinen Namen), der mit der Seite wegrollte. Jetzt steht unten eine feste Leiste wie am iPhone: vier Ziele mit Zeichen
// und Namen und „Mehr“ für den Rest. Am Desktop bleibt die Seitenleiste, wie sie ist.
//
// Welche vier? Die, die man unterwegs braucht und die eine Entscheidung abnehmen: Heute (was ist dran), Gespräche
// (Kingfisher fragen), Aufgaben (abhaken, „+ Aufgabe“), Kalender (wann, wo). Nachrichten hat das Handy selbst, und was
// daraus wichtig ist, steht auf Heute; Gedächtnis (Menschen, Dokumente, Suche) fragt man meist über Gespräche ab;
// Einstellungen braucht man selten. Diese drei liegen unter „Mehr“, jedes mit einem Satz, was darin steht.

import type { NavigationLabel } from "./ui";

export type LeistenZiel = { label: NavigationLabel | "Einstellungen"; zeichen: string; pfad: string };
export type MehrZiel = LeistenZiel & { satz: string };

/** Höchstens fünf Plätze: vier Ziele und „Mehr“. */
export const LEISTE: LeistenZiel[] = [
  { label: "Heute", zeichen: "house", pfad: "/today" },
  { label: "Gespräche", zeichen: "message-circle", pfad: "/conversations" },
  { label: "Aufgaben", zeichen: "folder", pfad: "/vorhaben" },
  { label: "Kalender", zeichen: "calendar-days", pfad: "/calendar" },
];

export const MEHR: MehrZiel[] = [
  { label: "Nachrichten", zeichen: "mail", pfad: "/nachrichten", satz: "Post aus deinen Postfächern" },
  { label: "Gedächtnis", zeichen: "brain", pfad: "/memory", satz: "Menschen, Dokumente und Suche" },
  { label: "Einstellungen", zeichen: "settings", pfad: "/settings", satz: "Zugänge, Sicherung, was Kingfisher darf" },
];

/** Steht die aktive Seite unter „Mehr“? Dann trägt „Mehr“ die Markierung und sagt, welche es ist. */
export function aktivUnterMehr(aktiv: string): MehrZiel | null {
  return MEHR.find(ziel => ziel.label === aktiv) ?? null;
}
