import { useEffect, useRef, useState } from "react";
import { Schalter } from "../grundlage";
import { api, ApiError, type ModelRoles } from "../api";
import { listenForCloudAccessChange } from "../cloudAccessEvents";
import { WIEDER_LOKAL, einschaltenMoeglich, frageArt, hintergrundZeile, statusSatz, zustimmungsSatz } from "./cloudEinordnung";
import { SCHALTER } from "./gliederung";

// „Neue Mails in der Cloud einordnen“: ein Schalter für die Rolle hintergrund, nur Anthropic, mit eigener Einwilligung
// in einem Satz (sidecar: hintergrund_cloud.py). Nur das Einordnen neuer Mails samt Bitten und Zusagen geht in die
// Cloud; Verdichtung, Lage und Entwürfe bleiben auf diesem Rechner. Aus ist die Vorgabe und mit einem Klick wieder
// erreicht. Gestaltung wie CloudSchalter.tsx (gleiche Klassen).

const fehlerText = (e: unknown) => e instanceof ApiError && e.detail ? e.detail : "Das konnte nicht gespeichert werden. Bitte erneut versuchen.";

export function CloudEinordnungSchalter() {
  const [rollen, setRollen] = useState<ModelRoles | null>(null);
  const [geladenFehler, setGeladenFehler] = useState(false);
  const [frage, setFrage] = useState(false);
  const [zugestimmt, setZugestimmt] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [hinweis, setHinweis] = useState("");
  const loadVersion = useRef(0);

  useEffect(() => {
    let aktiv = true;
    async function load() {
      const version = ++loadVersion.current;
      try {
        const daten = await api.modelRoles();
        if (aktiv && version === loadVersion.current) { setRollen(daten); setGeladenFehler(false); }
      } catch {
        if (aktiv && version === loadVersion.current) setGeladenFehler(true);
      }
    }
    const cloudAccessChanged = () => {
      setFrage(false); setZugestimmt(false); setFehler(""); setHinweis(""); setRollen(null); setGeladenFehler(false);
      void load();
    };
    void load();
    const unsubscribe = listenForCloudAccessChange(cloudAccessChanged);
    return () => { aktiv = false; loadVersion.current++; unsubscribe(); };
  }, []);

  const zeile = rollen ? hintergrundZeile(rollen.rollen) : null;
  const stand = zeile?.cloud_einordnung ?? null;
  const an = Boolean(stand?.aktiv);

  async function ausschalten() {
    setArbeitet(true); setFehler(""); setHinweis(""); setFrage(false);
    const version = loadVersion.current;
    try {
      const neu = await api.saveModelRole("hintergrund", { cloud: false });
      if (version !== loadVersion.current) return;
      setRollen(neu); setHinweis(WIEDER_LOKAL);
    } catch (e) { if (version === loadVersion.current) setFehler(fehlerText(e)); }
    finally { setArbeitet(false); }
  }

  async function einschalten() {
    if (!stand || !einschaltenMoeglich(stand, zugestimmt)) return;
    setArbeitet(true); setFehler(""); setHinweis("");
    const version = loadVersion.current;
    try {
      const neu = await api.saveModelRole("hintergrund", { cloud: true, anbieter: "anthropic", einwilligung: true });
      if (version !== loadVersion.current) return;
      setRollen(neu); setFrage(false); setZugestimmt(false);
      setHinweis("Neue Mails werden jetzt über Anthropic eingeordnet. Mit einem Klick auf den Schalter ist das wieder aus.");
    } catch (e) { if (version === loadVersion.current) setFehler(fehlerText(e)); }
    finally { setArbeitet(false); }
  }

  function umschalten(neu: boolean) {
    setHinweis(""); setFehler("");
    if (!neu) { void ausschalten(); return; }
    setZugestimmt(false); setFrage(true);
  }

  return <section className="darf-zeile" aria-label={SCHALTER.cloud_einordnung.titel}>
    {geladenFehler ? <p role="alert" className="settings-error">Der Stand konnte gerade nicht gelesen werden.</p> : !rollen ? <p>Wird geladen …</p> : !zeile || !stand ? null : <>
      <Schalter className="welt-schalter" titel={SCHALTER.cloud_einordnung.titel} satz={SCHALTER.cloud_einordnung.verlaesst} an={an || frage} deaktiviert={arbeitet} onWechsel={umschalten} />
      {an && <p className="source-hint" role="status">{statusSatz(stand)}</p>}
      {frage && !an && (frageArt(stand) === "ohne_zugang"
        ? <div className="darf-frage" role="group" aria-label="Cloud-Einordnung einschalten">
          <p>Dafür braucht es den vorbereiteten Claude-Zugang (Schlüssel und Modell) unter <a href="#ki">KI &amp; Modelle</a>. Bis dahin bleibt alles auf diesem Rechner.</p>
          <button type="button" className="secondary-action" onClick={() => setFrage(false)}>Verstanden</button>
        </div>
        : <div className="darf-frage" role="group" aria-label="Cloud-Einordnung einschalten">
          <label className="model-consent"><input type="checkbox" checked={zugestimmt} onChange={event => setZugestimmt(event.target.checked)} />
            <span>{zustimmungsSatz(zeile)}</span></label>
          <div className="darf-frage-knoepfe">
            <button type="button" className="primary-action" disabled={arbeitet || !einschaltenMoeglich(stand, zugestimmt)} onClick={() => void einschalten()}>Cloud-Einordnung einschalten</button>
            <button type="button" className="secondary-action" onClick={() => setFrage(false)}>Abbrechen</button>
          </div>
        </div>)}
    </>}
    {hinweis && <p role="status" className="source-hint">{hinweis}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}
