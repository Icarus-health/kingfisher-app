import {useEffect, useState} from "react";
import {api} from "../api";
import {navigate} from "../ui";

const UEBERGANGEN = "kingfisher.erststart.spaeter";
// Geprüft wird einmal je Seitenaufruf; danach gilt der Hinweis auf der Startseite selbst.
let geprueft = false;

const uebergangen = () => {
  try { return sessionStorage.getItem(UEBERGANGEN) === "1"; } catch { return false; }
};

/**
 * Beim ersten Öffnen der Startseite: Ist die Einrichtung nicht abgeschlossen und fehlt Wesentliches, geht der
 * Assistent auf. Wer „Später weitermachen“ wählte, wird in dieser Sitzung nicht noch einmal gefragt. Antwortet der
 * Sidecar nicht, bleibt die Startseite, wie sie ist: Ein Ausfall darf nie in einen Assistenten sperren.
 * Gibt `true` zurück, solange noch geprüft wird (die Startseite zeigt dann noch nichts).
 */
export function useErststartWeiterleitung(pfad: string): boolean {
  const heute = pfad === "/today" || pfad === "/";
  const [prueft, setPrueft] = useState(heute && !geprueft && !uebergangen());
  useEffect(() => {
    if (!heute || geprueft || uebergangen()) { setPrueft(false); return; }
    geprueft = true;
    api.einrichtung().then(stand => {
      if (stand.zeigen) navigate("/willkommen");
      setPrueft(false);
    }).catch(() => setPrueft(false));
  }, [heute]);
  return prueft;
}

export const ERSTSTART_SPAETER = UEBERGANGEN;
