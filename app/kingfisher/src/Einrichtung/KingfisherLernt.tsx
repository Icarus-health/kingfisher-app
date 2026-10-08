import {useEffect, useRef, useState} from "react";
import {api, type HintergrundStand, type MailIntakeStatus} from "../api";
import {abfrageAbstandMs, lerntFuss, lerntZeilen, prozent, type LerntZeile} from "./lernt";
import {MailErneut} from "./MailErneut";
import "./Einrichtung.css";

/** Current work, plus an explicit pause that must remain possible to release. */
export function KingfisherLernt({kompakt = false, beiAenderung, leerText}: {
  kompakt?: boolean;
  /** Wird gerufen, wenn sich ändert, ob etwas läuft (die Startseite entscheidet damit über ihren Hinweis). */
  beiAenderung?: (laeuft: boolean, zeilen: LerntZeile[]) => void;
  /** Steht statt Nichts da, wenn nichts läuft (nur in der Einrichtung, damit der Bereich nicht leer wirkt). */
  leerText?: string;
}) {
  const [zeilen, setZeilen] = useState<LerntZeile[] | null>(null);
  const [hintergrund, setHintergrund] = useState<HintergrundStand | null>(null);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [erneut, setErneut] = useState(false);
  const [abgleich, setAbgleich] = useState(0);
  const meldung = useRef(beiAenderung);
  meldung.current = beiAenderung;
  // Was außer den Mails zuletzt gelesen wurde, damit ein „Erneut versuchen“ die Zeilen sofort neu bilden kann.
  const zuletzt = useRef<{akten: {offen: number; gesamt: number} | null; hintergrund: HintergrundStand | null; laden: Parameters<typeof lerntZeilen>[3]}>({akten: null, hintergrund: null, laden: null});

  useEffect(() => {
    let lebt = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let vorher: boolean | null = null;
    async function lesen() {
      if (document.visibilityState !== "visible") { timer = setTimeout(lesen, abfrageAbstandMs(false)); return; }
      const [intake, akten, hinten, laden] = await Promise.allSettled([api.mailIntake(), api.lernt(), api.hintergrund(), api.modellLaden()]);
      if (!lebt) return;
      // Fällt eine Quelle aus, bleibt die andere sichtbar; ein Fehler zeigt sich nicht als Meldung, sondern als „nichts“.
      const status: MailIntakeStatus | null = intake.status === "fulfilled" ? intake.value : null;
      const stand = akten.status === "fulfilled" ? akten.value.akten : null;
      const hintergrundStand = hinten.status === "fulfilled" ? hinten.value : null;
      zuletzt.current = {akten: stand, hintergrund: hintergrundStand, laden: laden.status === "fulfilled" ? laden.value : null};
      const neu = lerntZeilen(status, stand, hintergrundStand, zuletzt.current.laden);
      setHintergrund(hintergrundStand);
      setZeilen(neu);
      if (vorher !== neu.length > 0) { vorher = neu.length > 0; meldung.current?.(vorher, neu); }
      timer = setTimeout(lesen, abfrageAbstandMs(neu.length > 0));
    }
    void lesen();
    return () => { lebt = false; clearTimeout(timer); };
  }, [abgleich]);

  async function umschalten(pause: boolean) {
    setArbeitet(true); setFehler("");
    try {
      const neu = await api.hintergrundPausieren(pause);
      setHintergrund(neu);
      setZeilen(vorher => (vorher ?? []).map(zeile => zeile.id === "einordnen" ? lerntZeilen(null, null, neu).find(z => z.id === "einordnen") ?? zeile : zeile));
      // Invalidate pending old reads and reload all progress, including mail.
      setAbgleich(wert => wert + 1);
    } catch {
      setFehler("Das hat gerade nicht geklappt. Bitte versuche es noch einmal.");
    } finally {
      setArbeitet(false);
    }
  }

  function nachErneut(status: MailIntakeStatus) {
    const {akten, hintergrund: hinten, laden} = zuletzt.current;
    setZeilen(lerntZeilen(status, akten, hinten, laden));
    setErneut(true);
  }

  if (zeilen === null) return null;
  const fuss = lerntFuss(hintergrund, zeilen.some(zeile => zeile.id === "mail"));
  if (zeilen.length === 0 && !hintergrund?.pausiert) return leerText ? <p className="lernt-leer" role="status">{leerText}</p> : null;
  const titel = hintergrund?.pausiert ? "Verarbeitung pausiert" : fuss.grund ? "Verarbeitung wartet" : "Kingfisher lernt gerade";
  return <section className={`lernt${kompakt ? " lernt-kompakt" : ""}`} aria-label={titel} aria-live="polite">
    <h2>{titel}</h2>
    <ul>{zeilen.map(zeile => {
      const wert = prozent(zeile);
      return <li key={`${zeile.id}-${zeile.konto ?? ""}`} className={zeile.id === "mail_fehler" ? "lernt-fehler" : undefined}>
        <span>{zeile.text}</span>
        {zeile.gesamt !== null ? <progress max={100} value={wert ?? undefined} aria-label={zeile.text} /> : null}
        {zeile.id === "mail_fehler" && zeile.konto ? <MailErneut konto={zeile.konto} technik={zeile.technik} beiErgebnis={nachErneut} /> : null}
      </li>;
    })}</ul>
    {erneut && zeilen.some(zeile => zeile.id === "mail") ? <p className="lernt-grund" role="status">Kingfisher versucht es jetzt noch einmal. Scheitert es wieder, steht hier der Grund.</p> : null}
    {fuss.grund ? <p className="lernt-grund">{fuss.grund}</p> : null}
    {fuss.satz ? <p className="lernt-hinweis">{fuss.satz}</p> : null}
    {kompakt ? null : <p className="lernt-hinweis">{fuss.grund ? "Du kannst Kingfisher weiter benutzen." : "Das läuft im Hintergrund weiter. Du kannst Kingfisher schon benutzen."}</p>}
    {fuss.knopf ? <button type="button" className="text-action lernt-knopf" disabled={arbeitet}
      onClick={() => void umschalten(fuss.knopf === "Pausieren")}>{fuss.knopf}</button> : null}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </section>;
}
