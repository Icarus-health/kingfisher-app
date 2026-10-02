import { ProfileSource } from "./ProfileSource";
import { gueltigeQuellen, quellenWeg, technikZeile } from "./quellenWeg";
import { navigate } from "./ui";
import { GESTUETZT_AUF } from "./beleg";
import "./BelegQuellen.css";

/**
 * Die Quellen einer belegten Gedächtnisantwort, je ein Klick: eine Nachricht in diesem Gespräch wird angesprungen,
 * eine aus einem anderen Gespräch geöffnet, eine Mail, ein Termin oder ein Dokument in der Quellenansicht gezeigt.
 * Unter der Antwort steht sichtbar „Gestützt auf“ mit dem Hinweis je Quelle in Alltagssprache (Fremdprobe 2, Befund 13);
 * Kennungen nur hinter „Für Techniker“.
 */
export function BelegQuellen({ quellen, gespraech, zeigeNachricht, onChange }: {
  quellen: unknown;
  gespraech: string;
  zeigeNachricht: (nachricht: string) => void;
  onChange?: () => void;
}) {
  const liste = gueltigeQuellen(quellen);
  if (!liste.length) return null;
  return <div className="beleg-quellen" role="group" aria-label="Worauf die Antwort sich stützt">
    <p className="beleg-kopf">{GESTUETZT_AUF}</p>
    {liste.map((quelle) => {
      const weg = quellenWeg(quelle, gespraech);
      const name = `Quelle ${quelle.nummer} öffnen`;
      return <div className="beleg-quelle" key={quelle.nummer} data-quelle={quelle.nummer} data-quelle-ref={quelle.source_ref ?? ""} data-claim={quelle.assertion_id}>
        <span className="beleg-text">[{quelle.nummer}] {quelle.text}</span>
        {weg.art === "quelle"
          ? <ProfileSource kind="episode" id={weg.episode} label={name} quiet onChange={onChange} />
          : <button className="quiet-source-toggle" type="button" title={quelle.text}
            onClick={() => weg.art === "nachricht" ? zeigeNachricht(weg.nachricht) : navigate(weg.pfad)}>{name}</button>}
      </div>;
    })}
    <details className="quelle-technik">
      <summary>Für Techniker</summary>
      {liste.map((quelle) => <p key={quelle.nummer}>{technikZeile(quelle)}</p>)}
    </details>
  </div>;
}
