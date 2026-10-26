// Warten im Gespräch (Paket T, 26.10.2026): reine Logik ohne React, testbar mit node --test.
//
// Die eigene Frage steht sofort im Gespräch, darunter der echte Schritt, den der Sidecar gerade geht (GET
// /api/v1/conversations/{id}/fortschritt, sidecar: gespraech_fortschritt.py). Keine geschätzte Restzeit. War eine lokale
// Antwort langsam und ist die Cloud aus, steht darunter ein Satz mit einem Knopf zum Schalter; einmal weggeklickt, bleibt
// er weg (im Browser gemerkt, jeder Zugriff in try/catch).
import type { GespraechFortschritt, Message } from "./api";
import { LANGSAM_S, gueltigeZeiten } from "./antwortzeit.ts";

export const WARTEN_VORGABE = "Kingfisher antwortet …";
export const LANGSAM_SATZ = "Lokal dauert das. Mit der Cloud ginge es in wenigen Sekunden.";
export const LANGSAM_KNOPF = "Cloud einschalten";
export const LANGSAM_WEG = "Nicht mehr zeigen";
export const LANGSAM_MERKER = "kingfisher.tempo.cloudHinweis";
/** So oft fragt die Oberfläche nach dem Schritt, solange eine Antwort läuft. Der Abruf ist leicht (ein Wörterbuch). */
export const ABFRAGE_MS = 700;

/**
 * Der ganze Hinweis unter einer langsamen lokalen Antwort: der Nutzen und, in einem kurzen Satz, was dann hinausginge und
 * an wen (Persona-Prüfung, D6). `wohin` ist der vorbereitete Anbieter mit Land („Anthropic (USA)“), wenn es genau einen
 * gibt; sonst steht da, dass beim Einschalten zugestimmt wird.
 */
export function langsamSatz(wohin: string | null | undefined): string {
  const an = wohin && wohin.trim() ? wohin.trim() : "einen Cloudanbieter, dem du beim Einschalten zustimmst";
  return `${LANGSAM_SATZ} Dann gingen deine Fragen und Inhalte deiner Mails an ${an}.`;
}

/** Der vorbereitete Cloudanbieter, wenn es genau einen gibt (Schlüssel und Modell da); sonst null. */
export function vorbereiteterAnbieter(anbieter: ReadonlyArray<{ schluessel_da: boolean; standardmodell: string; wohin?: string }> | null | undefined): string | null {
  const bereit = (anbieter ?? []).filter(a => a.schluessel_da && a.standardmodell.trim());
  return bereit.length === 1 ? bereit[0].wohin ?? null : null;
}

/** Der Satz unter der eigenen Frage: der Schritt aus dem Sidecar, sonst „Kingfisher antwortet …“. */
export function warteSatz(stand: GespraechFortschritt | null | undefined): string {
  return stand && stand.laeuft && typeof stand.satz === "string" && stand.satz.trim() ? stand.satz : WARTEN_VORGABE;
}

type Kontext = { zeiten?: unknown; gedaechtnis_cloud?: unknown; cloud_antwort?: unknown } | undefined | null;

/**
 * Steht unter dieser Antwort der Satz zur Cloud? Nur wenn sie gemessen langsamer als `LANGSAM_S` war, nicht schon aus der
 * Cloud kam, die Cloud sicher aus ist (`cloudAn === false`, unbekannt zählt nicht) und der Satz nicht weggeklickt wurde.
 */
export function langsamHinweis(kontext: Kontext, { cloudAn, weggeklickt }: { cloudAn: boolean | null; weggeklickt: boolean }) {
  const zeiten = gueltigeZeiten(kontext?.zeiten);
  if (!zeiten || !(zeiten.gesamt > LANGSAM_S)) return false;
  if (kontext?.gedaechtnis_cloud || kontext?.cloud_antwort) return false;
  return cloudAn === false && !weggeklickt;
}

type Speicher = { getItem(key: string): string | null; setItem(key: string, value: string): void } | undefined | null;

function standardSpeicher(): Speicher {
  try { return globalThis.localStorage; } catch { return undefined; }
}

export function weggeklickt(speicher: Speicher = standardSpeicher()) {
  try { return speicher?.getItem(LANGSAM_MERKER) === "1"; } catch { return false; }
}

export function wegklicken(speicher: Speicher = standardSpeicher()) {
  try { speicher?.setItem(LANGSAM_MERKER, "1"); } catch { /* ohne Speicher bleibt es für diese Sitzung weg */ }
}

// Eine Frage, die auf Heute oder am Gesprächsanfang gestellt wurde, wartet hier auf ihr Gespräch: Das Gespräch öffnet
// sofort, zeigt sie und stellt sie selbst (genau einmal).
const AUSSTEHEND = new Map<string, string>();

export function merkeFrage(gespraech: string, frage: string) {
  AUSSTEHEND.set(gespraech, frage);
}

export function nimmFrage(gespraech: string): string | null {
  const frage = AUSSTEHEND.get(gespraech) ?? null;
  AUSSTEHEND.delete(gespraech);
  return frage;
}

/** Zeigt der Server die Frage schon als letzte Nachricht? Dann steht sie nicht ein zweites Mal da. */
export function frageSchonDa(nachrichten: ReadonlyArray<Pick<Message, "role" | "content">>, frage: string) {
  const letzte = nachrichten[nachrichten.length - 1];
  return Boolean(letzte && letzte.role === "user" && letzte.content === frage);
}

const ANBIETER: Record<string, string> = {
  anthropic: "Anthropic", openai: "OpenAI", mistral: "Mistral", openrouter: "OpenRouter", "ollama-cloud": "Ollama",
};

/**
 * „Über Anthropic beantwortet.“: unter einer Antwort, die über die Cloud kam; sonst null. Gilt für Gedächtnisantworten
 * (`gedaechtnis_cloud`) und für gewöhnliche Gesprächsantworten (`cloud_antwort`, Persona-Prüfung, Kleinpunkt a).
 */
export function cloudVermerk(kontext: { gedaechtnis_cloud?: unknown; cloud_antwort?: unknown } | undefined | null): string | null {
  const cloud = (kontext?.gedaechtnis_cloud ?? kontext?.cloud_antwort) as { anbieter?: unknown } | undefined;
  if (!cloud || typeof cloud !== "object") return null;
  const name = typeof cloud.anbieter === "string" ? ANBIETER[cloud.anbieter] ?? "die Cloud" : "die Cloud";
  return `Über ${name} beantwortet.`;
}
