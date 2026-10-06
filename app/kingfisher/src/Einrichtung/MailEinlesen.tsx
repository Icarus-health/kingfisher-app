import {useCallback, useEffect, useState} from "react";
import {api, ApiError, type MailIntakeAccount} from "../api";
import {einlesenStand, einlesenVerweis} from "./einlesen";
import {einlesenFrage} from "./postfach";
import {Verweis} from "../VerweisLink";
import {MailErneut} from "./MailErneut";

const fehlerText = (fehler: unknown) => fehler instanceof ApiError && fehler.detail ? fehler.detail
  : "Das hat nicht geklappt. Bitte in einem Moment erneut versuchen.";

/**
 * Der eine Klick nach dem Verbinden: Kingfisher liest die Mails des Kontos ein (Umfang prüfen, dann starten,
 * wie in Einstellungen → Zugänge, nur in einem Zug). Erst dieser Klick startet das Einlesen; das Verbinden allein tut es nicht.
 * Während des Starts steht da, worauf gewartet wird; danach der Fortschritt, alle paar Sekunden neu. Antwortet das
 * Postfach nicht, kommt nach höchstens einer Viertelminute der Grund in einem Satz (Fremdprobe, Befund 4).
 */
export function MailEinlesen({beiGestartet}: {beiGestartet?: () => void}) {
  const [konten, setKonten] = useState<MailIntakeAccount[] | null>(null);
  // Die Adresse je Konto, damit die Frage „dein Postfach lena@example.org“ sagen kann (Fremdprobe 3, Befund 5).
  const [adressen, setAdressen] = useState<Record<string, string>>({});
  const [arbeitet, setArbeitet] = useState<string | null>(null);
  const [fehler, setFehler] = useState("");

  const laden = useCallback(async () => {
    try { setKonten((await api.mailIntake()).accounts); } catch { setKonten(current => current ?? []); }
  }, []);
  useEffect(() => { void laden(); }, [laden]);
  useEffect(() => {
    let aktiv = true;
    api.integrations().then(antwort => {
      if (aktiv) setAdressen(Object.fromEntries(antwort.mail_accounts.map(konto => [konto.id, konto.user])));
    }).catch(() => undefined);
    return () => { aktiv = false; };
  }, []);

  const laeuft = (konten ?? []).some(konto => konto.connected && konto.started);
  useEffect(() => {
    if (!laeuft) return;
    const timer = window.setInterval(() => { if (document.visibilityState === "visible") void laden(); }, 5000);
    return () => window.clearInterval(timer);
  }, [laeuft, laden]);

  async function starten(konto: MailIntakeAccount) {
    if (arbeitet) return;
    setArbeitet(konto.account_id); setFehler("");
    try {
      const umfang = await api.previewMailIntake(konto.account_id);
      await api.startMailIntake(konto.account_id, umfang.folders);
      await laden();
      beiGestartet?.();
    } catch (problem) { setFehler(fehlerText(problem)); }
    finally { setArbeitet(null); }
  }

  const verbunden = (konten ?? []).filter(konto => konto.connected);
  if (!verbunden.length) return null;
  return <div className="erststart-einlesen" aria-label="Mails einlesen">
    {verbunden.map(konto => konto.started
      ? <div key={konto.account_id}>
        <p role="status" className={konto.stand?.zustand === "gescheitert" ? undefined : "erststart-ok"}>{einlesenStand(konto)}{einlesenVerweis(konto) ? <> <Verweis ziel={einlesenVerweis(konto)!} />.</> : null}</p>
        {konto.stand?.zustand === "gescheitert"
          ? <MailErneut konto={konto.account_id} technik={konto.stand.technik} beiErgebnis={stand => setKonten(stand.accounts)} /> : null}
      </div>
      : <div key={konto.account_id}>
        <p>{einlesenFrage(konto.label, adressen[konto.account_id])}</p>
        <button className="primary-action" type="button" disabled={arbeitet !== null} onClick={() => void starten(konto)}>
          {arbeitet === konto.account_id ? "Wird gestartet …" : fehler ? "Erneut versuchen" : "Mails einlesen"}</button>
        {arbeitet === konto.account_id ? <p role="status" className="source-hint">Kingfisher fragt dein Postfach, welche Mailbereiche es gibt. Antwortet es nicht, steht hier gleich der Grund.</p> : null}
      </div>)}
    {fehler ? <p role="alert" className="settings-error">{fehler}</p> : null}
  </div>;
}
