// Auf welchem System Kingfisher läuft, und die Sätze, die davon abhängen (Fremdprobe, Befund 18). Reine Daten und
// Logik, ohne React, damit `node --test` sie prüfen kann; der Abruf steht in useSystem.ts, die Angabe kommt aus
// sidecar/icarus_memory/laufumgebung.py (`GET /api/v1/system`).
//
// Regel: Kein Text der Oberfläche nennt den Mac fest. Wer „auf diesem Mac“ sagen will, schreibt „auf diesem {Rechner}“
// und gibt den Text durch `fuerSystem`; was es nur auf dem Mac gibt (die Mac-Helfer), sagt `nurAufDemMac`. Der Test
// tests/system.test.mjs sucht nach festen Mac-Sätzen in den Dateien der Oberfläche.

export type SystemArt = "mac" | "docker" | "linux" | "windows" | "rechner";
export type SystemAngabe = { art: SystemArt; name: string; geraet: "Mac" | "Rechner"; mac_helfer: boolean };

/** Solange die Angabe noch nicht da ist: neutral. „Rechner“ stimmt immer, „Mac“ nicht. */
export const UNBEKANNT: SystemAngabe = { art: "rechner", name: "dieser Rechner", geraet: "Rechner", mac_helfer: false };

/** Wo Kingfisher läuft, als Ortsangabe in einem Satz: „im Browser mit Docker“, „unter Linux“. */
export function wo(art: SystemArt): string {
  return { mac: "auf diesem Mac", docker: "im Browser mit Docker", linux: "unter Linux", windows: "unter Windows",
    rechner: "auf diesem Rechner" }[art];
}

/** Setzt in `text` für `{Rechner}` „Mac“ oder „Rechner“ ein. */
export function fuerSystem(text: string, system: Pick<SystemAngabe, "art">): string {
  return text.replaceAll("{Rechner}", system.art === "mac" ? "Mac" : "Rechner");
}

/**
 * Für Dinge, die ein Mac-Helfer erledigt (Ordner im Fenster wählen, Mac-Kalender, Apple Karten, Sicherung): Auf dem
 * Mac der Satz, was zu tun ist, wenn der Helfer schweigt; sonst ehrlich, dass es das hier nicht gibt.
 */
export function nurAufDemMac(system: Pick<SystemAngabe, "art">, was: string): string {
  if (system.art === "mac") return `${was} erledigt ein Helfer der Kingfisher-App. Er meldet sich gerade nicht; öffne die Kingfisher-App neu.`;
  return `${was} gibt es nur in der Kingfisher-App auf dem Mac, nicht ${wo(system.art)}.`;
}

/** Der Satz, wenn der Rechner seine Ausstattung (Arbeitsspeicher, Chip) noch nicht gemeldet hat. */
export function ausstattungUnbekannt(system: Pick<SystemAngabe, "art">): string {
  if (system.art === "mac") return "Die Ausstattung des Mac ist noch unbekannt. Öffne Kingfisher über die Kingfisher-App, dann meldet ein Helfer sie.";
  if (system.art === "docker") return "Die Ausstattung des Rechners ist noch unbekannt: Im Container sieht Kingfisher sie nicht. Es gilt eine vorsichtige Vorauswahl.";
  return "Die Ausstattung des Rechners ist noch unbekannt. Es gilt eine vorsichtige Vorauswahl.";
}

/** Das Gerät, an dem jemand Kingfisher gerade bedient (nicht das, auf dem es läuft): ein Mac oder nur ein Bildschirm zum Tippen. */
export type Eingabegeraet = { mac: boolean; nurTouch: boolean };

/** Aus den Angaben des Browsers: Mac an der Plattform (nicht iPhone, nicht iPad); `nurTouch`, wenn es keinen Zeiger zum Schweben gibt. */
export function eingabegeraetAus(angaben: { plattform?: string; userAgent?: string; nurTouch?: boolean }): Eingabegeraet {
  const text = `${angaben.plattform ?? ""} ${angaben.userAgent ?? ""}`;
  return { mac: /mac/i.test(text) && !/iphone|ipad|ipod/i.test(text), nurTouch: Boolean(angaben.nurTouch) };
}

/**
 * Der Tastenhinweis am Suchfeld (Fremdprobe 2, Befund 11): „⌘ K“ auf dem Mac, „Strg K“ auf anderen Systemen, keiner auf
 * einem Gerät ohne Tastatur. Die Taste selbst wirkt überall (Befehl oder Steuerung mit K).
 */
export function tastenHinweis(geraet: Eingabegeraet): string | null {
  if (geraet.nurTouch) return null;
  return geraet.mac ? "⌘ K" : "Strg K";
}

/** Woher die Angabe zur Ausstattung stammt: ein Helfer auf dem Rechner, Kingfisher selbst, im Container gemessen, unbekannt. */
export type AusstattungQuelle = "bericht" | "eigene" | "untergrenze" | "unbekannt";

/**
 * Die eine Aussage zur Ausstattung unter „Für Techniker“ (Fremdprobe 2, Befund 27): „15,7 GB Arbeitsspeicher, selbst
 * gemessen“, mit Chip nur, wenn er bekannt ist; `null`, wenn nichts bekannt ist (dann gilt `ausstattungUnbekannt`).
 * Modellwahl und Geräteangaben benutzen dieselbe Funktion, damit nie „selbst gemessen“ neben „noch unbekannt“ steht.
 */
export function ausstattungSatz(a: { chip?: string | null; gb: number | null; quelle: AusstattungQuelle }): string | null {
  if (a.quelle === "unbekannt" || a.gb === null || !Number.isFinite(a.gb)) return null;
  const gb = `${a.gb.toLocaleString("de-DE")} GB Arbeitsspeicher`;
  if (a.quelle === "untergrenze") return `Mindestens ${gb}, im Container gemessen; der Rechner kann mehr haben`;
  const chip = a.chip ? `${a.chip} · ` : "";
  return a.quelle === "eigene" ? `${chip}${gb}, selbst gemessen` : `${chip}${gb}`;
}

/** Die Quelle aus dem Geräteprofil des Sidecars (`GET /api/v1/device/profile`, Feld `source`). */
export function ausstattungQuelle(source: string): AusstattungQuelle {
  if (source === "eigene" || source === "untergrenze") return source;
  return source === "unknown" ? "unbekannt" : "bericht";
}
