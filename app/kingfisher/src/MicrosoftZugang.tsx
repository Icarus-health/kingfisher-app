import { useCallback, useEffect, useState } from "react";
import { api, type MicrosoftKonten } from "./api";
import { MicrosoftAnmeldung } from "./MicrosoftAnmeldungKarte";
import { SAETZE } from "./microsoftAnmeldung";

const datum = (wert: string | null) => {
  if (!wert) return "";
  const zeit = new Date(wert);
  return Number.isNaN(zeit.getTime()) ? "" : zeit.toLocaleString("de-DE", { day: "numeric", month: "numeric", hour: "2-digit", minute: "2-digit" });
};

/**
 * Einstellungen → Zugänge: Microsoft 365 (Hochschule oder Firma). Ein Konto bringt Post und Kalender; die
 * Teams-Mitschriften sind ein zweiter Klick, weil Microsoft dafür die Zustimmung der IT verlangt. Darunter steht je
 * Besprechung ein Satz, was aus ihrer Mitschrift geworden ist.
 */
export function MicrosoftZugang({ aktiv, beiAenderung }: { aktiv: boolean; beiAenderung: () => void }) {
  const [konten, setKonten] = useState<MicrosoftKonten | null>(null);
  const [neu, setNeu] = useState(false);
  const [mitschriftenFuer, setMitschriftenFuer] = useState("");
  const [holt, setHolt] = useState(false);
  const [satz, setSatz] = useState("");
  const laden = useCallback(() => {
    api.microsoftKonten().then(setKonten).catch(() => setSatz("Die Microsoft-Konten sind gerade nicht erreichbar."));
  }, []);
  useEffect(() => { if (aktiv) laden(); }, [aktiv, laden]);
  const verbunden = () => { setNeu(false); setMitschriftenFuer(""); laden(); beiAenderung(); };

  async function nachsehen() {
    setHolt(true); setSatz("");
    try {
      const antwort = await api.microsoftMitschriftenAbholen();
      setKonten(antwort);
      setSatz("Kingfisher hat bei Microsoft nach neuen Mitschriften gesehen.");
    } catch { setSatz("Kingfisher konnte gerade nicht bei Microsoft nachsehen. Es versucht es von allein wieder."); }
    finally { setHolt(false); }
  }

  const liste = konten?.konten ?? [];
  return <section className="source-section ms-zugang" aria-label="Microsoft 365">
    <h2>Microsoft 365</h2>
    <p className="source-hint">Für Hochschulen und Firmen mit Outlook und Teams: eine Anmeldung bei Microsoft bringt Post, Kalender und auf Wunsch die Mitschriften deiner Teams-Besprechungen.</p>
    {liste.map(konto => <div key={konto.adresse} className="ms-konto">
      <strong>{konto.adresse}</strong>
      <span className="source-hint">{konto.verbunden ? [konto.post ? "Post" : "", konto.kalender ? "Kalender" : "", konto.mitschriften ? "Teams-Mitschriften" : ""].filter(Boolean).join(", ") + " · nur lesen" : konto.satz}</span>
      {!konto.verbunden ? <MicrosoftAnmeldung adresse={konto.adresse} knopf="Neu anmelden" beiVerbunden={verbunden} /> : null}
      {konto.verbunden && !konto.mitschriften ? (mitschriftenFuer === konto.adresse
        ? <MicrosoftAnmeldung adresse={konto.adresse} mitschriften knopf="Bei Microsoft zustimmen" beiVerbunden={verbunden} />
        : <button type="button" className="secondary-action" onClick={() => setMitschriftenFuer(konto.adresse)}>Teams-Mitschriften dazunehmen</button>) : null}
      {konto.mitschriften ? <>
        {konto.besprechungen.length ? <ul>{konto.besprechungen.map(b => <li key={`${b.titel}-${b.beginn}`}><strong>{b.titel}</strong> {datum(b.beginn)}: {b.satz}</li>)}</ul>
          : <p className="source-hint">Noch keine Teams-Besprechung mit Mitschrift in den letzten zwei Wochen. Kingfisher sieht alle zehn Minuten nach.</p>}
        <button type="button" className="text-action" disabled={holt} onClick={() => void nachsehen()}>{holt ? "Sieht nach …" : "Jetzt nachsehen"}</button>
      </> : null}
    </div>)}
    {neu ? <MicrosoftAnmeldung beiVerbunden={verbunden} /> : <button type="button" className="secondary-action" onClick={() => setNeu(true)}>{liste.length ? "Weiteres Microsoft-Konto anmelden" : "Mit Microsoft anmelden"}</button>}
    <p className="source-hint">{SAETZE.bleibt}</p>
    {satz ? <p role="status">{satz}</p> : null}
  </section>;
}
