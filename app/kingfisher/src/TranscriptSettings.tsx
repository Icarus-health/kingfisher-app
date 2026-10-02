import { useCallback, useEffect, useState } from "react";
import { api, type TranskriptEintrag, type TranskriptUebersicht } from "./api";
import { OrdnerImBrowser } from "./OrdnerImBrowser";
import { ordnerWeg, wartetSatz } from "./ordnerWahl";
import { ProfileSource } from "./ProfileSource";
import { fuerSystem, nurAufDemMac } from "./system";
import { useSystem } from "./useSystem";
import "./TranscriptSettings.css";

const wann = (wert: string) => {
  const datum = new Date(wert);
  return Number.isNaN(datum.getTime()) ? "" : new Intl.DateTimeFormat("de-DE", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(datum);
};

// Der Pfad, wie ihn ein Mensch liest: der Ordnername und der Ort davor, ohne das Benutzerverzeichnis.
function kurzerPfad(pfad: string) {
  const teile = pfad.replace(/\/+$/, "").split("/").filter(Boolean);
  const ohneHome = teile[0] === "Users" ? teile.slice(2) : teile;
  return ohneHome.length ? `~/${ohneHome.join("/")}` : pfad;
}

function Zeile({ eintrag, busy, onZuordnen, onLoesen }: { eintrag: TranskriptEintrag; busy: boolean; onZuordnen: (id: string, key: string) => void; onLoesen: (id: string) => void }) {
  return <article className="transkript-zeile">
    <div>
      <strong>{eintrag.titel}</strong>
      <small>Aufgenommen {wann(eintrag.aufgenommen)}{eintrag.sprecher.length ? ` · ${eintrag.sprecher.slice(0, 3).join(", ")}` : ""}</small>
      {eintrag.status === "zugeordnet" && eintrag.termin ? <p>Gehört zu „{eintrag.termin.titel}“, {wann(eintrag.termin.start)}.{eintrag.von === "nutzer" ? " Von dir gewählt." : " Vorschlag, noch nicht bestätigt."}</p> : null}
      {eintrag.status === "vorschlag" ? <p>Gehört das zu einem dieser Termine?</p> : null}
      {eintrag.status === "allein" ? <p>Kein passender Termin gefunden. Im Kalender unter „Nachbereiten“ lässt sie sich einem Termin zuordnen.</p> : null}
    </div>
    <div className="transkript-aktionen">
      {eintrag.status === "vorschlag" ? eintrag.kandidaten.map(kandidat =>
        <button className="secondary-action" type="button" key={kandidat.key} disabled={busy} title={kandidat.gruende.join(" ")} onClick={() => onZuordnen(eintrag.id, kandidat.key)}>{kandidat.titel}, {wann(kandidat.start)}</button>) : null}
      {eintrag.status === "zugeordnet" && eintrag.von === "auto" && eintrag.termin ? <button className="secondary-action" type="button" disabled={busy} title="Trägt die Sprecher als Beteiligte in die Mitschrift ein. „Zuordnung lösen“ nimmt das wieder zurück." onClick={() => onZuordnen(eintrag.id, eintrag.termin!.key)}>Stimmt so</button> : null}
      {eintrag.status === "zugeordnet" ? <button className="text-action" type="button" disabled={busy} onClick={() => onLoesen(eintrag.id)}>Zuordnung lösen</button> : null}
      <ProfileSource kind="episode" id={eintrag.id} label="Ansehen" quiet />
    </div>
  </article>;
}

// Einstellungen → Zugänge → Ordner und Dateien: der Eingangsordner für Meeting-Mitschriften. Mit Helfer am Mac wird im Dialog
// des Mac gewählt (der Vorgabeordner braucht keinen); ohne Helfer im Browser, aus bekannten Orten oder mit geprüftem Pfad
// (Befund 6). „Trennen“ nimmt die Mitschriften wieder aus dem Gedächtnis, die Dateien bleiben liegen. `beiAenderung` meldet
// jede Änderung des Menschen (der Assistent zeigt dann „Weiter“, Fremdprobe 3, Befund 4).
export function TranscriptSettings({ beiAenderung }: { beiAenderung?: () => void } = {}) {
  const system = useSystem();
  const [daten, setDaten] = useState<TranskriptUebersicht | null>(null);
  const [fehler, setFehler] = useState("");
  const [busy, setBusy] = useState(false);
  const [trennen, setTrennen] = useState(false);
  const [hinweis, setHinweis] = useState("");
  const [andererOrdner, setAndererOrdner] = useState(false);

  const laden = useCallback(async () => {
    try { setDaten(await api.transkripte()); setFehler(""); }
    catch { setFehler("Der Mitschriften-Eingang konnte nicht geladen werden."); }
  }, []);
  useEffect(() => { void laden(); }, [laden]);
  useEffect(() => {
    if (busy) return;
    const timer = window.setInterval(() => void laden(), 4000);
    return () => window.clearInterval(timer);
  }, [busy, laden]);

  async function tun(aktion: () => Promise<unknown>, erfolg = "") {
    if (busy) return;
    setBusy(true); setFehler(""); setHinweis("");
    try { await aktion(); if (erfolg) setHinweis(erfolg); await laden(); beiAenderung?.(); }
    catch { setFehler("Das hat nicht geklappt. Bitte erneut versuchen."); }
    finally { setBusy(false); }
  }

  const ordner = daten?.ordner;
  const wartet = Boolean(ordner?.pick_request);
  const weg = ordner ? ordnerWeg(ordner) : "browser";
  const gewaehlt = (satz: string) => { setHinweis(satz); setAndererOrdner(false); void laden(); beiAenderung?.(); };
  const offene = (daten?.eintraege ?? []).filter(eintrag => eintrag.status !== "zugeordnet")
    .sort((a, b) => Number(b.status === "vorschlag") - Number(a.status === "vorschlag")).slice(0, 8);
  const zugeordnete = (daten?.eintraege ?? []).filter(eintrag => eintrag.status === "zugeordnet");
  const fehlerLauf = ordner?.last_run?.errors ?? [];

  return <section className="source-section document-import transkript-eingang" aria-label="Meetings: Mitschriften">
    <div className="compact-integration-heading"><div><h2>Meetings</h2><p>Exportiere Mitschriften aus MacWhisper, Teams oder Meet in einen Ordner. Kingfisher liest sie und ordnet sie dem passenden Termin zu.</p></div></div>
    {!daten && !fehler ? <p role="status">Wird geladen …</p> : null}
    {daten && ordner ? <>
      {wartet ? <div className="transkript-status" role="status">
        <p>{fuerSystem(wartetSatz(ordner.pick_request!.modus, daten.vorgabe), system)}</p>
        {!ordner.helfer ? <p>{nurAufDemMac(system, "Die Ordnerwahl im Fenster")}</p> : null}
        <button className="secondary-action" type="button" disabled={busy} onClick={() => void tun(() => api.transkriptAuswahlAbbrechen())}>Abbrechen</button>
      </div> : null}

      {!ordner.folder && !wartet && weg === "helfer" ? <div className="transkript-status">
        <p>Noch kein Ordner. Kingfisher liest nur den Ordner, den du hier auswählst.</p>
        <button className="primary-action" type="button" disabled={busy} onClick={() => void tun(() => api.transkriptOrdnerWaehlen("vorgabe"))}>Ordner „{daten.vorgabe}“ verwenden</button>
        <button className="secondary-action" type="button" disabled={busy} onClick={() => void tun(() => api.transkriptOrdnerWaehlen("waehlen"))}>Anderen Ordner wählen …</button>
        <small>Der Vorgabeordner wird ohne Rückfrage angelegt, falls es ihn nicht gibt. Für einen anderen zeigt die App einen normalen Auswahldialog.</small>
      </div> : null}
      {!ordner.folder && !wartet && weg === "browser" ? <div className="transkript-status"><OrdnerImBrowser prefix="/api/v1/transcript-sync" beiGewaehlt={gewaehlt} /></div> : null}

      {ordner.folder ? <div className="transkript-status">
        <p><strong>Ordner</strong> <span className="transkript-pfad" title={ordner.folder}>{kurzerPfad(ordner.folder)}</span></p>
        <p role="status">{!ordner.enabled ? "Pausiert." : ordner.running ? "Aktiv. Neue Dateien werden etwa einmal pro Minute aufgenommen."
          : ordner.lokal ? "Kingfisher hat den Ordner seit ein paar Minuten nicht gelesen." : nurAufDemMac(system, "Das Lesen des Ordners")}</p>
        <p>{daten.stand.aufgenommen} {daten.stand.aufgenommen === 1 ? "Mitschrift" : "Mitschriften"} aufgenommen · {daten.stand.zugeordnet} einem Termin zugeordnet · {daten.stand.offen} ohne Termin</p>
        <div className="transkript-aktionen">
          <button className="secondary-action" type="button" disabled={busy} onClick={() => void tun(() => api.transkriptAktiv(!ordner.enabled))}>{ordner.enabled ? "Pausieren" : "Fortsetzen"}</button>
          <button className="secondary-action" type="button" disabled={busy || wartet} onClick={() => weg === "helfer" ? void tun(() => api.transkriptOrdnerWaehlen("waehlen")) : setAndererOrdner(wert => !wert)}>Anderen Ordner wählen …</button>
          <button className="text-action" type="button" disabled={busy} onClick={() => setTrennen(true)}>Ordner trennen</button>
        </div>
        {andererOrdner && weg === "browser" ? <OrdnerImBrowser prefix="/api/v1/transcript-sync" beiGewaehlt={gewaehlt} /> : null}
        {trennen ? <div className="transkript-bestaetigung" role="alertdialog" aria-label="Ordner trennen">
          <p>Beim Trennen nimmt Kingfisher alle Mitschriften aus diesem Ordner aus dem Gedächtnis. Deine Dateien bleiben unverändert.</p>
          <button className="secondary-action decision-confirm" type="button" disabled={busy} onClick={() => void tun(async () => { const antwort = await api.transkriptOrdnerTrennen(); setTrennen(false); setHinweis(`Getrennt. ${antwort.entzogen} ${antwort.entzogen === 1 ? "Mitschrift wurde" : "Mitschriften wurden"} entzogen.`); })}>Ordner trennen</button>
          <button className="text-action" type="button" disabled={busy} onClick={() => setTrennen(false)}>Abbrechen</button>
        </div> : null}
      </div> : null}
      {ordner.getrennt && !ordner.folder && !wartet && !hinweis ? <p className="transkript-hinweis">Der Ordner ist getrennt. Die Mitschriften sind nicht mehr im Gedächtnis.</p> : null}
      {fehlerLauf.length ? <p role="alert">{fehlerLauf.join(" ")}</p> : null}

      {offene.length ? <section aria-label="Mitschriften ohne Termin"><h3>Noch ohne Termin</h3>
        {offene.map(eintrag => <Zeile key={eintrag.id} eintrag={eintrag} busy={busy} onZuordnen={(id, key) => void tun(() => api.transkriptZuordnen(id, key), "Zugeordnet.")} onLoesen={id => void tun(() => api.transkriptLoesen(id), "Zuordnung gelöst.")} />)}
      </section> : null}
      {zugeordnete.length ? <details className="transkript-liste"><summary>Einem Termin zugeordnet ({daten.stand.zugeordnet})</summary>
        {zugeordnete.map(eintrag => <Zeile key={eintrag.id} eintrag={eintrag} busy={busy} onZuordnen={(id, key) => void tun(() => api.transkriptZuordnen(id, key), "Bestätigt.")} onLoesen={id => void tun(() => api.transkriptLoesen(id), "Zuordnung gelöst.")} />)}
        {daten.mehr ? <small>Gezeigt werden die neuesten Mitschriften.</small> : null}
      </details> : null}
    </> : null}
    {hinweis ? <p role="status">{hinweis}</p> : null}
    {fehler ? <p role="alert">{fehler} <button className="text-action" type="button" onClick={() => void laden()}>Erneut versuchen</button></p> : null}
  </section>;
}
