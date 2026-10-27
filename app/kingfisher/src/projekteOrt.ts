// Projekte haben einen Ort (Persona-Prüfung, Paket H, H2, 27.10.2026). Bis 1.0.29 gab es sie zweimal: unter „Gedächtnis →
// Projekte“ (ein Verzeichnis, das zur Akte führte) und unter „Aufgaben → Projekte“ (anlegen, Status, Aufgaben, Board).
// Beide zeigten dieselben Projekte (`workspace.projects`, dieselbe Kennung). Jetzt stehen sie nur unter Aufgaben; jedes
// Projekt öffnet dort seine Akte („Akte öffnen“). Das Gedächtnis verweist dorthin, alte Verweise führen dorthin.

export const PROJEKTE_ORT = "/vorhaben?view=projects";

/** Zeigt die Adresse auf das frühere „Gedächtnis → Projekte“? */
export function projekteImGedaechtnis(search: string): boolean {
  return new URLSearchParams(search).get("tab") === "projects";
}
