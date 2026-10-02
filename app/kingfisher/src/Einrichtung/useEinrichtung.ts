import {useCallback, useEffect, useRef, useState} from "react";
import {api, type EinrichtungAenderung, type EinrichtungStand} from "../api";

/** Der Stand der Einrichtung vom Sidecar: laden, ändern (mit Antwort), neu lesen. `fehler` heißt: nicht erreichbar. */
export function useEinrichtung() {
  const [stand, setStand] = useState<EinrichtungStand | null>(null);
  const [fehler, setFehler] = useState(false);
  const lebt = useRef(true);
  useEffect(() => { lebt.current = true; return () => { lebt.current = false; }; }, []);

  const laden = useCallback(async () => {
    try { const neu = await api.einrichtung(); if (lebt.current) { setStand(neu); setFehler(false); } return neu; }
    catch { if (lebt.current) setFehler(true); return null; }
  }, []);
  useEffect(() => { void laden(); }, [laden]);

  const aendern = useCallback(async (aenderung: EinrichtungAenderung) => {
    try { const neu = await api.einrichtungSetzen(aenderung); if (lebt.current) { setStand(neu); setFehler(false); } return neu; }
    catch { if (lebt.current) setFehler(true); return null; }
  }, []);

  return {stand, fehler, laden, aendern};
}
