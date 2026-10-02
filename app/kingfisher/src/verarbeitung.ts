// Gedächtnis → Verarbeitung & Verlauf in Alltagssprache (Fremdprobe 2, Befund 16). Reine Logik, testbar mit node --test.
//
// Vorher stand „Aktiv mit qwen3.5:9b.“ direkt über „Wenn du sie aktivierst, werden …“, und darunter Kacheln wie
// „Prüflauf durchgeführt“, „Teilweise geprüft“, „Prüfung fehlgeschlagen 2“. Jetzt: ein Satz zum Stand, ein Satz, was es
// bewirkt (passend dazu, ob es an ist), ein Satz zur Prüfung; Modellname und Kacheln stehen hinter „Für Techniker“.
import type { MemoryAutomation, MemoryCoverage } from "./api";

const anzahl = (n: number, einzahl: string, mehrzahl: string) => `${n} ${n === 1 ? einzahl : mehrzahl}`;

/** Der erste Satz unter „Automatisches Sortieren“: läuft es, und wenn nicht, warum. Ohne Modellnamen. */
export function sortierStand(a: Pick<MemoryAutomation, "state" | "cloud_modell"> & {requested?: boolean}): string {
  // Eingeschaltet, aber das Modell lädt noch oder antwortet noch nicht: kein „Pausiert“, es beginnt von selbst (Befund 3).
  if (a.requested && (a.state === "model_missing" || a.state === "local_model_unavailable"))
    return "An: Kingfisher sortiert deine Quellen selbst, sobald das Sprachmodell auf diesem Rechner bereit ist.";
  switch (a.state) {
    case "active": return "An: Kingfisher sortiert deine Quellen selbst, auf diesem Rechner.";
    case "legacy_active": return "An, aber noch nach der alten Einstellung: Ob es nur auf diesem Rechner läuft, ist nicht abgesichert.";
    case "model_missing": return "Pausiert: Es fehlt noch ein Modell auf diesem Rechner.";
    case "cloud_ueber_ollama": return `Pausiert: ${a.cloud_modell ?? "Das gewählte Modell"} läuft nicht auf diesem Rechner, sondern im Internet. Das Sortieren wartet, bis ein Modell auf diesem Rechner gewählt ist.`;
    case "wrong_model": return "Pausiert: Das gewählte Modell läuft nicht auf diesem Rechner.";
    case "local_model_unavailable": return "Pausiert: Das Modell auf diesem Rechner antwortet gerade nicht.";
    default: return "Aus: Kingfisher sortiert gerade nichts von selbst.";
  }
}

/** Läuft das Sortieren? Eine Quelle für den Satz zum Stand und für den Fortschritt darunter (Fremdprobe 3, Befund 12). */
export const sortiertGerade = (a: Pick<MemoryAutomation, "state">) => a.state === "active" || a.state === "legacy_active";

/** Der zweite Satz: was das Sortieren bewirkt. Läuft es, steht kein „wenn du es einschaltest“ da. */
export function sortierWirkung(a: Pick<MemoryAutomation, "state" | "pending"> & {requested?: boolean}): string {
  const warten = a.pending > 0 ? ` ${anzahl(a.pending, "Quelle wartet", "Quellen warten")} noch darauf.` : "";
  const grenze = "Es wird nichts versendet, und nichts gilt als Wissen, bevor du es bestätigst.";
  if (a.state === "active" || (a.requested && a.state !== "legacy_active")) return `Dabei entstehen Vorschläge für Aufgaben und Wissen sowie Zusammenfassungen. ${grenze}${warten}`;
  if (a.state === "legacy_active") return `Mit „Lokal absichern“ läuft es nur noch mit dem Modell auf diesem Rechner. ${grenze}${warten}`;
  return `Wenn du es einschaltest, sortiert Kingfisher vorhandene und neue Quellen auf diesem Rechner und schlägt Aufgaben, Wissen und Zusammenfassungen vor. ${grenze}${warten}`;
}

/** Ein Satz statt der Kacheln „Prüflauf durchgeführt“, „Teilweise geprüft“, „Prüfung fehlgeschlagen“. */
export function pruefSatz(counts: MemoryCoverage["counts"]): string {
  const fertig = counts.completed ?? 0;
  const offen = (counts.pending ?? 0) + (counts.running ?? 0);
  const teils = counts.partial ?? 0;
  const fehler = counts.failed ?? 0;
  const aus = counts.excluded ?? 0;
  const gesamt = fertig + offen + teils + fehler + aus;
  if (gesamt === 0) return "Noch nichts zu prüfen.";
  const teile = [
    fertig ? `${anzahl(fertig, "Quelle ist", "Quellen sind")} fertig durchgesehen` : "",
    offen ? `${anzahl(offen, "wartet", "warten")} noch` : "",
    teils ? `${anzahl(teils, "ist", "sind")} erst zum Teil durchgesehen` : "",
    aus ? `${anzahl(aus, "ist", "sind")} ausgenommen` : "",
  ].filter(Boolean);
  const satz = teile.length ? teile.join(", ").replace(/, ([^,]*)$/, " und $1") + "." : "";
  const nochmal = fehler ? ` Bei ${anzahl(fehler, "Quelle", "Quellen")} hat es nicht geklappt; du musst nichts tun, Kingfisher versucht es von selbst noch einmal.` : "";
  return `${satz[0]?.toUpperCase() ?? ""}${satz.slice(1)}${nochmal}`.trim();
}

/** Der Satz zum Fortschritt des Sortierens: was gefundene Angaben bedeuten, ohne Fachwort. */
export const FUNDE_SATZ = "Was dabei gefunden wird, nutzt Kingfisher im Gespräch als Hinweis mit Quelle; als Wissen gilt es erst, wenn du es bestätigst.";
