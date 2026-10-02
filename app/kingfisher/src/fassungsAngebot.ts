// Fassung und Update-Angebot (docs/53-download-und-updates.md). Reine Logik ohne React, testbar mit node --test.
//
// Das Update selbst macht die Mac-App: Die Seite schickt über die Brücke `window.webkit.messageHandlers.kingfisher`
// `{aktion: "aktualisieren", fassung, image}`. Die App sichert, lädt das Bild, startet neu und lädt die Seite neu.
// Damit die Seite danach sagen kann, ob es geklappt hat, merkt sie sich Ziel- und Ausgangsfassung im Browser
// (`localStorage`, jeder Zugriff in try/catch: im privaten Fenster fehlt er, dann gibt es eben keine Rückmeldung).

export type FassungManifest = {
  fassung: string; datum: string; image: string; dmg: string; hinweise: string[]; app_mindestens: string;
};

/** GET /api/v1/fassung (sidecar: fassung.py). `erreicht` nur in der Antwort von „Jetzt nachsehen“. */
export type FassungStand = {
  fassung: string;
  neueste: FassungManifest | null;
  update_verfuegbar: boolean;
  app_update_noetig: boolean;
  geprueft_um: string | null;
  pruefen: boolean;
  download_seite?: string | null;
  erreicht?: boolean;
};

export type Bruecke = { postMessage: (nachricht: unknown) => void };

export const MERKER = "kingfisher.update";
export const SATZ_VORHER = "Kingfisher sichert vorher deine Daten und ist etwa eine Minute weg.";
export const SATZ_OHNE_APP = "Öffne Kingfisher über die App, um zu aktualisieren.";
export const SATZ_FEHLGESCHLAGEN = "Das Update hat nicht geklappt; deine Daten sind gesichert.";
export const SATZ_PRUEFEN = "Einmal am Tag fragt Kingfisher bei GitHub, ob es eine neue Fassung gibt. Über dich geht dabei nichts hinaus.";

/** Die Brücke zur Mac-App, wenn diese Seite im Fenster der App läuft; im Browser null. */
export function brueckeFinden(fenster: unknown = globalThis): Bruecke | null {
  try {
    const kandidat = (fenster as { webkit?: { messageHandlers?: { kingfisher?: Bruecke } } })?.webkit?.messageHandlers?.kingfisher;
    return kandidat && typeof kandidat.postMessage === "function" ? kandidat : null;
  } catch {
    return null;
  }
}

/** Die Fassung für Menschen: „1.0.0“, oder ein Satz, wenn sie aus dem Quelltext gebaut ist. */
export function fassungText(fassung: string): string {
  return /^\d+\.\d+\.\d+$/.test(fassung) ? `Fassung ${fassung}` : "Aus dem Quelltext gebaut, ohne Fassungsnummer";
}

/** Was das Angebot zeigt: Überschrift mit der ersten Neuerung, und welcher Weg (Knopf, neue App laden, App öffnen). */
export type Angebot = {
  titel: string;
  weg: "knopf" | "app_laden" | "app_oeffnen";
  satz: string;
};

export function angebot(stand: FassungStand | null, bruecke: boolean): Angebot | null {
  if (!stand?.update_verfuegbar || !stand.neueste) return null;
  const { fassung, hinweise } = stand.neueste;
  const erste = hinweise.find(h => h.trim()) ?? "";
  const titel = erste ? `Neue Fassung ${fassung} ist da: ${erste}` : `Neue Fassung ${fassung} ist da.`;
  if (stand.app_update_noetig) {
    return { titel, weg: "app_laden", satz: `Für Fassung ${fassung} braucht Kingfisher eine neue App. Lade sie von der Download-Seite und ziehe sie in „Programme“; deine Daten bleiben.` };
  }
  if (!bruecke) return { titel, weg: "app_oeffnen", satz: SATZ_OHNE_APP };
  return { titel, weg: "knopf", satz: SATZ_VORHER };
}

/** Die Nachricht an die App. Genau diese drei Angaben, nichts sonst. */
export function auftrag(manifest: FassungManifest) {
  return { aktion: "aktualisieren", fassung: manifest.fassung, image: manifest.image } as const;
}

type Speicher = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function speicher(): Speicher | null {
  try { return globalThis.localStorage ?? null; } catch { return null; }
}

/** Vor dem Auftrag: Ziel und Ausgangsfassung merken. */
export function merken(ziel: string, vorher: string, ablage: Speicher | null = speicher()): void {
  try { ablage?.setItem(MERKER, JSON.stringify({ ziel, vorher })); } catch { /* ohne Ablage keine Rückmeldung */ }
}

/**
 * Nach dem Neuladen: einmal sagen, wie es ausging, und den Merker löschen. „Kingfisher ist jetzt auf Fassung 1.2.0.“,
 * wenn die Zielfassung läuft; der Satz vom Fehlschlag, wenn noch die alte läuft; sonst nichts.
 */
export function rueckmeldung(laeuft: string, ablage: Speicher | null = speicher()): string {
  let roh: string | null = null;
  try { roh = ablage?.getItem(MERKER) ?? null; } catch { return ""; }
  if (!roh) return "";
  try { ablage?.removeItem(MERKER); } catch { /* bleibt stehen; die Rückmeldung kommt dann noch einmal */ }
  try {
    const { ziel, vorher } = JSON.parse(roh) as { ziel?: unknown; vorher?: unknown };
    if (typeof ziel === "string" && laeuft === ziel) return `Kingfisher ist jetzt auf Fassung ${ziel}.`;
    if (typeof vorher === "string" && laeuft === vorher) return SATZ_FEHLGESCHLAGEN;
  } catch { /* unlesbar: nichts sagen */ }
  return "";
}

/** Die Antwort auf „Jetzt nachsehen“ in einem Satz. */
export function nachgesehenText(stand: FassungStand): string {
  if (stand.erreicht === false) return "Die Download-Seite war gerade nicht erreichbar. Versuche es später noch einmal.";
  if (stand.update_verfuegbar && stand.neueste) return `Neue Fassung ${stand.neueste.fassung} ist da.`;
  return "Kingfisher ist auf dem neuesten Stand.";
}

/** „Zuletzt nachgesehen am 2. Oktober um 8:00“; leer, wenn noch nie. */
export function zuletztText(geprueftUm: string | null, zone?: string): string {
  if (!geprueftUm) return "Noch nie nachgesehen.";
  const zeit = new Date(geprueftUm);
  if (Number.isNaN(zeit.getTime())) return "";
  const tag = zeit.toLocaleDateString("de-DE", { day: "numeric", month: "long", timeZone: zone });
  const uhr = zeit.toLocaleTimeString("de-DE", { hour: "numeric", minute: "2-digit", timeZone: zone });
  return `Zuletzt nachgesehen am ${tag} um ${uhr}.`;
}
