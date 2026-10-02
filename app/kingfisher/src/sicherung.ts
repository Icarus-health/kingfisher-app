// Reine Logik der Sicherung (ohne React, testbar mit node --test). Fremdprobe, Befund 8: Ohne Helfer kein Formular, das
// ins Leere führt, sondern eine Sicherung, die Kingfisher selbst schreibt und der Browser speichert.
import type {RecoveryStatus} from "./api";

/** Mit Sicherungshelfer auf dem Mac dessen Weg (ein laufender Auftrag gehört auch dazu), sonst der Download. */
export function sicherungWeg(stand: RecoveryStatus | null): "helfer" | "download" {
  if (!stand) return "download";
  const laeuft = stand.job?.status === "queued" || stand.job?.status === "running";
  return stand.online || laeuft ? "helfer" : "download";
}
