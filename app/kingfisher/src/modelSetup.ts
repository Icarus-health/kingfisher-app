// Reine Logik der Karte „Für diesen Rechner empfohlen“ (ohne React, testbar mit node --test).
import type {ModelOrchestra, ModelPullState, ModelRecommendationRow} from "./api";

export type RoleStatus = ModelRecommendationRow["status"];

export const statusLabel = (status: RoleStatus) =>
  status === "eingerichtet" ? "Eingerichtet" : status === "installiert" ? "Installiert" : "Fehlt";

// Was der Knopf einer Zeile heißt; eingerichtet braucht keinen.
export const actionLabel = (status: RoleStatus) =>
  status === "eingerichtet" ? null : status === "installiert" ? "Übernehmen" : "Einrichten";

// Die Aufgaben, die „Alles einrichten“ bearbeitet: Schon Eingerichtetes wird übersprungen.
export const pendingRoles = (rows: ModelRecommendationRow[]) =>
  rows.filter(row => row.status !== "eingerichtet").map(row => row.rolle);

// Nur Modelle, die wirklich geladen werden müssen, zählen zur Größe; jedes Modell nur einmal.
export function downloadSize(rows: ModelRecommendationRow[]) {
  const seen = new Map<string, number>();
  for (const row of rows) if (row.status === "fehlt" && !seen.has(row.empfohlen.name)) seen.set(row.empfohlen.name, row.empfohlen.groesse_gb);
  return {models: [...seen.keys()], gb: [...seen.values()].reduce((sum, value) => sum + value, 0)};
}

const gbText = (gb: number) => (Math.round(gb * 10) / 10).toLocaleString("de-DE");

// Der eine Satz vor „Alles einrichten“. Der Einzelsatz kommt vom Server (mit Größe und Dauer).
export function allConfirmation(rows: ModelRecommendationRow[]) {
  const {models, gb} = downloadSize(rows);
  if (models.length === 0) return "Es wird nichts heruntergeladen; die installierten Modelle werden übernommen.";
  const von = Math.max(1, Math.ceil(gb * 1024 / 62.5 / 60));
  const bis = Math.max(2, Math.ceil(gb * 1024 / 12.5 / 60));
  return `Es werden nacheinander ${models.length === 1 ? "1 Modell" : `${models.length} Modelle`} mit zusammen etwa ${gbText(gb)} GB geladen; das dauert je nach Internetleitung etwa ${von} bis ${bis} Minuten.`;
}

// Die eine Zeile unter den Aufgaben: was alle Modelle zusammen brauchen. Unbekanntes wird gesagt, nicht geraten.
export function orchesterZeile(o: ModelOrchestra) {
  const platte = o.festplatte_frei_gb === null ? "freier Platz unbekannt" : `frei: ${gbText(o.festplatte_frei_gb)} GB`;
  const rest = o.unbekannte_modelle.length ? ` Die Größe von ${o.unbekannte_modelle.join(", ")} ist nicht bekannt und fehlt in der Summe.` : "";
  return `Zusammen: ${gbText(o.tag_gb)} GB Arbeitsspeicher am Tag, ${gbText(o.nacht_gb)} GB nachts, ${gbText(o.festplatte_gb)} GB Festplatte (${platte}).${rest}`;
}

export const pullPercent = (state: Pick<ModelPullState, "fortschritt">) =>
  state.fortschritt === null || !Number.isFinite(state.fortschritt) ? null : Math.max(0, Math.min(100, Math.floor(state.fortschritt * 100)));

export const isRunning = (state: Pick<ModelPullState, "phase">) => state.phase === "wartet" || state.phase === "laedt" || state.phase === "prueft";

export function describePull(state: ModelPullState) {
  const percent = pullPercent(state);
  if (state.phase === "fehler") return state.fehler ? `${state.fehler.grund} ${state.fehler.naechster_schritt}` : state.text;
  if (state.phase === "fertig") return "Eingerichtet und geprüft.";
  if (state.phase === "prueft") return "Das Modell wird geprüft …";
  if (state.phase === "laedt") return percent === null ? "Das Modell wird geladen …" : `Das Modell wird geladen … ${percent} %`;
  return "Wird vorbereitet …";
}

// Cloud lässt sich nur zuschalten, wenn der Anbieter gewählt ist, ein Schlüssel vorliegt und der Nutzer eingewilligt hat.
export const cloudReady = (provider: string, hasKey: boolean, consent: boolean) => provider !== "" && hasKey && consent;

// Fragt den Stand eines Ladevorgangs, bis er endet. `wait` ist austauschbar, damit der Test nicht schläft.
export async function watchPull({read, onState, wait = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms)),
  intervalMs = 1000, isStopped = () => false, maxErrors = 3}: {
  read: () => Promise<ModelPullState>;
  onState: (state: ModelPullState) => void;
  wait?: (ms: number) => Promise<void>;
  intervalMs?: number;
  isStopped?: () => boolean;
  maxErrors?: number;
}): Promise<ModelPullState | null> {
  let errors = 0;
  while (!isStopped()) {
    try {
      const state = await read();
      errors = 0;
      if (isStopped()) return null;
      onState(state);
      if (!isRunning(state)) return state;
    } catch {
      // Ein kurzer Aussetzer (Neustart, Netz) beendet den Lauf auf dem Server nicht; erst mehrere in Folge gelten als Verlust.
      if (++errors >= maxErrors) return null;
    }
    await wait(intervalMs);
  }
  return null;
}

/** Block known oversized plans before making any setup request. Unknown capacity is not a fit claim. */
export function setupFits(rows: Array<Pick<ModelRecommendationRow, "rolle" | "empfohlen">>,
  plan: Pick<ModelOrchestra, "passt_tag" | "passt_nacht"> | undefined, roles: string[]): boolean {
  return roles.length > 0 && roles.every(role => rows.some(row => row.rolle === role && row.empfohlen.passt))
    && (roles.length === 1 || (plan?.passt_tag !== false && plan?.passt_nacht !== false));
}
