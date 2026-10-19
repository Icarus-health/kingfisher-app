// Verweise in die Einstellungen als Ziel, nicht als Text (Fremdprobe, Befund 25). Reine Logik, testbar mit node --test.
// Aus „Pausieren kannst du jederzeit unter Einstellungen → Für Techniker → Zeitplan und Hintergrund“ wird ein Klick,
// der genau dort landet. Der Wortlaut des Verweises kommt aus der Gliederung; benennt jemand einen Reiter um, folgt er.
import {BEREICHE, TECHNIK, kennungVon, zielAus} from "./Einstellungen/gliederung.ts";

export type Verweis = {href: string; text: string};

/**
 * `darf`, `zugaenge`, `technik-hintergrund` … ergeben Adresse und Wortlaut. Eine Kennung, die es nicht gibt, ist ein
 * Fehler im Code und kein Grund, den Nutzer auf eine andere Seite zu schicken: Dann wirft die Funktion.
 */
export function verweis(kennung: string): Verweis {
  const ziel = zielAus(kennung);
  if (kennungVon(ziel) !== kennung) throw new Error(`Unbekanntes Ziel in den Einstellungen: ${kennung}`);
  const bereich = BEREICHE.find(eintrag => eintrag.id === ziel.bereich);
  const technik = ziel.technik ? TECHNIK.find(eintrag => eintrag.id === ziel.technik) : null;
  const teile = ["Einstellungen", bereich?.label ?? "", ...(technik ? [technik.titel] : [])];
  return {href: `/settings#${kennung}`, text: teile.join(" → ")};
}

/**
 * Ein Satz des Sidecars, der den Weg schon im Wortlaut nennt („… Melde dich unter Einstellungen → Zugänge neu an.“):
 * zerlegt in den Text davor, den Verweis und den Text danach, damit genau dieser Wortlaut zum Klick wird. Der Satz
 * bleibt so auch dort richtig, wo er nur als Text steht. Nennt er den Weg nicht oder kennt die Gliederung das Ziel
 * nicht (ein älterer Sidecar), bleibt er ganz Text: Ein fehlender Klick ist besser als eine kaputte Seite.
 */
export function satzMitVerweis(satz: string, kennung?: string | null): {vor: string; verweis: Verweis | null; nach: string} {
  const ganz = {vor: satz, verweis: null, nach: ""};
  if (!kennung) return ganz;
  let ziel: Verweis;
  try { ziel = verweis(kennung); } catch { return ganz; }
  const stelle = satz.indexOf(ziel.text);
  if (stelle < 0) return ganz;
  return {vor: satz.slice(0, stelle), verweis: ziel, nach: satz.slice(stelle + ziel.text.length)};
}
