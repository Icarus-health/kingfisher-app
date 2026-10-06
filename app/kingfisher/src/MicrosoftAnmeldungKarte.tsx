import { useEffect, useRef, useState } from "react";
import { api, ApiError, type MicrosoftAnmeldung as Stand, type MicrosoftStand } from "./api";
import { MS_LINK, SAETZE, istFertig, nachfragen, standSatz } from "./microsoftAnmeldung";
import "./MicrosoftAnmeldung.css";

/**
 * „Mit Microsoft anmelden“ (docs/50-microsoft-365.md): Kingfisher zeigt einen kurzen Code und den Link zu Microsoft,
 * der Mensch meldet sich dort im Browser an, die Karte fragt nach und sagt, was daraus geworden ist. Kein Passwort,
 * kein Servername, nichts zu tippen außer dem Code auf der Seite von Microsoft (mit Kopierknopf).
 */
export function MicrosoftAnmeldung({ adresse = "", mitschriften = false, knopf, beiVerbunden, ohneApp }: {
  adresse?: string; mitschriften?: boolean; knopf?: string;
  beiVerbunden: (stand: Stand) => void;
  /** Wird gerufen, wenn die Kennung der App fehlt: Der Mail-Schritt zeigt dann den Weg mit Passwort. */
  ohneApp?: () => void;
}) {
  const [stand, setStand] = useState<MicrosoftStand | null>(null);
  const [anmeldung, setAnmeldung] = useState<Stand | null>(null);
  const [fehler, setFehler] = useState("");
  const [arbeitet, setArbeitet] = useState(false);
  const [kopiert, setKopiert] = useState(false);
  const beobachter = useRef<ReturnType<typeof nachfragen> | null>(null);
  const verbunden = useRef(beiVerbunden);
  verbunden.current = beiVerbunden;
  const fehltApp = useRef(ohneApp);
  fehltApp.current = ohneApp;

  useEffect(() => {
    let aktiv = true;
    api.microsoftConfig().then(wert => {
      if (!aktiv) return;
      setStand(wert);
      if (!wert.configured) fehltApp.current?.();
    }).catch(() => { if (aktiv) setFehler("Die Anmeldung bei Microsoft ist gerade nicht erreichbar. Bitte versuche es gleich noch einmal."); });
    return () => { aktiv = false; beobachter.current?.stop(); };
  }, []);

  function beobachten(sitzung: string) {
    beobachter.current?.stop();
    beobachter.current = nachfragen({
      lesen: () => api.microsoftNachfragen(sitzung),
      beiStand: naechster => {
        setAnmeldung(alt => ({ ...alt, ...naechster, sitzung }));
        if (naechster.status === "connected") verbunden.current(naechster);
      },
      beiFehler: () => setFehler("Kingfisher erreicht sich gerade selbst nicht. Es versucht es von allein weiter."),
    });
  }

  async function starten() {
    if (arbeitet) return;
    setArbeitet(true); setFehler(""); setKopiert(false);
    try {
      const neu = await api.microsoftAnmelden(adresse.trim(), mitschriften);
      setAnmeldung(neu);
      if (neu.sitzung) beobachten(neu.sitzung);
    } catch (problem) {
      setFehler(problem instanceof ApiError && problem.detail ? problem.detail : "Die Anmeldung bei Microsoft ließ sich nicht starten. Bitte versuche es gleich noch einmal.");
    } finally { setArbeitet(false); }
  }

  async function abbrechen() {
    if (!anmeldung?.sitzung) return;
    beobachter.current?.stop();
    try { await api.microsoftAbbrechen(anmeldung.sitzung); } catch { /* der Code läuft ohnehin ab */ }
    setAnmeldung({ ...anmeldung, status: "cancelled", satz: "Abgebrochen. Du kannst die Anmeldung jederzeit neu starten." });
  }

  async function kopieren() {
    if (!anmeldung?.user_code) return;
    try { await navigator.clipboard.writeText(anmeldung.user_code); setKopiert(true); }
    catch { setFehler("Kopieren ging nicht; markiere den Code und kopiere ihn von Hand."); }
  }

  const wartet = anmeldung && !istFertig(anmeldung);
  const ende = anmeldung && istFertig(anmeldung);
  const gesperrt = !stand?.configured || !stand.secure_storage;

  return <div className="ms-anmeldung" aria-label={mitschriften ? "Teams-Mitschriften dazunehmen" : "Mit Microsoft anmelden"}>
    {!anmeldung || ende ? <>
      <p className="source-hint">{mitschriften ? SAETZE.mitschriften : SAETZE.einleitung}</p>
      {stand && !stand.configured ? <p role="status" className="ms-fehlt">{SAETZE.ohneApp} {mitschriften ? null : SAETZE.ohnePasswortWeg}</p> : null}
      {stand && stand.configured && !stand.secure_storage ? <p role="alert">{SAETZE.ohneSpeicher}</p> : null}
      {anmeldung?.status !== "connected" ? <button type="button" className="primary-action" disabled={arbeitet || gesperrt} onClick={() => void starten()}>
        {arbeitet ? "Wird vorbereitet …" : ende ? "Neu anmelden" : knopf ?? "Mit Microsoft anmelden"}
      </button> : null}
    </> : null}
    {wartet && anmeldung.user_code ? <section className="ms-code" aria-label="Dein Code für Microsoft">
      <p>{SAETZE.schritte}</p>
      <div className="ms-code-zeile">
        <output className="ms-code-wert" aria-label="Code">{anmeldung.user_code}</output>
        <button type="button" className="secondary-action" onClick={() => void kopieren()}>{kopiert ? "Kopiert" : "Code kopieren"}</button>
      </div>
      <p><a className="primary-action ms-link" href={anmeldung.verification_uri || MS_LINK} target="_blank" rel="noopener noreferrer">Seite von Microsoft öffnen</a></p>
      <p role="status" className="ms-stand">{standSatz(anmeldung)}</p>
      {anmeldung.hinweis ? <p role="status" className="source-hint">{anmeldung.hinweis}</p> : null}
      <p className="source-hint">{SAETZE.admin}</p>
      <div className="ms-knoepfe">
        <button type="button" className="secondary-action" onClick={() => void beobachter.current?.jetzt()}>Jetzt nachsehen</button>
        <button type="button" className="text-action" onClick={() => void abbrechen()}>Abbrechen</button>
      </div>
    </section> : null}
    {ende ? <p role={anmeldung.status === "connected" ? "status" : "alert"} className={anmeldung.status === "connected" ? "erststart-ok" : "settings-error"}>{standSatz(anmeldung)}</p> : null}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </div>;
}
