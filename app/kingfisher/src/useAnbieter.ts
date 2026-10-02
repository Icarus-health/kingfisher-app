import {useEffect, useState} from "react";
import {api, type AnbieterErkennung, type MailProvider} from "./api";
import type {GoogleKonfiguration} from "./googleWeg";
import {anbieterZurAdresse} from "./Einrichtung/schritte";

const adresseFertig = (adresse: string) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(adresse.trim());

/**
 * Der Anbieter zu einer Adresse, einmal gefragt: zuerst an der Endung (`gmail.com`), sonst fragt der Sidecar die eine
 * Anbieter-Erkennung (`anbieter_erkennen.py`: Google Workspace, Microsoft 365, nur über den Namensdienst des Rechners).
 * `erkennung` ist die ganze Antwort (Dienst und Art, für die Verzweigung im Mail-Schritt), `null` bei bekannter Endung
 * und solange nichts da ist. `prueft` ist wahr, solange die Antwort aussteht; erst danach fragt die Karte „Welcher
 * Anbieter?“.
 */
export function useAnbieter(adresse: string, katalog: MailProvider[]): {anbieter: MailProvider | null; prueft: boolean; erkennung: AnbieterErkennung | null} {
  const lokal = anbieterZurAdresse(adresse, katalog);
  const [gefunden, setGefunden] = useState<{adresse: string; erkennung: AnbieterErkennung | null} | null>(null);
  const fertig = adresseFertig(adresse);
  const sauber = adresse.trim().toLowerCase();
  useEffect(() => {
    if (lokal || !fertig) return;
    let aktiv = true;
    const uhr = window.setTimeout(() => {
      api.erkenneAnbieter(sauber).then(antwort => {
        if (aktiv) setGefunden({adresse: sauber, erkennung: antwort});
      }).catch(() => { if (aktiv) setGefunden({adresse: sauber, erkennung: null}); });
    }, 350);
    return () => { aktiv = false; window.clearTimeout(uhr); };
  }, [sauber, fertig, Boolean(lokal)]);
  if (lokal) return {anbieter: lokal, prueft: false, erkennung: null};
  if (!fertig) return {anbieter: null, prueft: false, erkennung: null};
  if (gefunden?.adresse !== sauber) return {anbieter: null, prueft: true, erkennung: null};
  // Der Katalog im Browser ist die Quelle der Anzeige; der Sidecar nennt nur, welcher Eintrag es ist.
  const vomServer = gefunden.erkennung?.provider ?? null;
  const eintrag = vomServer ? katalog.find(item => item.id === vomServer.id) ?? vomServer : null;
  return {anbieter: eintrag, prueft: false, erkennung: gefunden.erkennung};
}

/** Ist „Mit Google anmelden“ (OAuth) eingerichtet? `null`, solange es nicht bekannt ist. */
export function useGoogleKonfiguration(): GoogleKonfiguration {
  const [konfiguration, setKonfiguration] = useState<GoogleKonfiguration>(null);
  useEffect(() => {
    let aktiv = true;
    api.googleConfig().then(wert => { if (aktiv) setKonfiguration(wert); })
      .catch(() => { if (aktiv) setKonfiguration({configured: false, secure_storage: false}); });
    return () => { aktiv = false; };
  }, []);
  return konfiguration;
}
