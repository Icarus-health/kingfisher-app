// „Kingfisher lernt gerade“: aus dem, was der Sidecar schon meldet, die wenigen Zeilen, die jetzt wirklich laufen.
// Reine Logik (ohne React, testbar mit node --test). Es zählt nur, was läuft; sonst ist die Liste leer und nichts wird gezeigt.
import type {HintergrundStand, MailIntakeStatus, ModellLaden} from "../api";
import {deriveIntakeProgress} from "../mailIntakeProgress.ts";

export type LerntZeile = {
  id: "modell" | "einordnen" | "mail" | "mail_fehler" | "nachtrag" | "sortieren" | "akten"; text: string; fertig: number | null; gesamt: number | null;
  /** Bei `mail_fehler`: das Konto für „Erneut versuchen“ und die Angabe für „Für Techniker“. */
  konto?: string; technik?: string | null;
};

const zahl = (wert: number) => wert.toLocaleString("de-DE");

// Zustände, in denen die Einordnung noch etwas vor sich hat und die Zeile erscheint.
const IM_GANG = new Set(["laeuft", "wartet", "pausiert"]);

/** „fertig etwa morgen Mittag“ aus der Schätzung des Sidecars; ohne Messung „noch unklar“, pausiert ohne Zeit. */
export function fertigText(stand: HintergrundStand): string {
  if (stand.zustand === "pausiert") return "pausiert";
  const text = stand.schaetzung?.text;
  if (text) return text.startsWith("in ") ? `fertig ${text}` : `fertig etwa ${text}`;
  return "wann es fertig ist, ist noch unklar";
}

/** Die Zeilen für die Anzeige. `akten` ist der Stand der Berechnung (`null`, wenn nichts offen ist);
 * `hintergrund` der Stand der Einordnung aller Quellen mit Schätzung (`GET /api/v1/hintergrund`). */
