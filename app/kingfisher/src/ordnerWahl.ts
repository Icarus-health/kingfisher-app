// Reine Logik der Ordnerwahl (ohne React, testbar mit node --test). Fremdprobe, Befund 6: Mit Helfer am Mac gilt dessen
// Auswahldialog (der Vorgabeordner braucht keinen); ohne Helfer wählt man im Browser.
import type {OrdnerOrt, TranskriptOrdner} from "./api";

export type OrdnerWeg = "helfer" | "browser";

/** Mit Helfer der Weg über den Mac, sonst der im Browser. Ein im Browser gewählter Ordner bleibt im Browser. */
export const ordnerWeg = (ordner: Pick<TranskriptOrdner, "helfer" | "lokal">): OrdnerWeg =>
  ordner.helfer && !ordner.lokal ? "helfer" : "browser";

/**
 * Was über der Auswahl am Mac steht, solange sie läuft. Der Vorgabeordner öffnet kein Fenster. `{Rechner}` setzt
 * `fuerSystem` (system.ts) ein; die Auswahl läuft nur mit Helfer, also auf dem Mac, aber der Satz nennt ihn nicht fest.
 */
export function wartetSatz(modus: "vorgabe" | "waehlen", vorgabe: string): string {
  return modus === "vorgabe"
    ? `Kingfisher legt den Ordner „${vorgabe}“ auf deinem {Rechner} an und liest ihn dann.`
    : "Bitte wähle den Ordner im Fenster, das sich auf deinem {Rechner} geöffnet hat.";
}

/** Die Beschriftung eines Orts zum Anklicken. */
export function ortText(ort: OrdnerOrt): string {
  if (ort.vorgabe) return ort.da ? `Ordner „${ort.name}“ verwenden` : `Ordner „${ort.name}“ anlegen und verwenden`;
  return `${ort.name} verwenden`;
}

export function ortZusatz(ort: OrdnerOrt): string {
  if (!ort.da) return "";  // die Beschriftung sagt schon „anlegen und verwenden“
  const cloud = ort.cloud ? "aus der Cloud, auf diesem Rechner abgeglichen · " : "";
  if (ort.dateien === 0) return `${cloud}noch leer`;
  return cloud + (ort.dateien >= 500 ? "500 Dateien oder mehr" : `${ort.dateien} ${ort.dateien === 1 ? "passende Datei" : "passende Dateien"}`);
}

/** Ein Satz, wenn es nichts anzuklicken gibt (Container ohne eingebundenen Ordner). */
export const OHNE_ORTE = "Kingfisher läuft hier in einem Container und sieht die Ordner deines Rechners nicht. "
  + "Ein Techniker kann einen Ordner für Kingfisher freigeben; dann erscheint er hier zum Anklicken.";
