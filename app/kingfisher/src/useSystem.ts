import { useEffect, useState } from "react";
import { api } from "./api";
import { UNBEKANNT, eingabegeraetAus, type Eingabegeraet, type SystemAngabe } from "./system";

// Die Angabe, auf welchem System Kingfisher läuft, einmal je Seitenaufruf geholt und geteilt (system.ts). Bis sie da
// ist, und wenn sie nicht kommt, gilt die neutrale Angabe: „Rechner“ stimmt immer.
let angabe: SystemAngabe | null = null;
let unterwegs: Promise<SystemAngabe> | null = null;

function holen(): Promise<SystemAngabe> {
  unterwegs ??= api.system().then(wert => (angabe = wert)).catch(() => UNBEKANNT);
  return unterwegs;
}

export function useSystem(): SystemAngabe {
  const [wert, setWert] = useState<SystemAngabe>(angabe ?? UNBEKANNT);
  useEffect(() => {
    let aktiv = true;
    if (!angabe) void holen().then(neu => { if (aktiv) setWert(neu); });
    return () => { aktiv = false; };
  }, []);
  return wert;
}

/** Das Gerät des Betrachters, einmal aus dem Browser gelesen (für den Tastenhinweis am Suchfeld). */
export function useEingabegeraet(): Eingabegeraet {
  const [wert] = useState<Eingabegeraet>(() => {
    if (typeof navigator === "undefined") return { mac: false, nurTouch: false };
    const daten = (navigator as Navigator & { userAgentData?: { platform?: string } }).userAgentData;
    const nurTouch = typeof window !== "undefined" && typeof window.matchMedia === "function"
      && window.matchMedia("(hover: none) and (pointer: coarse)").matches;
    return eingabegeraetAus({ plattform: daten?.platform || navigator.platform, userAgent: navigator.userAgent, nurTouch });
  });
  return wert;
}
