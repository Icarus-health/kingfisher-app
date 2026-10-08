// Reine Logik zum Einlesen der Mails im Assistenten (ohne React, testbar mit node --test).
import type {MailIntakeAccount} from "../api";
import {deriveIntakeProgress} from "../mailIntakeProgress.ts";

const zahl = (wert: number) => wert.toLocaleString("de-DE");

/** Wohin der Satz verweist, wenn er auf eine Einstellung zeigt (dann endet er mit „unter“ und der Verweis folgt). */
export const einlesenVerweis = (konto: MailIntakeAccount): string | null =>
  !konto.error && deriveIntakeProgress(konto).stage === "paused" ? "technik-hintergrund" : null;

/** Ein Satz zum Stand eines gestarteten Kontos: gezählt, gelesen, oder warum es gerade nicht weitergeht. */
export function einlesenStand(konto: MailIntakeAccount): string {
  const stand = deriveIntakeProgress(konto);
  if (konto.error) return `${konto.label}: Das Einlesen stockt gerade. Kingfisher versucht es von selbst wieder.`;
  // Gescheiterte heißen nie „gelesen“: Der Satz des Sidecars nennt den Grund (Fremdprobe 3, Befund 2).
  if (konto.stand?.zustand === "gescheitert") return konto.stand.satz;
  // Global pause has its own resume action; never describe it as active
  // counting or redirect it to the mailbox-specific pause control.
  if (konto.stand?.zustand === "pausiert" && !konto.paused) return konto.stand.satz;
  if (stand.stage === "paused") return `${konto.label}: Das Einlesen ist pausiert. Fortsetzen kannst du es unter`;
  if (konto.stand?.zustand === "wartet" || (stand.livePending > 0 && konto.stand?.zustand === "liest")) return konto.stand.satz;
  if (stand.total === null) return `${konto.label}: Kingfisher liest deine Mails und zählt sie gerade${stand.processed ? `; ${zahl(stand.processed)} sind schon gelesen` : ""}.`;
  if (stand.processed < stand.total) return `${konto.label}: ${zahl(stand.processed)} von ${zahl(stand.total)} Mails gelesen.`;
  return `${konto.label}: Alle ${zahl(stand.total)} Mails sind gelesen.`;
}