export function lerntZeilen(intake: MailIntakeStatus | null, akten: {offen: number; gesamt: number} | null,
  hintergrund: HintergrundStand | null = null, laden: Pick<ModellLaden, "laeuft" | "prozent"> | null = null): LerntZeile[] {
  const zeilen: LerntZeile[] = [];

  // Das Sprachmodell lädt im Hintergrund (Fremdprobe 2, Befund 6): zuerst, mit Prozent, bis es fertig ist.
  if (laden?.laeuft) zeilen.push({id: "modell", fertig: laden.prozent, gesamt: 100, text: `Kingfisher lädt sein Sprachmodell: ${laden.prozent} %`});

  // Die Gesamtzeile: alle Quellen, nicht nur Mails, mit der Schätzung aus der gemessenen Rate.
  const einordnen = hintergrund !== null && IM_GANG.has(hintergrund.zustand) && hintergrund.fortschritt.offen > 0;
  if (einordnen) {
    const {fertig, gesamt} = hintergrund.fortschritt;
    zeilen.push({id: "einordnen", fertig, gesamt, text: `${zahl(fertig)} von ${zahl(gesamt)} Quellen, ${fertigText(hintergrund)}`});
  }
  const konten = (intake?.accounts ?? []).filter(konto => konto.started && konto.connected && !konto.paused);
  const fortschritt = konten.map(konto => deriveIntakeProgress(konto));

  // Mails lesen: solange die Aufnahme des Bestands nicht durch ist. Der Satz ist die eine Aussage des Sidecars über das
  // Postfach (mail_stand.py, Fremdprobe 2, Befund 17): dieselbe wie unter „Für Techniker“; ein leeres Postfach liest nicht.
  const liest = konten.filter((konto, i) => konto.stand ? konto.stand.zustand === "liest"
    : fortschritt[i].stage === "inventory" || fortschritt[i].stage === "capture");
  if (liest.length) {
    const stand = liest.map(konto => fortschritt[konten.indexOf(konto)]);
    const fertig = liest.reduce((summe, konto, i) => summe + (konto.stand?.gelesen ?? stand[i].processed), 0);
    const gesamtJe = liest.map((konto, i) => konto.stand ? konto.stand.gesamt : stand[i].total);
    const alle = gesamtJe.every(wert => wert !== null) ? gesamtJe.reduce((summe: number, wert) => summe + (wert ?? 0), 0) : null;
    const saetze = liest.map(konto => konto.stand?.satz).filter((satz): satz is string => Boolean(satz));
    zeilen.push({
      id: "mail", fertig, gesamt: alle,
      text: saetze.length === liest.length ? saetze.join(" ")
        : alle === null ? `Deine Mails werden gelesen: bisher ${zahl(fertig)} gefunden`
        : `Deine Mails werden gelesen: ${zahl(fertig)} von ${zahl(alle)}`,
    });
  }

  // Mails kamen nicht ins Gedächtnis (Fremdprobe 3, Befund 2): der Satz mit dem Grund, je Postfach, statt „wird gelesen“.
  for (const konto of konten) {
    if (konto.stand?.zustand === "gescheitert") {
      zeilen.push({id: "mail_fehler", text: konto.stand.satz, fertig: null, gesamt: null, konto: konto.account_id, technik: konto.stand.technik ?? null});
    }
  }

  // Absender und Empfänger älterer Mails nachtragen.
  const offenNachtrag = konten.reduce((summe, konto) => {
    const nachtrag = konto.empfaengernachtrag;
    return summe + (nachtrag && !nachtrag.fertig ? nachtrag.offen : 0);
  }, 0);
  if (offenNachtrag > 0) {
    zeilen.push({id: "nachtrag", fertig: null, gesamt: null, text: `Bei älteren Mails werden Absender und Empfänger ergänzt: noch ${zahl(offenNachtrag)}`});
  }

  // Nach Themen sortieren, nur wenn das auch geschieht (lokale Sortierung eingeschaltet) und etwas übrig ist.
  // Sortieren ist Teil der Gesamtzeile; steht die da, erscheint dieselbe Arbeit nicht ein zweites Mal.
  if (!einordnen && intake?.analysis_active !== false) {
    const sortiert = fortschritt.filter(stand => stand.sources > 0 && stand.analyzed < stand.analysisSources && stand.stage !== "disconnected");
    if (sortiert.length) {
      const fertig = sortiert.reduce((summe, stand) => summe + stand.analyzed, 0);
      const alle = sortiert.reduce((summe, stand) => summe + stand.analysisSources, 0);
      zeilen.push({id: "sortieren", fertig, gesamt: alle, text: `Deine Mails werden nach Themen sortiert: ${zahl(fertig)} von ${zahl(alle)}`});
    }
  }

  // Akten zusammenstellen: Personen, Projekte, Orte.
  if (akten && akten.offen > 0) {
    const fertig = Math.max(0, akten.gesamt - akten.offen);
    zeilen.push({id: "akten", fertig, gesamt: akten.gesamt, text: `Personen, Projekte und Orte werden zusammengestellt: noch ${zahl(akten.offen)} Quellen`});
  }
  return zeilen;
}

/** Was unter den Zeilen steht: der Satz zum Anbleiben, warum gerade gewartet wird, und welcher Knopf passt.
 * `liestMails`: Das Einlesen läuft auch ohne Modell im Hintergrund und hält mit derselben Pause an; dann gehört der
 * Knopf ebenfalls hierher, denn Assistent und Fertig-Seite verweisen fürs Anhalten auf Heute (Fremdprobe 3, Befund 5). */
export function lerntFuss(stand: HintergrundStand | null, liestMails = false): {satz: string | null; grund: string | null; knopf: "Pausieren" | "Weiter" | null} {
  if (!stand) return {satz: null, grund: null, knopf: null};
  if (!IM_GANG.has(stand.zustand) || stand.fortschritt.offen <= 0) {
    return liestMails ? {satz: null, grund: null, knopf: stand.pausiert ? "Weiter" : "Pausieren"} : {satz: null, grund: null, knopf: null};
  }
  return {satz: stand.zustand === "pausiert" ? null : stand.satz, grund: stand.grund, knopf: stand.pausiert ? "Weiter" : "Pausieren"};
}

/** Prozent für einen Balken; `null`, wenn der Umfang noch unbekannt ist. */
export const prozent = (zeile: LerntZeile) =>
  zeile.gesamt && zeile.fertig !== null ? Math.min(99, Math.floor(100 * zeile.fertig / zeile.gesamt)) : null;

// Wie oft nachgesehen wird: zügig, solange etwas läuft, sonst gemächlich (ein neuer Lauf soll sich zeigen, ohne zu belasten).
export const abfrageAbstandMs = (laeuft: boolean) => (laeuft ? 4000 : 20000);
