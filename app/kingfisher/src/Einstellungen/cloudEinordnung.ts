// „Neue Mails in der Cloud einordnen“: die Sätze und Entscheidungen des Schalters, ohne React, damit `node --test` sie
// prüfen kann (tests/cloud-einordnung.test.mjs). Der Stand kommt aus GET /api/v1/models/roles (Rolle hintergrund,
// `cloud_einordnung`; sidecar: hintergrund_cloud.py). Der Satz zur Einwilligung kommt ebenfalls von dort (`cloud_satz`)
// und wird hier nur um „Ich willige ein.“ ergänzt, damit er an einer Stelle gepflegt wird.
import type { CloudEinordnungStand, ModelRoleState } from "../api.ts";
import { SCHALTER } from "./gliederung.ts";

export const OHNE_ZUGANG = "Dafür braucht es den vorbereiteten Claude-Zugang unter KI & Modelle (Schlüssel und Modell).";
export const WIEDER_LOKAL = "Einordnen läuft wieder nur auf diesem Rechner.";

/** Die Zeile der Rolle hintergrund aus GET /roles, oder null, wenn der Sidecar sie (noch) nicht kennt. */
export function hintergrundZeile(rollen: ModelRoleState[]): ModelRoleState | null {
  return rollen.find(r => r.rolle === "hintergrund" && r.cloud_einordnung) ?? null;
}

/** Der Satz, den der Mensch beim Einschalten anhakt: der Satz des Sidecars plus „Ich willige ein.“ */
export function zustimmungsSatz(zeile: Pick<ModelRoleState, "cloud_satz">): string {
  return `${zeile.cloud_satz.trim()} ${SCHALTER.cloud_einordnung.zustimmung}`;
}

/** Die Statuszeile, solange der Schalter an ist. */
export function statusSatz(stand: CloudEinordnungStand): string {
  if (stand.erschoepft) return `Heute sind die ${stand.tagesbudget} Aufrufe aufgebraucht; morgen geht es weiter.`;
  return `Neue Mails werden über Anthropic (${stand.modell}) eingeordnet. Heute ${stand.heute} von ${stand.tagesbudget} Aufrufen.`;
}

/** Einschalten geht nur mit vorbereitetem Zugang und angehaktem Satz. */
export function einschaltenMoeglich(stand: CloudEinordnungStand, zugestimmt: boolean): boolean {
  return stand.zugang_da && zugestimmt;
}

/** Was der Schalter bei der Frage „Einschalten?“ zeigt: den Hinweis auf den Zugang oder die Zustimmung. */
export function frageArt(stand: CloudEinordnungStand): "ohne_zugang" | "zustimmung" {
  return stand.zugang_da ? "zustimmung" : "ohne_zugang";
}
