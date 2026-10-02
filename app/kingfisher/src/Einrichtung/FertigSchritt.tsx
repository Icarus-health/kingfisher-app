import {useEffect, useState} from "react";
import {api, ApiError, type MailIntakeStatus, type MemoryAutomation} from "../api";
import {PAUSIEREN_AUF_HEUTE, automatikAngebote, fertigLeerText, liestSatz, ordnetEin, schonDaZahlen, stummTitel} from "./fertig";
import {KingfisherLernt} from "./KingfisherLernt";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";
import {usePostfaecher} from "./usePostfaecher";
import {Verweis} from "../Verweis";

const zahl = (wert: number) => wert.toLocaleString("de-DE");

// Was schon da ist, in Zahlen, die stimmen (Fremdprobe 3, Befund 6): Die Termine werden erst nach dem Abgleich gezählt,
// danach alle paar Sekunden nachgesehen, solange die Seite offen ist.
function SchonDa({stand, intake}: {stand: SchrittProps["stand"]; intake: MailIntakeStatus | null}) {
  const [termine, setTermine] = useState<number | null>(null);
  useEffect(() => {
    let lebt = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function lesen() {
      const kalender = await api.calendarMemory().catch(() => null);
      if (!lebt) return;
      if (kalender) setTermine(kalender.mac_termine + kalender.quellen.reduce((summe, quelle) => summe + quelle.termine, 0));
      timer = setTimeout(lesen, 5000);
    }
    if (stand.vorhanden.kalender) void api.syncCalendarMemory().catch(() => undefined).then(() => { if (lebt) void lesen(); });
    return () => { lebt = false; clearTimeout(timer); };
  }, [stand.vorhanden.kalender]);
  const zahlen = schonDaZahlen({mail: stand.vorhanden.mail, kalender: stand.vorhanden.kalender, intake, termine});
  if (!zahlen.length) return null;
  return <dl className="erststart-zahlen" aria-label="Schon da">
    {zahlen.map(eintrag => <div key={eintrag.titel}><dt>{eintrag.titel}</dt><dd>{eintrag.wert === null ? "…" : zahl(eintrag.wert)}</dd></div>)}
  </dl>;
}

/**
 * (f) „Fertig – dein erstes Briefing entsteht jetzt“: Was schon da ist, was im Hintergrund noch läuft, und was
 * nicht geht. Antwortet ein Postfach nicht, steht das hier mit Grund und Knopf, statt „Dein Briefing ist bereit“
 * (Fremdprobe, Befund 5). Einmal angeboten, vorausgewählt: Mails einlesen und Quellen lokal sortieren (Befund 17).
 */
