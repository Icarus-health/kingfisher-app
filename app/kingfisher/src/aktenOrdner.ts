// „Akten als Ordner“: was die Karte zum Stand sagt. Reine Logik (ohne React, testbar mit node --test).
// Gesagt wird, was ein Mensch dazu sagen würde: nie ein Paket, nie ein Zustandswort.
import type {AktenExport} from "./api";

export type Aussage = {text: string; fehler: boolean; ruhig: boolean};

const wann = (wert: string | null) => {
  const datum = wert ? new Date(wert) : null;
  return !datum || Number.isNaN(datum.getTime()) ? "" : new Intl.DateTimeFormat("de-DE", {weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit"}).format(datum);
};
const dateien = (n: number) => `${n.toLocaleString("de-DE")} ${n === 1 ? "Datei" : "Dateien"}`;

/** Der Pfad, wie ihn ein Mensch liest: ohne das Benutzerverzeichnis. */
export function kurzerPfad(pfad: string): string {
  const teile = pfad.replace(/\/+$/, "").split("/").filter(Boolean);
  const ohneHome = teile[0] === "Users" ? teile.slice(2) : teile;
  return ohneHome.length ? `~/${ohneHome.join("/")}` : pfad;
}

/** Ob die Karte den Stand öfter abfragen soll: solange etwas unterwegs ist. */
export function unterwegs(s: AktenExport | null): boolean {
  if (!s) return false;
  return s.laeuft || Boolean(s.pick_request) || Boolean(s.aktiv && s.ordner && s.stand && !s.angekommen && !s.fehler);
}

/** Ohne Angabe zum System: ein Satz, der keinen Mac nennt (Befund 18). Die Karte gibt `nurAufDemMac(…)` mit. */
export const OHNE_HELFER = "Der Helfer der Kingfisher-App, der den Ordner schreibt, meldet sich gerade nicht.";

/** Der eine Satz zum Stand des Ordners; leer, wenn es noch keinen Ordner gibt. `ohneHelfer`: was gilt, wenn der Helfer schweigt. */
export function aussage(s: AktenExport, ohneHelfer: string = OHNE_HELFER): Aussage | null {
  if (!s.ordner) return null;
  if (s.fehler) return {text: s.fehler, fehler: true, ruhig: false};
  if (s.laeuft) return {text: "Die Akten werden gerade geschrieben …", fehler: false, ruhig: false};
  if (!s.aktiv) return {text: s.angekommen && s.gespiegelt ? `Ausgeschaltet. Der Ordner bleibt, wie er war (${wann(s.gespiegelt.am)}).` : "Ausgeschaltet. Es wird nichts geschrieben.", fehler: false, ruhig: true};
  if (!s.stand) return {text: "Noch nichts geschrieben. Der Ordner wird gleich angelegt.", fehler: false, ruhig: false};
  if (s.angekommen && s.gespiegelt) {
    const verschwiegen = s.stand.uebersprungen ? (s.stand.uebersprungen === 1 ? " Eine Akte konnte nicht geschrieben werden." : ` ${s.stand.uebersprungen} Akten konnten nicht geschrieben werden.`) : "";
    return {text: `Zuletzt geschrieben: ${wann(s.gespiegelt.am)}, ${dateien(s.gespiegelt.dateien)}.${verschwiegen}`, fehler: false, ruhig: true};
  }
  if (!s.running) return {text: `${dateien(s.stand.dateien)} sind bereit. ${ohneHelfer}`, fehler: false, ruhig: false};
  return {text: `${dateien(s.stand.dateien)} sind bereit und werden jetzt in den Ordner geschrieben …`, fehler: false, ruhig: false};
}
