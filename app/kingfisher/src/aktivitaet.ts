// Eingaben an den Sidecar melden, damit der Hintergrund zurücktritt, solange jemand arbeitet (docs/46-hintergrund.md).
// Gemeldet wird gedrosselt: höchstens alle MELDE_ABSTAND_MS eine Meldung, gleich wie viel getippt wird. Abfragen, die
// die Oberfläche von selbst stellt, zählen beim Sidecar nicht als Eingabe; nur diese Meldung und echte Aktionen.

export const MELDE_ABSTAND_MS = 5000;
const EREIGNISSE = ["keydown", "pointerdown", "wheel", "touchstart"] as const;

/** Reine Logik: ob jetzt gemeldet werden soll. */
export const sollMelden = (jetzt: number, zuletzt: number | null, abstand = MELDE_ABSTAND_MS) =>
  zuletzt === null || jetzt - zuletzt >= abstand;

type Ziel = {
  addEventListener: (name: string, fn: () => void, optionen?: AddEventListenerOptions) => void;
  removeEventListener: (name: string, fn: () => void, optionen?: EventListenerOptions) => void;
};

/** Hört auf Eingaben im Fenster und meldet sie gedrosselt. Gibt eine Funktion zum Abmelden zurück. */
export function eingabenMelden(melden: () => unknown, ziel: Ziel = window, uhr: () => number = Date.now) {
  let zuletzt: number | null = null;
  const beiEingabe = () => {
    const jetzt = uhr();
    if (!sollMelden(jetzt, zuletzt)) return;
    zuletzt = jetzt;
    void melden();
  };
  for (const name of EREIGNISSE) ziel.addEventListener(name, beiEingabe, {passive: true, capture: true});
  return () => { for (const name of EREIGNISSE) ziel.removeEventListener(name, beiEingabe, {capture: true}); };
}
