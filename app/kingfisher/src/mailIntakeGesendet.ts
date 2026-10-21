import type {MailIntakeAccount} from "./api";
import {ordnerName} from "./mailAbruf.ts";

// Gesendete Mails einlesen (Oktober 2026): Ein Stabschef kennt die eigenen Zusagen. Der Satz zum Umfang kommt vom
// Sidecar (`umfang`, drei Fälle: Gesamtbestand, „Posteingang und Gesendet“, „Nur der Posteingang“); der Knopf
// „Gesendete Mails auch einlesen“ steht nur bei Konten, die mit nur dem Posteingang laufen.

/** Was gelesen wird, in einem Satz. Ohne `umfang` (älterer Sidecar) die bisherigen Sätze aus den Ordnernamen. */
export function umfangSatz(account: MailIntakeAccount): string {
  if (!account.started) return "Kingfisher schaut zuerst nach, welche Ordner es gibt, und zeigt sie dir vor dem Einlesen.";
  if (account.umfang) return account.umfang;
  if (account.folders.every(folder => folder.folder === "INBOX")) return "Nur der Posteingang. Gesendete und archivierte Mails sind nicht dabei.";
  return `Gelesen werden: ${account.folders.map(folder => ordnerName(folder.folder)).join(", ")}. Neue Mails aus diesen Ordnern kommen laufend dazu.`;
}

/** Nur wo nur der Posteingang läuft und ein Gesendet-Ordner erkennbar sein kann (nicht: nachgesehen und keiner da). */
export function gesendetKnopfSichtbar(account: MailIntakeAccount): boolean {
  if (!account.started || !account.connected) return false;
  if (account.gesendet_dabei !== false) return false;  // dabei, oder älterer Sidecar ohne die Angabe
  if (account.gesendet_erkennbar === false) return false;
  return account.folders.every(folder => folder.folder === "INBOX");
}

/** Die Antwort des Sidecars als Status; fehlt der Satz, ein ehrlicher Ersatz statt Schweigen. */
export function ergaenzenSatz(antwort: {satz?: string | null; ergaenzt?: string[]}): string {
  return antwort.satz || "Kingfisher hat nachgesehen; der Stand unten zeigt, was gelesen wird.";
}
