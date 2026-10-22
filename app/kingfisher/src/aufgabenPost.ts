import type {AufgabenPostGrund, AufgabenPostVorschlag, Task} from "./api";

// Aufgaben folgen der Post (Oktober 2026): Die eigene Mail erledigt die Aufgabe, die Antwort löst das Warten auf.
// Der Satz mit dem Grund kommt vom Sidecar (`aufgaben_post.py`); hier steht nur, wann er gezeigt wird und wie die
// Knöpfe heißen. Reversibel, deshalb ohne Rückfrage: Jede Zeile trägt „Rückgängig“.

/** Der Grund, den die Zeile zeigt: erledigt durch die Post, oder wieder bei dir; sonst nichts. */
export function postGrund(task: Pick<Task, "erledigt_grund" | "geaendert_grund" | "status">): AufgabenPostGrund | null {
  if (task.erledigt_grund && task.status === "done") return task.erledigt_grund;
  if (task.geaendert_grund && task.status === "open") return task.geaendert_grund;
  return null;
}

/** Der Satz der Zeile, oder null, wenn die Post an dieser Aufgabe nichts geändert hat. */
export function postSatz(task: Pick<Task, "erledigt_grund" | "geaendert_grund" | "status">): string | null {
  const grund = postGrund(task);
  return grund?.satz || null;
}

/** Der Knopf, der den Vorschlag annimmt: dieselbe Änderung, die der Durchlauf sonst selbst gemacht hätte. */
export function annehmenText(vorschlag: Pick<AufgabenPostVorschlag, "art">): string {
  return vorschlag.art === "erledigt" ? "Ja, erledigt" : "Ja, wieder bei mir";
}

/** Die Antwort nach dem Klick, mit „Rückgängig“ im Blick (Grundsatz 4 und 5). */
export function angenommenText(vorschlag: Pick<AufgabenPostVorschlag, "art">): string {
  return vorschlag.art === "erledigt" ? "Als erledigt abgelegt. Rückgängig geht in der Aufgabenliste."
    : "Die Aufgabe liegt wieder bei dir. Rückgängig geht in der Aufgabenliste.";
}
