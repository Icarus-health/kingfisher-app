// Neu anmelden unter Zugänge (docs/47-einstellungen.md): reine Logik ohne React, damit `node --test` sie prüft.
import type { MailAccount, MailStand } from "../api";

/** Welcher Weg am Postfach steht, wenn sein Stand hierher verweist (Anmeldung abgelaufen, Passwort fehlt): das neue
 * Passwort, „Mit Google anmelden“ mit demselben Konto, oder nichts (Microsoft hat seine eigene Karte „Neu anmelden“). */
export function neuAnmeldenWeg(konto: Pick<MailAccount, "auth">, stand?: Pick<MailStand, "verweis"> | null): "passwort" | "google" | null {
  if (stand?.verweis !== "zugaenge") return null;
  if (!konto.auth) return "passwort";
  return konto.auth === "google" ? "google" : null;
}

/** Für ein Google-Postfach: derselbe Knopf wie beim Verbinden, mit demselben Konto. Kingfisher ersetzt dann die alte
 * Anmeldung; es entsteht kein zweites Postfach und kein zweites Einlesen. Ohne eingerichtete Google-Anmeldung sagt der
 * Satz, wer sie einrichtet. */
export function googleNeuSatz(googleVorne: boolean): string {
  return googleVorne
    ? "Melde dich weiter unten mit „Mit Google anmelden“ und demselben Google-Konto neu an. Kingfisher ersetzt dann die alte Anmeldung; ein zweites Postfach entsteht nicht."
    : "Neu anmelden geht mit „Mit Google anmelden“. Das richtet ein Techniker unter Einstellungen → Für Techniker → Google-Anmeldung vorbereiten ein; danach meldest du dich hier mit demselben Google-Konto neu an.";
}

/** Was nach dem Neu-Anmelden dasteht: der Satz des Sidecars (etwa zu einem Kalender, der das neue Passwort nicht annahm),
 * sonst die Bestätigung. */
export function angemeldetSatz(label: string, satz?: string | null): string {
  return satz || `Angemeldet. Kingfisher liest ${label} gleich weiter.`;
}
