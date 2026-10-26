import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { InterfaceIcon } from "../InterfaceIcon";
import { icon } from "../ui";
import { bereichName, vorschlagSatz, type Konten, type Konto } from "../kontenBereiche";

/**
 * Eine Zeile unter Zugänge für ein Postfach oder einen Kalender (Paket K): Name (ein Klick benennt um), Adresse, der
 * Stand in einem Satz, der Bereich. Ein Vorschlag steht sichtbar als Vorschlag mit Grund da und wird mit einem Klick
 * übernommen; ohne Vorschlag fragt die Zeile einmal „Welcher Bereich?“. Alles ist umkehrbar; die Seite zeigt danach den
 * Hinweis mit „Rückgängig“.
 */
export function KontoZeile({ konto, konten, iconName, neben, ersatzStand, busy, entfernen, onUmbenennen, onBereich, onNeuerBereich, children }: {
  konto: Konto;
  /** Null, solange Bereiche und Stand noch laden: Dann steht die Zeile ohne sie da. */
  konten: Konten | null;
  iconName: "mail" | "calendar-days";
  neben: string;
  /** Was rechts steht, solange der Sidecar keinen Stand kennt (etwa „Unvollständig eingerichtet“). */
  ersatzStand?: string;
  busy: boolean;
  entfernen?: { aktiv: boolean; onRemove: () => void; onCancel: () => void };
  /** Gibt bei Ablehnung den Satz des Sidecars zurück, sonst null. */
  onUmbenennen: (name: string) => Promise<string | null>;
  onBereich: (bereich: string | null) => void;
  onNeuerBereich: (name: string) => Promise<string | null>;
  children?: ReactNode;
}) {
  const [bearbeiten, setBearbeiten] = useState(false);
  const [entwurf, setEntwurf] = useState(konto.name);
  const [fehler, setFehler] = useState("");
  const [waehlen, setWaehlen] = useState(false);
  const eingabe = useRef<HTMLInputElement>(null);
  const nameKnopf = useRef<HTMLButtonElement>(null);
  const fertig = useRef(false);
  useEffect(() => { if (bearbeiten) { eingabe.current?.focus(); eingabe.current?.select(); } }, [bearbeiten]);
  useEffect(() => { if (!bearbeiten) setEntwurf(konto.name); }, [konto.name, bearbeiten]);

  async function speichern() {
    if (fertig.current) return;
    fertig.current = true;
    const satz = await onUmbenennen(entwurf);
    if (satz) { setFehler(satz); fertig.current = false; eingabe.current?.focus(); return; }
    setFehler(""); setBearbeiten(false); fertig.current = false;
    requestAnimationFrame(() => nameKnopf.current?.focus());
  }
  function taste(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") { event.preventDefault(); void speichern(); }
    if (event.key === "Escape") { event.preventDefault(); fertig.current = true; setBearbeiten(false); setFehler(""); setEntwurf(konto.name); requestAnimationFrame(() => { fertig.current = false; nameKnopf.current?.focus(); }); }
  }

  const titel = bearbeiten
    ? <input ref={eingabe} className="konto-name-eingabe" aria-label={`Neuer Name für ${konto.name}`} value={entwurf} maxLength={120}
        disabled={busy} onChange={event => setEntwurf(event.target.value)} onKeyDown={taste} onBlur={() => void speichern()} />
    : konto.umbenennbar === false ? <strong className="g-zeile-titel">{konto.name}</strong>
      : <button ref={nameKnopf} type="button" className="g-zeile-titel konto-name" title="Umbenennen" aria-label={`${konto.name} umbenennen`}
          onClick={() => { setFehler(""); setEntwurf(konto.name); setBearbeiten(true); }}>{konto.name}</button>;
  const stand = konto.stand;
  const ohneBereich = !konto.bereich;
  const offeneWahl = Boolean(konten) && (waehlen || (ohneBereich && !konto.vorschlag));
  return <div className="konto">
    <div className="source-row g-zeile konto-zeile">
      <span className="g-zeile-symbol" aria-hidden="true"><InterfaceIcon name={iconName} /></span>
      <span className="g-zeile-text">
        {titel}
        {neben ? <small className="g-zeile-neben">{neben}</small> : null}
        {stand ? <small className={`konto-stand konto-stand-${stand.art}`}>{stand.satz}</small>
          : ersatzStand ? <small className="konto-stand">{ersatzStand}</small> : null}
      </span>
      {konten && konto.bereich && !entfernen?.aktiv ? <button type="button" className="konto-bereich" aria-expanded={waehlen}
          aria-label={`Bereich: ${bereichName(konten, konto.bereich)}. Ändern`} onClick={() => setWaehlen(offen => !offen)}>
          {bereichName(konten, konto.bereich) || konto.bereich}</button> : null}
      {entfernen ? (entfernen.aktiv
        ? <span className="source-remove-confirm" role="group" aria-label={`${konto.name} entfernen`}>Quelle wirklich entfernen?<button disabled={busy} onClick={entfernen.onRemove} type="button">Entfernen</button><button disabled={busy} onClick={entfernen.onCancel} type="button">Abbrechen</button></span>
        : <button aria-label={`${konto.name} entfernen`} className="source-remove" disabled={busy} onClick={entfernen.onRemove} type="button"><img src={icon("trash2", "Outline")} alt="" /></button>) : null}
    </div>
    {fehler ? <p className="settings-error konto-fehler" role="alert">{fehler}</p> : null}
    {konten && ohneBereich && konto.vorschlag && !waehlen ? <div className="konto-frage">
      <span className="konto-frage-satz">{vorschlagSatz(konten, konto)}</span>
      <span className="konto-frage-knoepfe">
        <button type="button" className="g-knopf-getoent g-kompakt" disabled={busy} onClick={() => onBereich(konto.vorschlag!.bereich)}>Übernehmen</button>
        <button type="button" className="g-knopf-schlicht g-kompakt" disabled={busy} onClick={() => setWaehlen(true)}>Anderer Bereich</button>
      </span>
    </div> : null}
    {konten && offeneWahl ? <BereichWahl konten={konten} aktuell={konto.bereich} name={konto.name} busy={busy}
      frage={ohneBereich ? "Welcher Bereich?" : "Bereich"}
      onWahl={bereich => { setWaehlen(false); if (bereich !== konto.bereich) onBereich(bereich); }}
      onNeu={async name => { const satz = await onNeuerBereich(name); if (!satz) setWaehlen(false); return satz; }} /> : null}
    {children}
  </div>;
}

