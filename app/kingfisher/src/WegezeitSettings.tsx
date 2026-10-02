import { useEffect, useState } from "react";
import { api, ApiError, type WegezeitStand } from "./api";
import { Verweis } from "./Verweis";
import { wegezeitSchalter } from "./wegezeitSchalter";
import { SCHALTER } from "./Einstellungen/gliederung";

const DIENSTE = { openrouteservice: "OpenRouteService", google: "Google Routen" } as const;
const MITTEL = { auto: "Auto", oepnv: "Bus und Bahn", fuss: "zu Fuß" } as const;

// Der Stand der Wegezeit-Einstellung und das Speichern mit Rückmeldung. Die Schalterzeile unter „Was Kingfisher darf“
// und der Kartendienst hinter „Für Techniker“ benutzen beide diesen Stand.
function useWegezeit(beiAenderung?: (stand: WegezeitStand) => void) {
  const [stand, setStand] = useState<WegezeitStand | null>(null);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.wegezeit().then(daten => { if (aktiv) setStand(daten); }).catch(() => { if (aktiv) setFehler("Die Einstellung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);
  async function ausfuehren(aktion: () => Promise<WegezeitStand>, text: string) {
    setArbeitet(true); setFehler(""); setGespeichert("");
    try { const neu = await aktion(); setStand(neu); setGespeichert(text); beiAenderung?.(neu); }
    catch (problem) { setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Das konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }
  return { stand, arbeitet, fehler, gespeichert, ausfuehren };
}

// „Wegezeit berechnen“: Vorgabe aus. Nur mit dieser Einwilligung verlassen zwei Adressen den Rechner
// (Startort und Ort des Termins), und zwar an Apple Karten auf dem Mac oder an den Routenplaner, den man selbst einträgt.
// Einschalten geht erst, wenn es rechnen kann (Befund 19): Fehlt der Startort, steht hier sein Feld (gespeichert wird er
// an derselben Stelle wie unter „Kingfisher und du“); fehlt ein Kartendienst, sagt ein Satz das und verweist nach hinten.
// `beiAenderung` meldet jeden neuen Stand sofort (die Marke im Assistenten zeigt dann „An“ ohne Neuladen).
export function WegezeitSettings({ beiAenderung }: { beiAenderung?: (stand: WegezeitStand) => void } = {}) {
  const { stand, arbeitet, fehler, gespeichert, ausfuehren } = useWegezeit(beiAenderung);
  const [startort, setStartort] = useState("");
  const schalter = stand ? wegezeitSchalter(stand) : null;
  return <section className="darf-zeile" aria-label={SCHALTER.wegezeit.titel}>
    {!stand || !schalter ? <p>Wird geladen …</p> : <>
      <label className="wegezeit-schalter"><input type="checkbox" role="switch" checked={schalter.an} disabled={arbeitet || schalter.gesperrt}
        onChange={event => void ausfuehren(() => api.wegezeitSetzen({ aktiv: event.target.checked }), event.target.checked ? "Wegezeit wird berechnet." : "Wegezeit wird nicht mehr berechnet.")} />
        <span><strong>{SCHALTER.wegezeit.titel}</strong><small>{SCHALTER.wegezeit.verlaesst}</small></span></label>
      {schalter.gesperrt && schalter.fehlt === "startort" ? <form className="wegezeit-startort" onSubmit={event => {
        event.preventDefault();
        if (startort.trim()) void ausfuehren(() => api.wegezeitSetzen({ heimat: startort.trim() }), "Startort gespeichert. Jetzt kannst du die Wegezeit einschalten.");
      }}>
        <p className="source-hint" role="status">{stand.fehlt_satz || "Für die Wegezeit fehlt noch dein Startort."}</p>
        <label htmlFor="wegezeit-startort">Von wo startest du meistens?</label>
        <div><input id="wegezeit-startort" value={startort} maxLength={300} autoComplete="street-address" placeholder="Straße, Ort" disabled={arbeitet} onChange={event => setStartort(event.target.value)} />
          <button type="submit" className="secondary-action" disabled={arbeitet || !startort.trim()}>Startort speichern</button></div>
      </form> : null}
      {schalter.gesperrt && schalter.fehlt === "dienst" ? <p className="source-hint" role="status">{stand.fehlt_satz} Er hinterlegt den Schlüssel unter <Verweis ziel="technik-kartendienst" />.</p> : null}
      {stand.aktiv && <>
        <p className="source-hint">{stand.heimat
          ? <>Startort: {stand.heimat}. Ändern kannst du ihn unter <Verweis ziel="ich" />.</>
          : <>Dir fehlt noch ein Startort. Trag ihn unter <Verweis ziel="ich" /> ein.</>}</p>
        <label htmlFor="wegezeit-mittel">Womit fährst du meistens?</label>
        <select id="wegezeit-mittel" value={stand.verkehrsmittel} disabled={arbeitet}
          onChange={event => void ausfuehren(() => api.wegezeitSetzen({ verkehrsmittel: event.target.value as WegezeitStand["verkehrsmittel"] }), "Gespeichert.")}>
          {Object.entries(MITTEL).map(([wert, name]) => <option key={wert} value={wert}>{name}</option>)}
        </select>
        <p className="source-hint">{stand.dienste.apple ? "Apple Karten ist auf diesem Mac bereit."
          : (stand.dienste.openrouteservice || stand.dienste.google) ? "Ein eigener Routenplaner ist eingerichtet."
          : "Ohne Apple Karten braucht die Wegezeit einen eigenen Routenplaner; den richtet ein Techniker ein."}</p>
      </>}
    </>}
    {gespeichert && <p role="status" className="source-hint">{gespeichert}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}

// Hinter „Für Techniker“: der Kartendienst für die Wegezeit, nötig nur ohne Apple Karten.
export function WegezeitKartendienst() {
  const { stand, arbeitet, fehler, gespeichert, ausfuehren } = useWegezeit();
  const [schluessel, setSchluessel] = useState("");
  const [dienst, setDienst] = useState<keyof typeof DIENSTE>("openrouteservice");
  return <section className="source-section" aria-label="Kartendienst für die Wegezeit">
    <p className="source-hint">Nur nötig ohne Apple Karten. Der Schlüssel liegt im Schlüsselbund dieses Rechners und wird nie wieder angezeigt.</p>
    {!stand ? <p>Wird geladen …</p> : <>
      <form onSubmit={event => { event.preventDefault(); if (schluessel.trim()) void ausfuehren(() => api.wegezeitSchluessel(dienst, schluessel.trim()), "Schlüssel gespeichert.").then(() => setSchluessel("")); }}>
        <label htmlFor="wegezeit-dienst">Kartendienst</label>
        <select id="wegezeit-dienst" value={dienst} onChange={event => setDienst(event.target.value as keyof typeof DIENSTE)}>
          {Object.entries(DIENSTE).map(([wert, name]) => <option key={wert} value={wert}>{name}</option>)}
        </select>
        <label htmlFor="wegezeit-schluessel">Schlüssel</label>
        <input id="wegezeit-schluessel" type="password" autoComplete="off" value={schluessel} onChange={event => setSchluessel(event.target.value)} />
        <button type="submit" className="secondary-action" disabled={arbeitet || schluessel.trim().length < 8}>Schlüssel speichern</button>
        {stand.schluessel_hinterlegt[dienst] && <button type="button" className="secondary-action" disabled={arbeitet}
          onClick={() => void ausfuehren(() => api.wegezeitSchluesselLoeschen(dienst), "Schlüssel entfernt.")}>Schlüssel entfernen</button>}
      </form>
      {stand.schluessel_hinterlegt[dienst] && <p className="source-hint" role="status">{`Für ${DIENSTE[dienst]} ist ein Schlüssel hinterlegt.`}</p>}
    </>}
    {gespeichert && <p role="status" className="source-hint">{gespeichert}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}
