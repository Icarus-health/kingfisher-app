// Reine Logik von „Postfach mit Adresse“ (ohne React, testbar mit node --test). Fremdprobe 2, Befunde 2 bis 4: Eine
// eigene Domain findet Kingfisher selbst (SRV, Autoconfig, Mailserver; `server_finden.py`); nur wenn nichts antwortet,
// fragt die Karte im Assistenten selbst nach Servername und Port, mit Vorgabe 993.
import type {MailProvider} from "./api";

/** Die Wahl „Nicht dabei“ in der Anbieterliste: dann Servername und Port. */
export const EIGENER_SERVER = "eigen";
export const STANDARD_PORT = 993;

/** Wo man den Servernamen findet, in einem Satz. */
export const SERVER_SATZ = "Den Namen des Mailservers nennt dein Anbieter in seiner Anleitung für Mailprogramme (dort „IMAP“ "
  + "oder „Posteingangsserver“); oft heißt er imap.<deine Domain> oder mail.<deine Domain>.";

export const adresseFertig = (adresse: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(adresse.trim());

export const domainVon = (adresse: string) => adresse.trim().slice(adresse.trim().lastIndexOf("@") + 1).toLowerCase();

/** Was beim Nachsehen den Rechner verlässt, in einem Satz. */
export const nachsehenSatz = (adresse: string) => `Dafür fragt Kingfisher nur nach ${domainVon(adresse) || "deiner Domain"}, `
  + "beim Namensdienst und bei der Domain selbst, nie bei Dritten.";

/** Ein Servername, wie ihn ein Mensch tippt: ohne Leerzeichen, ohne „imaps://“, klein. Leer, wenn es keiner ist. */
export function servername(text: string): string {
  const name = text.trim().toLowerCase().replace(/^imaps?:\/\//, "").replace(/\/.*$/, "").replace(/\.$/, "");
  return /^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(name) || /^\d{1,3}(\.\d{1,3}){3}$/.test(name) ? name : "";
}

/** Der Server, den der Mensch als letzte Möglichkeit selbst einträgt; `null`, solange der Name keiner ist. */
export function eigenerServer(name: string, port: number): MailProvider | null {
  const host = servername(name);
  if (!host || !Number.isInteger(port) || port < 1 || port > 65535) return null;
  return {id: EIGENER_SERVER, label: host, imap_host: host, imap_port: port, smtp_host: "", smtp_port: 587,
    app_password: false, hint: "", help_url: ""};
}

/** Womit Kingfisher sich anmeldet: meist die ganze Adresse, bei manchen Domains nur der Teil vor dem @. */
export function anmeldeName(adresse: string, anbieter: Pick<MailProvider, "benutzer">): string {
  const sauber = adresse.trim();
  return anbieter.benutzer === "lokalteil" ? sauber.slice(0, sauber.lastIndexOf("@")) : sauber;
}

/** Was nach „Erkannt:“ steht. Ein selbst gefundener Server heißt nach seinem Namen. */
export const erkanntText = (anbieter: Pick<MailProvider, "id" | "label">) =>
  anbieter.id === "gefunden" ? `Erkannt: ${anbieter.label}. Kingfisher hat deinen Mailserver in den Angaben deiner Domain gefunden.`
    : `Erkannt: ${anbieter.label}`;

/** Der Name, unter dem das Postfach in der Liste steht: die Adresse. Nach dem Anbieter hießen zwei Gmail-Konten gleich
 * (Paket K); umbenennen geht unter Zugänge mit einem Klick auf den Namen. Ohne Adresse der Anbieter. */
export const postfachName = (adresse: string, anbieter: Pick<MailProvider, "id" | "label">) =>
  adresse.trim().toLowerCase() || anbieter.label;

/** Ein schon verbundenes Postfach, wie es `GET /api/v1/konten` nennt. */
export type Verbundenes = {id: string; name: string; adresse: string};

/**
 * Ist die getippte Adresse schon verbunden (Persona-Prüfung, Paket S, Befund 4)? Erkannt wird es an der Adresse, bevor
 * jemand ein Passwort sucht; der Sidecar prüft beim Speichern zusätzlich Anmeldung und Server (`doppeltes_postfach`).
 */
export function schonVerbunden(adresse: string, postfaecher: readonly Verbundenes[]): Verbundenes | null {
  const sauber = adresse.trim().toLowerCase();
  if (!adresseFertig(sauber)) return null;
  return postfaecher.find(p => p.adresse.trim().toLowerCase() === sauber) ?? null;
}

/** Der ruhige Hinweis dazu; der Weg dorthin steht daneben (unter Zugänge ein Knopf zur Zeile). */
export const schonVerbundenSatz = (name: string) => `Dieses Postfach ist schon verbunden: ${name}. Kingfisher liest es bereits.`;
export const SCHON_VERBUNDEN_WO = "Du findest es unter Einstellungen → Zugänge.";
