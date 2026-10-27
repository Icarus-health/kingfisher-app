import { useSyncExternalStore } from "react";
import { ansagen, type AnsageOrt } from "./ansageOrt.ts";

/** Der eine Ort für höfliche Ansagen (Paket B, B1), unsichtbar, einmal in der App. Was angesagt wird, steht auch sichtbar
 * auf der Seite; der Ort sagt es nur einmal, zur rechten Zeit. */
export function AnsageAnzeige({ ort = ansagen }: { ort?: AnsageOrt }) {
  const text = useSyncExternalStore(ort.abonnieren, ort.stand, ort.stand);
  return <div className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">{text}</div>;
}
