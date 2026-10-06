import {useCallback, useEffect, useReducer, useState, type ReactNode} from "react";
import {api} from "../api";
import {TranscriptSettings} from "../TranscriptSettings";
import {WegezeitSettings} from "../WegezeitSettings";
import {Wetter} from "../WeltSettings";
import {SchrittFuss, type SchrittProps} from "./SchrittFuss";
import {Verweis} from "../VerweisLink";
import {FREIGABEN_START, freigabenErledigt, freigabenWeiter, wetterHinweis, type FreigabeId} from "./freigaben";

type Zeile = {id: FreigabeId; titel: string; satz: string; inhalt: ReactNode; hinweis?: string | null};

// „Was darf Kingfisher noch?“ Alles ist aus, bis man es einschaltet. Jede Zeile sagt in einem Satz, was passiert, und
// öffnet beim Einrichten die vorhandene Einstellung; eine zweite Fassung davon gibt es nicht. Jede Änderung meldet sich
// sofort: Die Marke folgt dem Schalter, und wer etwas angefasst hat, geht mit „Weiter“ statt „Überspringen“ weiter
// (Fremdprobe 3, Befund 4).
export function FreigabenSchritt({weiter, ueberspringen, zurueck}: SchrittProps) {
  const [offen, setOffen] = useState<FreigabeId | null>(null);
  const [stand, melden] = useReducer(freigabenWeiter, FREIGABEN_START);
  const lesen = useCallback(async () => {
    const [meetings, wetter, fahrzeiten] = await Promise.allSettled([api.transkripte(), api.wetter(), api.wegezeit()]);
    melden({art: "gelesen", an: {
      meetings: meetings.status === "fulfilled" ? Boolean(meetings.value.ordner.folder && meetings.value.ordner.enabled) : null,
      wetter: wetter.status === "fulfilled" ? wetter.value.aktiv : null,
      fahrzeiten: fahrzeiten.status === "fulfilled" ? fahrzeiten.value.aktiv : null,
    }});
  }, []);
  useEffect(() => { void lesen(); }, [lesen]);

  const zeilen: Zeile[] = [
    {id: "meetings", titel: "Meetings",
      inhalt: <TranscriptSettings beiAenderung={() => { melden({art: "geaendert", id: "meetings"}); void lesen(); }} />,
      satz: "Kingfisher liest Mitschriften deiner Meetings aus einem Ordner, den du auswählst, und ordnet sie dem Termin zu."},
    {id: "wetter", titel: "Wetter", hinweis: wetterHinweis(stand),
      inhalt: <Wetter beiAenderung={neu => melden({art: "geaendert", id: "wetter", an: neu.aktiv})}
        beiWunsch={an => melden({art: "wetter_wunsch", an})} />,
      satz: "Das Briefing nennt das Wetter an deinem Ort. Dafür geht nur der Ortsname an einen Wetterdienst."},
    // Die Marke neben der Überschrift folgt dem Schalter sofort, nicht erst nach dem Neuladen (Befund 19).
    {id: "fahrzeiten", titel: "Fahrzeiten",
      inhalt: <WegezeitSettings beiAenderung={neu => melden({art: "geaendert", id: "fahrzeiten", an: neu.aktiv})} />,
      satz: "Kingfisher sagt dir, wann du losfahren musst. Dafür gehen nur die Adresse des Termins und dein Startort an einen Kartendienst."},
  ];

  return <div className="erststart-inhalt">
    <p>Das alles ist ausgeschaltet, bis du es einschaltest. Du kannst es jederzeit unter <Verweis ziel="darf" /> ändern.</p>
    <ul className="erststart-freigaben">{zeilen.map(zeile => {
      const an = stand.an[zeile.id];
      return <li key={zeile.id}>
        <div className="erststart-freigabe-kopf">
          <div><strong>{zeile.titel}</strong><p>{zeile.satz}</p></div>
          <span className={`erststart-schalter${an ? " ist-an" : ""}`} role="status">{an === null ? "…" : an ? "An" : "Aus"}</span>
          <button type="button" className="secondary-action" aria-expanded={offen === zeile.id}
            onClick={() => { const zu = offen === zeile.id; setOffen(zu ? null : zeile.id); if (zu) void lesen(); }}>
            {offen === zeile.id ? "Zuklappen" : an ? "Ändern" : "Einrichten"}</button>
        </div>
        {zeile.hinweis ? <p className="source-hint erststart-freigabe-hinweis" role="status">{zeile.hinweis}</p> : null}
        {offen === zeile.id ? <div className="erststart-freigabe-inhalt">{zeile.inhalt}</div> : null}
      </li>;
    })}</ul>
    <SchrittFuss erledigt={freigabenErledigt(stand)} zurueck={zurueck} weiter={() => void weiter()} ueberspringen={() => void ueberspringen()} />
  </div>;
}
