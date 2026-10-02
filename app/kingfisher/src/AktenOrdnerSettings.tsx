import { useCallback, useEffect, useState } from "react";
import { ApiError, api, type AktenExport } from "./api";
import { aussage, kurzerPfad, unterwegs } from "./aktenOrdner";
import { fuerSystem, nurAufDemMac } from "./system";
import { useSystem } from "./useSystem";
import "./AktenOrdnerSettings.css";

// Einstellungen → Für Techniker → Akten als Ordner: die Akten als lesbarer Ordner (Markdown, für Obsidian oder jeden Editor).
// Nur zum Lesen: nichts aus dem Ordner fließt zurück. Aus, bis jemand einen Ordner wählt; gewählt wird im Dialog des Mac,
// nie getippt. Schreiben kann nur der Helfer der Kingfisher-App auf dem Mac; anderswo sagt die Karte das, statt eine
// Auswahl anzubieten, die nie ankommt (Befund 18, Sätze über system.ts). Ein Abschnitt für Techniker, nicht für den Alltag: weder die Startseite noch der Assistent verweisen darauf
// (sidecar: akten_export_routes.py, scripts/mac_folder_worker.py).
export function AktenOrdnerSettings() {
  const system = useSystem();
  const [daten, setDaten] = useState<AktenExport | null>(null);
  const [fehler, setFehler] = useState("");
  const [hinweis, setHinweis] = useState("");
  const [busy, setBusy] = useState(false);

  const laden = useCallback(async () => {
    try { setDaten(await api.aktenExport()); setFehler(""); }
    catch { setFehler("Der Stand konnte nicht geladen werden."); }
  }, []);
  useEffect(() => { void laden(); }, [laden]);
  const offen = unterwegs(daten);
  useEffect(() => {
    if (!offen || busy) return;
    const timer = window.setInterval(() => void laden(), 2500);
    return () => window.clearInterval(timer);
  }, [offen, busy, laden]);

  async function tun(aktion: () => Promise<AktenExport>, erfolg = "") {
    if (busy) return;
    setBusy(true); setFehler(""); setHinweis("");
    try { const neu = await aktion(); setDaten(neu); if (erfolg) setHinweis(erfolg); }
    catch (e) { setFehler(e instanceof ApiError && e.detail ? e.detail : "Das hat nicht geklappt. Bitte erneut versuchen."); }
    finally { setBusy(false); }
  }

  const wartet = Boolean(daten?.pick_request);
  const ohneHelfer = nurAufDemMac(system, "Das Schreiben in den Ordner");
  const stand = daten ? aussage(daten, ohneHelfer) : null;
  // Kein Helfer und nicht auf dem Mac: eine Auswahl wäre ein Knopf ohne Antwort.
  const nichtHier = Boolean(daten && !daten.running && system.art !== "mac");

  return <>
    <section className="source-section akten-ordner" aria-label="Akten als Ordner">
      <h2>Akten als Ordner</h2>
      <p>Schreibt deine Akten als lesbare Dateien in einen Ordner, zum Beispiel für Obsidian; sie sind nur zum Lesen, Änderungen dort fließen nicht zurück, und die Dateien enthalten Klartext.</p>
      {!daten && !fehler ? <p role="status">Wird geladen …</p> : null}
      {daten ? <>
        {wartet ? <div className="akten-ordner-block" role="status">
          <p>{fuerSystem("Bitte wähle den Ordner im Fenster, das sich auf deinem {Rechner} geöffnet hat.", system)}</p>
          {!daten.running ? <p>{nurAufDemMac(system, "Die Ordnerwahl im Fenster")}</p> : null}
          <div className="akten-ordner-aktionen"><button className="secondary-action" type="button" disabled={busy} onClick={() => void tun(() => api.aktenExportAuswahlAbbrechen())}>Abbrechen</button></div>
        </div> : null}

        {!daten.ordner && !wartet && nichtHier ? <div className="akten-ordner-block"><p>{nurAufDemMac(system, "Akten als Ordner")}</p></div> : null}
        {!daten.ordner && !wartet && !nichtHier ? <div className="akten-ordner-block">
          <p>Noch kein Ordner. Kingfisher schreibt nur in den Ordner, den du hier auswählst.</p>
          <div className="akten-ordner-aktionen">
            <button className="primary-action" type="button" disabled={busy} onClick={() => void tun(() => api.aktenExportOrdnerWaehlen("vorgabe"))}>Ordner „{daten.vorgabe}“ verwenden</button>
            <button className="secondary-action" type="button" disabled={busy} onClick={() => void tun(() => api.aktenExportOrdnerWaehlen("waehlen"))}>Anderen Ordner wählen …</button>
          </div>
          <small>Der Vorgabeordner wird angelegt, falls es ihn nicht gibt. Darin liegt ein Unterordner „{daten.ordnername}“; er wird bei jedem Schreiben ersetzt, alles andere im Ordner bleibt unberührt.</small>
        </div> : null}

        {daten.ordner ? <div className="akten-ordner-block">
          <p><strong>Ordner</strong> <span className="akten-ordner-pfad" title={daten.ordner}>{kurzerPfad(daten.ordner)}/{daten.ordnername}</span></p>
          <label className="akten-ordner-schalter"><input type="checkbox" checked={daten.aktiv} disabled={busy}
            onChange={event => void tun(() => api.aktenExportSetzen({ aktiv: event.target.checked }))} />
            <span>Akten in den Ordner schreiben</span></label>
          <label className="akten-ordner-schalter"><input type="checkbox" checked={daten.quellen} disabled={busy}
            onChange={event => void tun(() => api.aktenExportSetzen({ quellen: event.target.checked }))} />
            <span>Quellen mitschreiben</span></label>
          {daten.quellen ? <small>Mit Quellen enthält der Ordner den vollständigen Text deiner Mails, Termine und Notizen.</small> : null}
          {stand ? <p role={stand.fehler ? "alert" : "status"} className={stand.fehler ? "settings-error" : stand.ruhig ? "akten-ordner-ruhig" : undefined}>{stand.text}</p> : null}
          <div className="akten-ordner-aktionen">
            <button className="secondary-action" type="button" disabled={busy || daten.laeuft}
              onClick={() => void tun(() => api.aktenExportSchreiben(), "Die Akten wurden neu zusammengestellt.")}>Jetzt schreiben</button>
            <button className="secondary-action" type="button" disabled={busy || wartet} onClick={() => void tun(() => api.aktenExportOrdnerWaehlen("waehlen"))}>Anderen Ordner wählen …</button>
            <button className="text-action" type="button" disabled={busy}
              onClick={() => void tun(() => api.aktenExportOrdnerTrennen(), "Getrennt. Die Dateien in deinem Ordner bleiben liegen.")}>Ordner trennen</button>
          </div>
        </div> : null}
      </> : null}
      {hinweis ? <p role="status" className="akten-ordner-ruhig">{hinweis}</p> : null}
      {fehler ? <p role="alert" className="settings-error">{fehler} <button className="text-action" type="button" onClick={() => void laden()}>Erneut versuchen</button></p> : null}
    </section>
  </>;
}
