// Reine Logik der Quellenvorgaben unter „Was Kingfisher darf“ (ohne React, testbar mit node --test).
import type { WeltFeed, WeltVorgabe } from "./api";

export type VorgabeZustand = "an" | "abbestellt" | "aus";

/** `an`: hinzugefügt und eingeschaltet; `abbestellt`: hinzugefügt, aber im Briefing abbestellt; `aus`: nicht hinzugefügt. */
export function vorgabeZustand(vorgabe: Pick<WeltVorgabe, "feed_id">, feeds: ReadonlyArray<Pick<WeltFeed, "id" | "enabled">>): VorgabeZustand {
  const feed = feeds.find(f => f.id === vorgabe.feed_id);
  if (!feed) return "aus";
  return feed.enabled ? "an" : "abbestellt";
}

/** Die Feeds, die nicht aus der Vorgabeliste stammen: die eigenen Quellen des Nutzers. */
export function eigeneQuellen<T extends Pick<WeltFeed, "id" | "url">>(feeds: readonly T[], vorgaben: ReadonlyArray<Pick<WeltVorgabe, "url">>): T[] {
  const bekannt = new Set(vorgaben.map(v => v.url));
  return feeds.filter(f => !bekannt.has(f.url));
}

/**
 * Was der Nutzer ins Feld „Adresse“ getippt hat, als Adresse. Ohne Schema wird https davor gesetzt, damit niemand „https://“
 * tippen muss; Leerzeichen oder ein Name ohne Punkt sind keine Adresse (leer). Ob sie gilt, entscheidet der Sidecar.
 */
export function normiereAdresse(eingabe: string): string {
  const text = eingabe.trim();
  if (!text || /\s/.test(text)) return "";
  const mitSchema = /^[a-z][a-z0-9+.-]*:\/\//i.test(text) ? text : `https://${text}`;
  return /^[a-z][a-z0-9+.-]*:\/\/[^/?#]*\.[^/?#]+/i.test(mitSchema) ? mitSchema : "";
}

/** Ein Satz unter den Vorgaben: von wann die Liste ist, und dass ihre Adressen noch nicht abgerufen wurden (oder wann). */
export function vorgabenStandSatz(stand: { stand: string; abgerufen: string | null }): string {
  const tag = (iso: string) => {
    const datum = new Date(`${iso}T12:00:00`);
    return Number.isNaN(datum.getTime()) ? iso : datum.toLocaleDateString("de-DE", { day: "numeric", month: "long", year: "numeric" });
  };
  return stand.abgerufen
    ? `Die Liste ist vom ${tag(stand.stand)}; alle Adressen wurden am ${tag(stand.abgerufen)} geprüft.`
    : `Die Liste ist vom ${tag(stand.stand)}; die Adressen wurden noch nicht abgerufen. Kingfisher liest jede beim Hinzufügen einmal zur Probe, und antwortet sie nicht, steht der Grund da.`;
}
