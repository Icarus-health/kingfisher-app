import {useEffect, useRef, useState} from "react";
import {api, type HintergrundStand, type MailIntakeStatus} from "../api";
import {abfrageAbstandMs, lerntFuss, lerntZeilen, prozent, type LerntZeile} from "./lernt";
import {MailErneut} from "./MailErneut";
import "./Einrichtung.css";

function kurzerFortschritt(zeile: LerntZeile) {
  const zahl = (wert: number) => wert.toLocaleString("de-DE");
  if (zeile.id === "modell") return zeile.fertig === null ? "Die KI wird geladen" : `KI: ${zahl(zeile.fertig)} %`;
  const einheit = zeile.id === "mail" || zeile.id === "sortieren" ? "Mails" : "Quellen";
  if (zeile.fertig !== null && zeile.gesamt !== null) return `${zahl(zeile.fertig)} von ${zahl(zeile.gesamt)} ${einheit}`;
  if (zeile.id === "mail" && zeile.fertig !== null) return `${zahl(zeile.fertig)} Mails bisher gelesen`;
  return zeile.id === "nachtrag" ? "Absender und Empfänger ergänzen" : "Fortschritt noch unklar";
}

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
    let vorher: string | null = null;
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
      // Gemeldet wird, wenn sich ändert, ob etwas läuft oder welche Zeilen dastehen (die Fertig-Seite zeigt eine Zahl
      // nur einmal, Paket S, Befund 6).
      const kennung = `${neu.length > 0}:${neu.map(zeile => zeile.id).join(",")}`;
      if (vorher !== kennung) { vorher = kennung; meldung.current?.(neu.length > 0, neu); }
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
  const schritte = zeilen.filter(zeile => zeile.id !== "mail_fehler");
  const probleme = zeilen.filter(zeile => zeile.id === "mail_fehler");
  // Quellen und Mailaufnahme haben unterschiedliche Gesamtzahlen; niemals zusammenrechnen.
  const haupt: LerntZeile | undefined = schritte.find(zeile => zeile.id === "einordnen") ?? schritte[0]
    ?? (hintergrund?.pausiert && hintergrund.fortschritt.gesamt > 0 ? {id: "einordnen", text: "", fertig: hintergrund.fortschritt.fertig, gesamt: hintergrund.fortschritt.gesamt} : undefined);
  const titel = hintergrund?.pausiert ? "Verarbeitung pausiert" : probleme.length && !haupt ? "Verarbeitung braucht Aufmerksamkeit" : fuss.grund ? "Verarbeitung wartet" : "Kingfisher lernt gerade";
  return <section className={`lernt${kompakt ? " lernt-kompakt" : ""}`} aria-label={titel} aria-live="polite">
    <div className="lernt-kopf"><h2>{titel}</h2>
      {fuss.knopf ? <button type="button" className="text-action lernt-knopf" disabled={arbeitet}
        onClick={() => void umschalten(fuss.knopf === "Pausieren")}>{fuss.knopf}</button> : null}
    </div>
    <details className="lernt-details">
      <summary><span>{haupt ? kurzerFortschritt(haupt) : "Fortschritt derzeit nicht verfügbar"}</span>
        {haupt && haupt.gesamt !== null && haupt.gesamt > 0 ? <progress max={100} value={prozent(haupt) ?? undefined} aria-label={kurzerFortschritt(haupt)} /> : null}
        <span className="lernt-mehr">Details</span>
      </summary>
    <div className="lernt-einzelheiten">
    <ul>{schritte.map(zeile => {
      const wert = prozent(zeile);
      return <li key={`${zeile.id}-${zeile.konto ?? ""}`}>
        <span>{zeile.text}</span>
        {zeile.gesamt !== null ? <progress max={100} value={wert ?? undefined} aria-label={zeile.text} /> : null}
      </li>;
    })}</ul>
    {fuss.grund ? <p className="lernt-grund">{fuss.grund}</p> : null}
    {fuss.satz ? <p className="lernt-hinweis">{fuss.satz}</p> : null}
    {kompakt ? null : <p className="lernt-hinweis">{fuss.grund ? "Du kannst Kingfisher weiter benutzen." : "Das läuft im Hintergrund weiter. Du kannst Kingfisher schon benutzen."}</p>}
    </div>
    </details>
    {probleme.length ? <ul className="lernt-probleme">{probleme.map(zeile => <li key={`${zeile.id}-${zeile.konto ?? ""}`} className="lernt-fehler">
      <span>{zeile.text}</span>
      {zeile.konto ? <MailErneut konto={zeile.konto} technik={zeile.technik} beiErgebnis={nachErneut} /> : null}
    </li>)}</ul> : null}
    {erneut && zeilen.some(zeile => zeile.id === "mail") ? <p className="lernt-grund" role="status">Kingfisher versucht es jetzt noch einmal. Scheitert es wieder, steht hier der Grund.</p> : null}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </section>;
}
