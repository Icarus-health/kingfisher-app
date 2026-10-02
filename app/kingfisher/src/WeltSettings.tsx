import { useEffect, useState } from "react";
import { ApiError, api, type WeltStand, type WetterOrt, type WetterStand } from "./api";
import { SCHALTER } from "./Einstellungen/gliederung";
import { eigeneQuellen, normiereAdresse, vorgabeZustand, vorgabenStandSatz } from "./weltVorgaben";
import "./WeltSettings.css";

// Wetter und Nachrichten im Briefing: zwei der fünf Schalter unter „Was Kingfisher darf“. Beides ist aus, bis man es
// einschaltet. Beim Wetter verlässt nur der Ortsname den Rechner; bei den Nachrichten wird nur abgerufen, was man selbst
// ausgewählt hat. Der Ort kommt aus einer Trefferliste, die Quellen aus einer Vorgabeliste zum Anklicken; getippt wird
// nichts, was sich zeigen ließe (sidecar: wetter_routes.py, welt_briefing_routes.py, welt_vorgaben.py).

// `beiAenderung` meldet jeden gespeicherten Stand, `beiWunsch` jedes Umlegen des Schalters (auch ohne Ort, wenn er nur
// die Ortssuche öffnet). Der Assistent zeigt damit „Weiter“ und sagt, warum das Wetter noch aus ist (Fremdprobe 3, Befund 4).
export function Wetter({ beiAenderung, beiWunsch }: { beiAenderung?: (stand: WetterStand) => void; beiWunsch?: (an: boolean) => void } = {}) {
  const [stand, setStand] = useState<WetterStand | null>(null);
  const [suche, setSuche] = useState("");
  const [treffer, setTreffer] = useState<WetterOrt[] | null>(null);
  const [sucheOffen, setSucheOffen] = useState(false);
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.wetter().then(daten => { if (aktiv) setStand(daten); }).catch(() => { if (aktiv) setFehler("Die Einstellung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);

  async function finden(text: string) {
    if (text.trim().length < 2) return;
    setArbeitet(true); setFehler(""); setGespeichert("");
    try {
      const antwort = await api.wetterOrte(text.trim());
      if (antwort.satz) { setTreffer(null); setFehler(antwort.satz); } else setTreffer(antwort.orte);
    }
    catch (e) { setTreffer(null); setFehler(e instanceof ApiError && e.detail ? e.detail : "Die Suche hat nicht geklappt. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }
  async function speichern(aenderung: Parameters<typeof api.wetterSetzen>[0], text: string) {
    setArbeitet(true); setFehler(""); setGespeichert("");
    try { const neu = await api.wetterSetzen(aenderung); setStand(neu); setGespeichert(text); setTreffer(null); setSucheOffen(false); beiAenderung?.(neu); }
    catch (e) { setFehler(e instanceof ApiError && e.detail ? e.detail : "Das konnte nicht gespeichert werden. Bitte erneut versuchen."); }
    finally { setArbeitet(false); }
  }
  // Ohne Ort gibt es nichts einzuschalten: Der Schalter öffnet dann die Ortssuche, und erst der Klick auf einen Treffer
  // schaltet das Wetter ein.
  function umschalten(an: boolean) {
    if (!stand) return;
    beiWunsch?.(an);
    if (an && !stand.name) { setSucheOffen(true); setGespeichert(""); return; }
    if (!an && !stand.name) { setSucheOffen(false); setTreffer(null); return; }
    void speichern({ aktiv: an }, an ? "Das Wetter steht im Briefing." : "Das Wetter steht nicht mehr im Briefing.");
  }

  return <section className="darf-zeile" aria-label={SCHALTER.wetter.titel}>
    {!stand ? <p>Wird geladen …</p> : <>
      <label className="welt-schalter"><input type="checkbox" role="switch" checked={(stand.aktiv && Boolean(stand.name)) || (!stand.name && sucheOffen)} disabled={arbeitet}
        onChange={event => umschalten(event.target.checked)} />
        <span><strong>{SCHALTER.wetter.titel}</strong><small>{SCHALTER.wetter.verlaesst}</small></span></label>
      {stand.name && stand.aktiv && !sucheOffen && <p className="source-hint">Ort: {stand.name}. <button type="button" className="text-action" onClick={() => { setSucheOffen(true); setSuche(""); }}>Ort ändern</button></p>}
      {sucheOffen && <form className="welt-suche" onSubmit={event => { event.preventDefault(); void finden(suche); }}>
        <label htmlFor="wetter-suche">{stand.name ? "Anderer Ort" : "Für welchen Ort soll das Wetter gelten?"}</label>
        {!stand.name && <p className="source-hint">An ist das Wetter erst, wenn du einen Ort gewählt hast.</p>}
        {stand.vorschlag && !treffer && <button type="button" className="secondary-action" disabled={arbeitet}
          onClick={() => { setSuche(stand.vorschlag); void finden(stand.vorschlag); }}>{stand.vorschlag} (dein Startort)</button>}
        <div><input id="wetter-suche" value={suche} maxLength={80} placeholder="Ort, zum Beispiel Mainz" autoComplete="off" onChange={event => setSuche(event.target.value)} disabled={arbeitet} />
          <button type="submit" className="secondary-action" disabled={arbeitet || suche.trim().length < 2}>Suchen</button></div>
      </form>}
      {treffer && (treffer.length === 0
        ? <p className="source-hint" role="status">Zu diesem Namen habe ich keinen Ort gefunden.</p>
        : <ul className="welt-treffer" aria-label="Gefundene Orte">{treffer.map(ort => <li key={`${ort.breite}:${ort.laenge}`}>
          <button type="button" className="secondary-action" disabled={arbeitet}
            onClick={() => void speichern({ aktiv: true, ort }, `Das Wetter für ${ort.name} steht jetzt im Briefing.`)}>{ort.ort}</button></li>)}</ul>)}
      {stand.aus_umgebung && <p className="source-hint">Dieser Ort ist aus der Konfiguration dieses Rechners übernommen.</p>}
    </>}
    {gespeichert && <p role="status" className="source-hint">{gespeichert}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}

export function Nachrichten() {
  const [stand, setStand] = useState<WeltStand | null>(null);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [fehler, setFehler] = useState("");
  const [gespeichert, setGespeichert] = useState("");
  useEffect(() => {
    let aktiv = true;
    api.welt().then(daten => { if (aktiv) setStand(daten); }).catch(() => { if (aktiv) setFehler("Die Einstellung konnte nicht geladen werden."); });
    return () => { aktiv = false; };
  }, []);

  async function ausfuehren(aktion: () => Promise<WeltStand>, text: string) {
    setArbeitet(true); setFehler(""); setGespeichert("");
    try { setStand(await aktion()); setGespeichert(text); return true; }
    catch (e) { setFehler(e instanceof ApiError && e.detail ? e.detail : "Das konnte nicht gespeichert werden. Bitte erneut versuchen."); return false; }
    finally { setArbeitet(false); }
  }
  const quellenVorhanden = stand !== null && (stand.feeds.some(f => f.enabled) || stand.weltquellen.some(q => q.gewaehlt));
  const eigene = stand ? eigeneQuellen(stand.feeds, stand.vorschlaege) : [];
  const adresse = normiereAdresse(url);

  return <section className="darf-zeile" aria-label={SCHALTER.welt.titel}>
    {!stand ? <p>Wird geladen …</p> : <>
      <label className="welt-schalter"><input type="checkbox" role="switch" checked={stand.aktiv} disabled={arbeitet}
        onChange={event => void ausfuehren(() => api.weltSetzen({ aktiv: event.target.checked }), event.target.checked ? "Eine passende Meldung pro Tag steht künftig im Briefing." : "Es stehen keine Meldungen mehr im Briefing.")} />
        <span><strong>{SCHALTER.welt.titel}</strong><small>{SCHALTER.welt.verlaesst}</small></span></label>
      {stand.aktiv && <>
        <p className="source-hint">Höchstens eine Meldung am Tag, und nur, wenn sie zu etwas aus deinen Akten passt. Zu jeder steht, warum sie da ist.</p>
        {!quellenVorhanden && <p className="source-hint" role="status">Wähle mindestens eine Quelle, sonst gibt es nichts zu lesen.</p>}
        <div className="welt-vorschlaege" role="group" aria-label="Quellen zum Anklicken">
          {stand.vorschlaege.map(v => {
            const zustand = vorgabeZustand(v, stand.feeds);
            const feed = stand.feeds.find(f => f.id === v.feed_id);
            return <div key={v.id} className="welt-vorgabe">
              <button type="button" className="welt-vorgabe-knopf" aria-pressed={zustand === "an"} disabled={arbeitet}
                onClick={() => void ausfuehren(() => zustand === "an" ? api.weltFeedWeg(v.feed_id as string)
                  : zustand === "abbestellt" ? api.weltFeedSchalter(v.feed_id as string, true) : api.weltFeedNeu(v.url, v.label),
                zustand === "an" ? `${v.label} ist entfernt.` : `${v.label} ist dabei.`)}>
                <strong>{v.label}</strong><small>{zustand === "abbestellt" ? "abbestellt, Klick schaltet wieder ein" : v.beschreibung}</small></button>
              {feed?.fehler ? <span className="settings-error" role="status">{feed.fehler}</span> : null}
            </div>;
          })}
        </div>
        <p className="source-hint">{vorgabenStandSatz(stand.vorschlaege_stand)}</p>
        {eigene.length > 0 && <ul className="welt-liste" aria-label="Deine eigenen Quellen">{eigene.map(feed => <li key={feed.id}>
          <label><input type="checkbox" checked={feed.enabled} disabled={arbeitet}
            onChange={event => void ausfuehren(() => api.weltFeedSchalter(feed.id, event.target.checked), event.target.checked ? `${feed.label} ist wieder eingeschaltet.` : `${feed.label} ist abbestellt.`)} />
            <span>{feed.label}</span></label>
          <button type="button" className="secondary-action" disabled={arbeitet}
            onClick={() => void ausfuehren(() => api.weltFeedWeg(feed.id), `${feed.label} wurde entfernt.`)}>Entfernen</button>
          {feed.fehler && <span className="settings-error" role="status">{feed.fehler}</span>}
        </li>)}</ul>}
        {stand.weltquellen.length > 0 && <fieldset className="welt-liste"><legend>Quellen, die du schon eingerichtet hast</legend>
          {stand.weltquellen.map(q => <label key={q.id}><input type="checkbox" checked={q.gewaehlt} disabled={arbeitet}
            onChange={event => void ausfuehren(() => api.weltSetzen({ weltquellen: stand.weltquellen.filter(x => x.id === q.id ? event.target.checked : x.gewaehlt).map(x => x.id) }),
              event.target.checked ? `${q.label} wird mitgelesen.` : `${q.label} wird nicht mehr mitgelesen.`)} /><span>{q.label}</span></label>)}
        </fieldset>}
        <form className="welt-eigene" aria-label="Eigene Quelle" onSubmit={event => { event.preventDefault(); void ausfuehren(() => api.weltFeedNeu(adresse, name.trim()), "Die Quelle ist dabei.").then(ok => { if (ok) { setUrl(""); setName(""); } }); }}>
          <label htmlFor="welt-feed-url">Eigene Quelle: Adresse</label>
          <input id="welt-feed-url" value={url} maxLength={2000} placeholder="https://…" autoComplete="off" inputMode="url" onChange={event => setUrl(event.target.value)} disabled={arbeitet} />
          <label htmlFor="welt-feed-name">Name (freiwillig)</label>
          <input id="welt-feed-name" value={name} maxLength={80} autoComplete="off" onChange={event => setName(event.target.value)} disabled={arbeitet} />
          <button type="submit" className="secondary-action" disabled={arbeitet || adresse === ""}>Quelle hinzufügen</button>
          <p className="source-hint">Die Adresse findest du meist auf der Seite der Zeitung unter „Abonnieren“. Kingfisher liest sie einmal zur Probe; öffentliche Adressen genügen, Anmeldedaten sind nicht nötig.</p>
        </form>
      </>}
      {stand.abbestellt.length > 0 && <div className="welt-abbestellt"><h3>Abbestellt</h3>
        <ul className="welt-liste">{stand.abbestellt.map(a => <li key={a.sache}><span>Keine Meldungen mehr zu {a.name}</span>
          <button type="button" className="secondary-action" disabled={arbeitet}
            onClick={() => void ausfuehren(() => api.weltZulassen(a.sache), `Meldungen zu ${a.name} sind wieder möglich.`)}>Wieder zulassen</button></li>)}</ul></div>}
      {stand.aktiv && stand.modell && <p className="source-hint">Ein Modell auf diesem Rechner prüft die Treffer zusätzlich; es kann eine Meldung nur streichen.</p>}
    </>}
    {gespeichert && <p role="status" className="source-hint">{gespeichert}</p>}
    {fehler && <p role="alert" className="settings-error">{fehler}</p>}
  </section>;
}
