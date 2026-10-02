import {useCallback, useEffect, useRef, useState} from "react";
import {api, type PostfachErreichbar} from "../api";

/**
 * Antworten die verbundenen Postfächer gerade? Einmal beim Öffnen und auf Knopfdruck (`pruefen`), nie im Takt:
 * Jede Prüfung ist eine Anmeldung beim Anbieter. `stumm` ist `null`, solange noch keine Antwort da ist.
 */
export function usePostfaecher(aktiv: boolean) {
  const [konten, setKonten] = useState<PostfachErreichbar[] | null>(null);
  const [prueft, setPrueft] = useState(false);
  const lebt = useRef(true);
  useEffect(() => { lebt.current = true; return () => { lebt.current = false; }; }, []);

  const pruefen = useCallback(async () => {
    setPrueft(true);
    try {
      const antwort = await api.mailErreichbar();
      if (lebt.current) setKonten(antwort.accounts);
    } catch {
      // Ist Kingfisher selbst nicht erreichbar, lässt sich über das Postfach nichts sagen: keine Behauptung.
      if (lebt.current) setKonten([]);
    } finally { if (lebt.current) setPrueft(false); }
  }, []);
  useEffect(() => { if (aktiv) void pruefen(); }, [aktiv, pruefen]);

  const stumm = konten === null ? null : konten.filter(konto => !konto.erreichbar);
  return {konten, stumm, prueft, pruefen};
}
