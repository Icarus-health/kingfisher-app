// Reine Logik von „Kalender wie Mail“ (ohne React, testbar mit node --test). Fremdprobe, Befund 7: Die Mailadresse
// genügt; der Anbieter wird an ihr erkannt, die Adresse des Kalenders ergänzt Kingfisher selbst.
import type {MailAccount, MailProvider} from "./api";
import {anbieterZurAdresse} from "./Einrichtung/schritte.ts";

export type KalenderWeg =
  | {art: "unvollstaendig"}
  /** Bekannter Anbieter mit Kalenderdienst: nur noch das Passwort (oder das des Postfachs). */
  | {art: "bekannt"; anbieter: MailProvider; passwortLabel: string}
  /** Google: der Kalender geht über seine geheime iCal-Adresse, ohne Passwort und ohne Cloud-Projekt (Befund 2). */
  | {art: "google_ical"; anbieter: MailProvider}
  /** Der Anbieter bietet keinen Kalenderzugang mit Passwort an (Microsoft): ein ehrlicher Satz. */
  | {art: "kein_zugang"; anbieter: MailProvider; satz: string}
  /** Eigene Domain: Kingfisher sucht den Kalender selbst beim Mailserver der Domain (Fremdprobe 2, Befund 5). */
  | {art: "selbst_suchen"; anbieter: MailProvider | null; passwortLabel: string}
  /** Der Katalog kennt die Adresse des Kalenders nicht, und gefunden wurde er nicht: dann braucht es sie, mit Feld. */
  | {art: "adresse_fehlt"; anbieter: MailProvider | null; passwortLabel: string};

export const ADRESSE_FEHLT = "Für diesen Anbieter brauche ich die Adresse deines Kalenders.";
/** Wo man die Adresse findet, und dass Überspringen nicht schadet: ein Satz unter dem Feld. */
export const ADRESSE_WO = "Dein Anbieter nennt sie in seiner Anleitung für Kalender-Programme. Du kannst den Kalender auch überspringen; das schadet nichts.";
/** Was beim selbst Suchen geschieht und wohin das Passwort geht, in einem Satz. */
export const SELBST_SUCHEN = "Kingfisher sucht deinen Kalender selbst beim Mailserver deiner Domain; das Passwort geht erst dorthin, wenn dort ein Kalender antwortet.";

/** Microsoft: kein Kalender mit Passwort, aber ein veröffentlichter Kalender als Abo-Adresse, nur lesend. */
export const MICROSOFT_WO_FINDEN = "Öffne Outlook im Browser, dort Einstellungen, Kalender, Freigegebene Kalender. Wähle unter „Kalender veröffentlichen“ deinen Kalender, klicke „Veröffentlichen“ und kopiere den ICS-Link; Kingfisher liest damit nur.";
export const MICROSOFT_EINSTELLUNGEN = {
  privat: "https://outlook.live.com/calendar/0/options/calendar/SharedCalendars",
  organisation: "https://outlook.office.com/calendar/options/calendar/SharedCalendars",
} as const;

export const adresseVollstaendig = (adresse: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(adresse.trim());

/**
 * Welcher Weg zu dieser Adresse passt. `adresseVerlangt`: der Server hat gesagt, dass er die Adresse braucht.
 * `vomServer`: der Anbieter, den der Sidecar am Mailserver der Domain erkannt hat (Google Workspace, Microsoft 365).
 */
export function kalenderWeg(adresse: string, anbieter: readonly MailProvider[], adresseVerlangt = false, vomServer: MailProvider | null = null): KalenderWeg {
  if (!adresseVollstaendig(adresse)) return {art: "unvollstaendig"};
  const erkannt = anbieterZurAdresse(adresse.trim(), anbieter) ?? vomServer;
  if (erkannt?.kalender_ical) return {art: "google_ical", anbieter: erkannt};
  const passwortLabel = erkannt?.app_password ? "App-Passwort" : "Passwort";
  if (erkannt?.caldav_note) return {art: "kein_zugang", anbieter: erkannt, satz: erkannt.caldav_note};
  if (erkannt?.caldav_url && !adresseVerlangt) return {art: "bekannt", anbieter: erkannt, passwortLabel};
  // Eine eigene Domain (nicht im Katalog, oder ihr Mailserver selbst gefunden): erst selbst suchen, dann fragen.
  if (!adresseVerlangt && (!erkannt || erkannt.id === "gefunden")) return {art: "selbst_suchen", anbieter: erkannt, passwortLabel};
  return {art: "adresse_fehlt", anbieter: erkannt, passwortLabel};
}

/** Das Postfach mit genau dieser Adresse, dessen Passwort auch für den Kalender gilt (nichts zweimal eingeben). */
export function postfachZurAdresse(adresse: string, konten: readonly Pick<MailAccount, "id" | "user" | "secret_present">[]) {
  const gesucht = adresse.trim().toLowerCase();
  return konten.find(konto => konto.secret_present && konto.user.trim().toLowerCase() === gesucht) ?? null;
}

/** Der Satz nach dem Verbinden: welche Kalender gefunden wurden. */
export function verbundenSatz(gefunden: readonly string[], neu: number): string {
  if (!gefunden.length) return "Verbunden.";
  const namen = gefunden.join(", ");
  if (neu === 0) return `Schon verbunden: ${namen}.`;
  return gefunden.length === 1 ? `Verbunden: dein Kalender „${namen}“.` : `Verbunden: ${gefunden.length} Kalender (${namen}).`;
}
