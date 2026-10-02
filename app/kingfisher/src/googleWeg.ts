// Reine Logik für Google ohne eigenes Cloud-Projekt (Fremdprobe, Befund 2; ohne React, testbar mit node --test).
// Post: Gmail über IMAP mit App-Passwort. Kalender: die geheime Adresse im iCal-Format, nur lesend (`kalender_abo.py`).
// „Mit Google anmelden“ (OAuth) steht vorne nur, wenn ein Techniker es eingerichtet hat; sonst kein gesperrter Knopf.
import type {MailProvider} from "./api";

/** Wo man die Adresse findet und was hinausgeht: zwei Sätze, vorne auf der Karte. */
export const WO_FINDEN = "Öffne Google Kalender im Browser, dort die Einstellungen deines Kalenders, und kopiere unter „Kalender integrieren“ die „Geheime Adresse im iCal-Format“. Füge sie hier ein; Kingfisher liest damit nur, und hinaus geht nichts außer dem Abruf dieser Adresse.";
export const KALENDER_EINSTELLUNGEN = "https://calendar.google.com/calendar/r/settings";
export const ADRESSE_FELD = "Geheime Adresse im iCal-Format";

export type GoogleKonfiguration = {configured: boolean; secure_storage: boolean} | null;

/** „Mit Google anmelden“ vorne zeigen? Nur wenn es eingerichtet ist und Zugänge geschützt gespeichert werden können. */
export function googleAnmeldungVorne(konfiguration: GoogleKonfiguration): boolean {
  return Boolean(konfiguration?.configured && konfiguration.secure_storage);
}

/** Sieht die Eingabe wie eine Kalenderadresse aus? (Die Prüfung selbst macht der Sidecar, mit einem Satz bei Fehlern.) */
export function siehtNachAdresseAus(url: string): boolean {
  return /^(https|webcal):\/\/\S+$/i.test(url.trim());
}

/** Der Satz nach dem Verbinden. */
export function aboVerbundenSatz(gefunden: string, termine: number, neu: number): string {
  if (neu === 0) return `Schon verbunden: ${gefunden}.`;
  const zahl = termine === 1 ? "1 Termin" : `${termine.toLocaleString("de-DE")} Termine`;
  return `Verbunden: ${gefunden} (${zahl}, nur lesen).`;
}

/** Text des Verweises auf die Hilfeseite eines Anbieters. */
export function hilfeText(anbieter: Pick<MailProvider, "help_label">): string {
  return anbieter.help_label || "So bekommst du es";
}
