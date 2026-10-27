import { useState } from "react";
import { api, ApiError, type PersonLoeschVorschau } from "./api";
import { Rueckfrage, zeigeHinweis } from "./grundlage";
import { exportSatz, geloeschtSatz, loeschRueckfrage } from "./personDaten";
import { memoryReturnPath } from "./profileReturn";
import { navigate } from "./ui";

/**
 * Personenakte → „Mehr“ (Persona-Prüfung, Paket P, D7): alles zu dieser Person exportieren (Auskunft) oder löschen.
 * Leise eingeklappt unter dem Kopf der Akte, keine eigene Seite. Der Export geht nur als Datei auf diesen Rechner; das
 * Löschen fragt vorher in einem Satz (`Rueckfrage`, Fokus auf „Abbrechen“) und nennt, was gelöscht wird und was bleibt.
 */
export function PersonMehr({ angabe, name }: { angabe: string; name: string }) {
  const [laeuft, setLaeuft] = useState<"" | "export" | "zaehlen" | "loeschen">("");
  const [meldung, setMeldung] = useState<{ text: string; fehler: boolean } | null>(null);
  const [vorschau, setVorschau] = useState<PersonLoeschVorschau | null>(null);
  const [dialogFehler, setDialogFehler] = useState("");

  function grund(problem: unknown, sonst: string) {
    return problem instanceof ApiError && problem.detail ? problem.detail : sonst;
  }

  async function exportieren() {
    if (laeuft) return;
    setLaeuft("export"); setMeldung(null);
    try {
      const { datei, name: dateiname } = await api.personAuskunft(angabe);
      const adresse = URL.createObjectURL(datei);
      const link = document.createElement("a");
      link.href = adresse; link.download = dateiname; document.body.appendChild(link); link.click(); link.remove();
      window.setTimeout(() => URL.revokeObjectURL(adresse), 60_000);
      setMeldung({ text: exportSatz(dateiname), fehler: false });
    } catch (problem) {
      setMeldung({ text: grund(problem, "Die Auskunft konnte nicht erstellt werden. Bitte versuche es noch einmal."), fehler: true });
    } finally { setLaeuft(""); }
  }

  async function fragen() {
    if (laeuft) return;
    setLaeuft("zaehlen"); setMeldung(null); setDialogFehler("");
    try { setVorschau(await api.personLoeschenVorschau(angabe)); }
    catch (problem) { setMeldung({ text: grund(problem, "Kingfisher konnte nicht zählen, was gelöscht würde. Es wurde nichts gelöscht."), fehler: true }); }
    finally { setLaeuft(""); }
  }

  async function loeschen() {
    setLaeuft("loeschen"); setDialogFehler("");
    try {
      const ergebnis = await api.personLoeschen(angabe);
      setVorschau(null);
      zeigeHinweis({ text: geloeschtSatz(ergebnis.name), verweis: { text: "Einstellungen", href: "/settings#ich" } });
      navigate(memoryReturnPath(window.location.search, "person"));
    } catch (problem) {
      setDialogFehler(grund(problem, "Das Löschen hat nicht geklappt. Bitte versuche es noch einmal."));
    } finally { setLaeuft(""); }
  }

  const frage = vorschau ? loeschRueckfrage(vorschau) : null;
  return <details className="person-mehr quiet-details">
    <summary>Mehr</summary>
    <div className="person-mehr-inhalt">
      <div className="person-mehr-zeile">
        <p>Alles, was Kingfisher über {name} weiß und woher, als Datei für dich, etwa für eine Auskunft nach der DSGVO.</p>
        <button type="button" className="g-knopf-getoent" aria-disabled={laeuft !== "" || undefined} onClick={() => void exportieren()}>
          {laeuft === "export" ? "Wird erstellt …" : "Alles exportieren"}</button>
      </div>
      <div className="person-mehr-zeile">
        <p>Alles zu {name} aus Kingfisher löschen. Postfach und Kalender bleiben, wie sie sind.</p>
        <button type="button" className="g-knopf-getoent person-mehr-loeschen" aria-disabled={laeuft !== "" || undefined} onClick={() => void fragen()}>
          {laeuft === "zaehlen" ? "Wird gezählt …" : "Alles löschen …"}</button>
      </div>
      {meldung ? <p className={meldung.fehler ? "settings-error person-mehr-meldung" : "source-hint person-mehr-meldung"} role={meldung.fehler ? "alert" : "status"}>{meldung.text}</p> : null}
    </div>
    {frage ? <Rueckfrage frage={frage.frage} satz={frage.satz} bestaetigen="Endgültig löschen" rot
      arbeitet={laeuft === "loeschen"} fehler={dialogFehler || undefined} className="person-loeschen-frage"
      onAbbrechen={() => { setVorschau(null); setDialogFehler(""); }} onBestaetigen={() => void loeschen()}>
      {frage.geloescht.length ? <div className="person-loeschen-teil"><h3>Gelöscht wird</h3><ul>{frage.geloescht.map(z => <li key={z}>{z}</li>)}</ul></div> : null}
      <div className="person-loeschen-teil"><h3>Bleibt</h3><ul>{frage.bleibt.map(z => <li key={z}>{z}</li>)}</ul></div>
    </Rueckfrage> : null}
  </details>;
}