export function FertigSchritt({stand, weiter, zurueck, gehe}: SchrittProps) {
  const {stumm, prueft, pruefen} = usePostfaecher(stand.vorhanden.mail);
  const [intake, setIntake] = useState<MailIntakeStatus | null>(null);
  const [automatik, setAutomatik] = useState<MemoryAutomation | null>(null);
  const [einlesenAn, setEinlesenAn] = useState(true);
  const [sortierenAn, setSortierenAn] = useState(true);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");

  useEffect(() => {
    let lebt = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function lesen() {
      const neu = await api.mailIntake().catch(() => null);
      if (!lebt) return;
      if (neu) setIntake(neu);
      timer = setTimeout(lesen, 5000);
    }
    if (stand.vorhanden.mail) void lesen();
    api.memoryAutomation().then(wert => { if (lebt) setAutomatik(wert); }).catch(() => undefined);
    return () => { lebt = false; clearTimeout(timer); };
  }, [stand.vorhanden.mail]);

  const nichtsVerbunden = !stand.vorhanden.mail && !stand.vorhanden.kalender;
  const angebote = automatikAngebote(intake, automatik, stumm);
  const nichtEingelesen = (intake?.accounts ?? []).filter(konto => konto.connected && !konto.started).length;
  const leerText = fertigLeerText({mail: stand.vorhanden.mail, kalender: stand.vorhanden.kalender, stumm, nichtEingelesen});
  const namen = (ids: string[]) => (intake?.accounts ?? []).filter(konto => ids.includes(konto.account_id)).map(konto => konto.label).join(", ");

  async function zumBriefing() {
    if (arbeitet) return;
    setArbeitet(true); setFehler("");
    try {
      if (einlesenAn) for (const id of angebote.einlesen) {
        const umfang = await api.previewMailIntake(id);
        await api.startMailIntake(id, umfang.folders);
      }
      if (sortierenAn && angebote.sortieren) await api.setMemoryAutomation(true, angebote.sortierenSpaeter);
      await weiter({abgeschlossen: true});
    } catch (problem) {
      setFehler(problem instanceof ApiError && problem.detail ? problem.detail
        : "Das ließ sich gerade nicht einschalten. Nimm das Häkchen weg oder versuche es noch einmal.");
    } finally { setArbeitet(false); }
  }

  return <div className="erststart-inhalt">
    {nichtsVerbunden
      ? <p>Du hast noch nichts verbunden. Das Briefing bleibt deshalb leer, bis du Mail oder Kalender verbindest; das geht jederzeit unter <Verweis ziel="zugaenge" />.</p>
      : <p>Kingfisher liest jetzt, was du verbunden hast, und stellt daraus dein erstes Briefing zusammen.</p>}
    {stumm && stumm.length ? <section className="erststart-stumm" role="alert" aria-labelledby="erststart-stumm-titel">
      <h2 id="erststart-stumm-titel">{stummTitel(stumm)}</h2>
      {stumm.map(konto => <p key={konto.account_id}>{konto.satz}</p>)}
      <p className="source-hint">Bis dahin kommt dein Briefing ohne Mails aus.</p>
      <div className="erststart-knoepfe">
        <button type="button" className="primary-action" onClick={() => gehe("mail")}>Postfach prüfen</button>
        <button type="button" className="text-action" disabled={prueft} onClick={() => void pruefen()}>{prueft ? "Wird geprüft …" : "Erneut prüfen"}</button>
      </div>
    </section> : null}
    <SchonDa stand={stand} intake={intake} />
    <KingfisherLernt leerText={leerText} />
    {angebote.einlesen.length || angebote.sortieren ? <fieldset className="erststart-automatik">
      <legend>Soll Kingfisher von selbst weiterarbeiten?</legend>
      {angebote.einlesen.length ? <label><input type="checkbox" checked={einlesenAn} onChange={event => setEinlesenAn(event.target.checked)} />
        {" "}Mails von {namen(angebote.einlesen)} jetzt und danach regelmäßig einlesen</label> : null}
      {angebote.sortieren ? <label><input type="checkbox" checked={sortierenAn} onChange={event => setSortierenAn(event.target.checked)} />
        {" "}Quellen auf diesem Rechner sortieren{angebote.sortierenSpaeter ? ", sobald das Sprachmodell bereit ist" : ""}; daraus entstehen nur Vorschläge, zur Tatsache wird etwas erst mit deinem Ja</label> : null}
      <p className="source-hint">{PAUSIEREN_AUF_HEUTE}</p>
    </fieldset> : null}
    <div className="erststart-hintergrund">
      <h2>Was im Hintergrund passiert</h2>
      <ul>
        {liestSatz(stand.vorhanden) ? <li>{liestSatz(stand.vorhanden)}</li> : null}
        {ordnetEin(automatik, angebote, sortierenAn)
          ? <li>Es ordnet ein, wer wer ist und was zu welchem Projekt gehört. Was es dabei vermutet, schlägt es nur vor; es wird erst mit deinem Ja zur Tatsache.</li>
          : <li>Einordnen, wer wer ist und was zu welchem Projekt gehört, kann Kingfisher, sobald das automatische Sortieren läuft.</li>}
        <li>Du kannst Kingfisher schon benutzen. Je mehr es gelesen hat, desto besser wird das Briefing.</li>
      </ul>
    </div>
    {arbeitet ? <p role="status" className="source-hint">Wird eingeschaltet …</p> : null}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
    <SchrittFuss erledigt arbeitet={arbeitet} zurueck={zurueck} weiter={() => void zumBriefing()} ueberspringen={() => undefined} weiterText="Zum Briefing" />
  </div>;
}