/** Die Wahl des Bereichs: je Bereich ein Knopf, dazu „Eigener Bereich“ mit einem Namensfeld; bei einem gesetzten „Ohne“. */
function BereichWahl({ konten, aktuell, name, frage, busy, onWahl, onNeu }: {
  konten: Konten; aktuell: string | null; name: string; frage: string; busy: boolean;
  onWahl: (bereich: string | null) => void; onNeu: (name: string) => Promise<string | null>;
}) {
  const [neu, setNeu] = useState(false);
  const [eingabe, setEingabe] = useState("");
  const [fehler, setFehler] = useState("");
  return <div className="konto-wahl" role="group" aria-label={`Bereich von ${name}`}>
    <span className="konto-frage-satz">{frage}</span>
    <span className="konto-frage-knoepfe">
      {konten.bereiche.map(b => <button key={b.id} type="button" className="g-knopf-getoent g-kompakt konto-wahl-knopf" aria-pressed={b.id === aktuell}
        disabled={busy} onClick={() => onWahl(b.id)}>{b.name}</button>)}
      {aktuell ? <button type="button" className="g-knopf-schlicht g-kompakt" disabled={busy} onClick={() => onWahl(null)}>Ohne</button> : null}
      {!neu ? <button type="button" className="g-knopf-schlicht g-kompakt" disabled={busy} onClick={() => setNeu(true)}>Eigener Bereich …</button> : null}
    </span>
    {neu ? <form className="konto-neu" onSubmit={async event => { event.preventDefault(); const satz = await onNeu(eingabe); setFehler(satz ?? ""); if (!satz) { setNeu(false); setEingabe(""); } }}>
      <input autoFocus aria-label="Name des neuen Bereichs" placeholder="Etwa „Verein“" maxLength={40} value={eingabe} onChange={event => setEingabe(event.target.value)} />
      <button type="submit" className="g-knopf-getoent g-kompakt" disabled={busy || !eingabe.trim()}>Anlegen</button>
      {fehler ? <p className="settings-error" role="alert">{fehler}</p> : null}
    </form> : null}
  </div>;
}
