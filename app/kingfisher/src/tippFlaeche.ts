// Tippflächen für kleine Zeichen (Persona-Prüfung, Paket H, H3): Wo Punkte zu dicht oder zu klein für einen Finger sind
// (Zeitstrahl der Akte), ist die ganze Spur das Ziel, und ein Tipp wählt den nächsten Punkt, wenn er nah genug liegt.

/** Der Index des Punktes, der `x` am nächsten liegt, wenn er höchstens `max` px entfernt ist; sonst `null`. */
export function naechsterPunkt(lagen: number[], x: number, max = 22): number | null {
  let beste: number | null = null;
  let abstand = Infinity;
  lagen.forEach((lage, i) => {
    const d = Math.abs(lage - x);
    if (d < abstand) { abstand = d; beste = i; }
  });
  return beste !== null && abstand <= max ? beste : null;
}
