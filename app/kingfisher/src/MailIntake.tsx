import {useEffect, useRef, useState} from "react";
import {api, ApiError, type MailAccount, type MailIntakeAccount, type MailIntakeStatus, type MailIntakePreview} from "./api";
import {deriveIntakeProgress, watchMailIntake} from "./mailIntakeProgress";
import "./MailIntake.css";
import {ordnerName} from "./mailAbruf";

// Für Techniker → Zeitplan und Hintergrund → „Ältere Mails einlesen“. Wörter ohne Technik (Fremdprobe, Befund 12): Ordner
// statt „Mailbereiche“, einlesen statt „Bestand aufnehmen“, „Posteingang“ statt „INBOX“.

const number = (value: number) => value.toLocaleString("de-DE");
const stageLabels: Record<string, string> = {
  disconnected: "Zugang fehlt", ready: "Verbunden · noch nicht eingelesen", paused: "Einlesen pausiert",
  error: "Einlesen braucht Aufmerksamkeit", inventory: "Mails werden gezählt", capture: "Mails werden eingelesen",
  waiting_analysis: "Ältere Mails warten auf das Sortieren",
  analysis: "Inhalte sortieren · noch ausstehend", current: "Eingelesen · neue Mails kommen regelmäßig dazu",
};

function scopeLabel(account: MailIntakeAccount) {
  if (!account.started) return "Kingfisher schaut zuerst nach, welche Ordner es gibt, und zeigt sie dir vor dem Einlesen.";
  if (account.folders.every(folder => folder.folder === "INBOX")) return "Nur der Posteingang. Gesendete und archivierte Mails sind nicht dabei.";
  return `Gelesen werden: ${account.folders.map(folder => ordnerName(folder.folder)).join(", ")}. Neue Mails aus diesen Ordnern kommen laufend dazu.`;
}

function errorLabel(error: string) {
  if (error === "credentials_missing") return "Zugangsdaten fehlen. Prüfe die Verbindung dieses Kontos.";
  if (error === "uidvalidity_changed") return "Ein Ordner im Postfach hat sich geändert. Kingfisher gleicht ihn neu ab.";
  if (error === "model_disabled") return "Das Sortieren wartet darauf, dass du die lokale KI freigibst.";
  return "Das Einlesen kam zuletzt nicht weiter. Prüfe das Postfach unter Zugänge und lade den Stand neu.";
}

function FolderProgress({account, index}: {account: MailIntakeAccount; index: number}) {
  const folder = account.folders[index];
  const progress = deriveIntakeProgress({...account, folders: [folder]});
  const label = `${account.label} · ${ordnerName(folder.folder)}`;
  return <section className="mail-intake-folder" aria-label={`Fortschritt ${label}`}>
    <h4>{ordnerName(folder.folder)}</h4>
    <ol className="mail-intake-stages">
      <li>
        <strong>Mails zählen</strong>
        <p>{progress.total === null ? `${number(progress.counted)} Mails bisher gezählt · wie viele es insgesamt sind, ist noch offen.`
          : `${number(progress.total)} Mails gezählt.`}</p>
        {progress.total === null && <progress aria-label={`Mails zählen: ${label}; Gesamtzahl noch offen`} />}
      </li>
      <li>
        <strong>Mails einlesen</strong>
        <p>{number(progress.captured)} neu gespeichert · {number(progress.duplicates)} schon bekannt
          {progress.total !== null ? ` · ${number(progress.processed)} von ${number(progress.total)} Mails gelesen` : " · Gesamtzahl noch offen"}</p>
        <progress max={100} value={progress.capturePercent ?? undefined}
          aria-label={`Mails einlesen: ${label}`} aria-valuetext={progress.total === null ? "Gesamtzahl noch offen"
            : `${number(progress.processed)} von ${number(progress.total)} Mails gelesen`} />
        <p>{number(progress.pending)} warten noch · {number(progress.failed)} ließen sich nicht abrufen</p>
      </li>
      <li>
        <strong>Inhalte sortieren</strong>
        <p>{number(progress.analyzed)} von {number(progress.analysisSources)} vorgesehenen Quellen inhaltlich sortiert.</p>
        <p>{progress.categoriesKnown ? `${number(progress.categorized)} von ${number(progress.analysisSources)} Quellen mit Themen versehen.` : "Themen: Stand noch unbekannt."}</p>
        <progress max={100} value={progress.analysisPercent ?? undefined}
          aria-label={`Inhalte sortieren: ${label}`} aria-valuetext={progress.total === null ? "Mails noch nicht alle gezählt"
            : !progress.categoriesKnown ? "Stand der Kategorisierung unbekannt"
            : `${number(progress.analyzed)} von ${number(progress.analysisSources)} Quellen sortiert; ${number(progress.categorized)} mit Themen versehen`} />
        <p>{number(progress.deferred)} zurückgestellt · {number(progress.analysisFailed)} Fehler beim Sortieren · {number(progress.excluded)} bewusst ausgeschlossen</p>
        {progress.categoriesKnown && <p>Kategorien: {number(progress.categoriesPending)} ausstehend · {number(progress.categoriesFailed)} fehlgeschlagen</p>}
      </li>
      <li><strong>Ergebnisse prüfen</strong><p>Automatische Kategorien und Hinweise bleiben Vorschläge. Prüfe sie mit den Originalstellen in der jeweiligen Quelle.</p></li>
    </ol>
    <p className="mail-intake-current">Neue Mails in diesem Ordner: {number(progress.livePending)} warten noch · {number(progress.liveFailed)} Abrufe fehlgeschlagen · {number(progress.liveFiltered)} ausgefiltert. Sie werden getrennt vom älteren Bestand gezählt.</p>
  </section>;
}

export function MailIntake({accounts, active, onChanged}: {
  accounts: MailAccount[];
  active: boolean;
  onChanged: () => void;
}) {
  const [status, setStatus] = useState<MailIntakeStatus | null>(null);
  const [message, setMessage] = useState("");
  const messageKind = useRef<"status" | "action" | null>(null);
  const [busyAccount, setBusyAccount] = useState<string | null>(null);
  const [backgroundBusy, setBackgroundBusy] = useState(false);
  const [checkingScope, setCheckingScope] = useState(false);
  const [previews, setPreviews] = useState<Record<string, MailIntakePreview>>({});
  const watcher = useRef<ReturnType<typeof watchMailIntake> | null>(null);
  const actionBusy = useRef(false);
  const activeRef = useRef(active);
  activeRef.current = active;
  const changedRef = useRef(onChanged);
  changedRef.current = onChanged;
  const accountsKey = accounts.map(account => `${account.id}:${account.configured}:${account.secret_present}`).join("|");
  const busy = busyAccount !== null || backgroundBusy;

  useEffect(() => {
    let mounted = true;
    setBusyAccount(null);
    setBackgroundBusy(false);
    setCheckingScope(false);
    actionBusy.current = false;
    setPreviews({});
    const current = watchMailIntake({
      read: signal => api.mailIntake(signal),
      onStatus: next => {if (mounted) {setStatus(next); if (messageKind.current === "status") {setMessage(""); messageKind.current = null;}}},
      onError: (kind, error) => {
        if (!mounted) return;
        messageKind.current = kind;
        if (error instanceof ApiError && error.status === 409) {
          setPreviews({});
          setMessage("Die Ordner im Postfach haben sich geändert. Sieh sie dir noch einmal an, bevor du einliest.");
        } else setMessage(kind === "action" ? "Das hat nicht geklappt. Bitte noch einmal versuchen."
          : "Der Stand konnte gerade nicht geladen werden. Der letzte bekannte Stand bleibt sichtbar; Kingfisher versucht es erneut.");
      },
      visible: activeRef.current && document.visibilityState === "visible",
    });
    watcher.current = current;
    const visible = () => current.setVisible(activeRef.current && document.visibilityState === "visible");
    document.addEventListener("visibilitychange", visible);
    return () => {
      mounted = false;
      current.stop();
      document.removeEventListener("visibilitychange", visible);
      if (watcher.current === current) watcher.current = null;
    };
  }, [accountsKey]);
  useEffect(() => {
    watcher.current?.setVisible(active && document.visibilityState === "visible");
  }, [active]);

  async function change(account: MailIntakeAccount, retry = false) {
    const current = watcher.current;
    if (!current || actionBusy.current) return;
    const preview = previews[account.account_id];
    if (!account.started && !preview) return;
    actionBusy.current = true;
    setBusyAccount(account.account_id); setMessage("");
    setCheckingScope(false);
    messageKind.current = null;
    const success = await current.run(signal => retry ? api.retryMailIntake(account.account_id, signal)
      : !account.started ? api.startMailIntake(account.account_id, preview.folders, signal)
      : api.pauseMailIntake(account.account_id, !account.paused, signal));
    if (watcher.current !== current) return;
    actionBusy.current = false;
    setBusyAccount(null);
    if (success) changedRef.current();
  }
  async function preview(account: MailIntakeAccount) {
    const current = watcher.current;
    if (!current || actionBusy.current) return;
    actionBusy.current = true;
    setBusyAccount(account.account_id); setMessage("");
    setCheckingScope(true);
    messageKind.current = null;
    const result = await current.inspect(signal => api.previewMailIntake(account.account_id, signal));
    if (watcher.current !== current) return;
    actionBusy.current = false;
    setBusyAccount(null);
    setCheckingScope(false);
    if (result) setPreviews(values => ({...values, [account.account_id]: result}));
  }

  async function resumeBackground() {
    const current = watcher.current;
    if (!current || actionBusy.current) return;
    actionBusy.current = true;
    setBackgroundBusy(true); setMessage(""); messageKind.current = null;
    const success = await current.run(async signal => {
      await api.hintergrundPausieren(false);
      return api.mailIntake(signal);
    });
    if (watcher.current !== current) return;
    actionBusy.current = false;
    setBackgroundBusy(false);
    if (success) changedRef.current();
  }

  return <section className="mail-intake" aria-label="Ältere Mails einlesen">
    <p>Kingfisher liest auf Wunsch auch die Mails, die schon in deinem Postfach liegen: Zuerst schaut es nach, welche Ordner es gibt, dann liest es sie ein und hält sie aktuell. Spam, Papierkorb und Anhänge bleiben außen vor; was eingelesen ist, gilt noch nicht als bestätigt.</p>
    {status?.background_paused && <div role="status">
      <p>Die gesamte Hintergrundarbeit ist pausiert. Bereits gespeicherte Inhalte bleiben verfügbar. Setze sie hier fort; einzeln pausierte Postfächer behalten ihre eigene Pause.</p>
      <button className="secondary-action" type="button" disabled={busy} onClick={() => {void resumeBackground();}}>
        {backgroundBusy ? "Wird fortgesetzt …" : "Verarbeitung fortsetzen"}
      </button>
    </div>}
    {status?.analysis_active === false && <p role="status">Das Sortieren ist pausiert oder es ist keine lokale KI da. Eingelesene Mails bleiben gespeichert; ausgewertet werden sie, sobald das Sortieren läuft (oben unter „Quellen automatisch sortieren“).</p>}
    {!status && !message && <p role="status">Wird geladen …</p>}
    {status && !status.accounts.length && <p>Verbinde zuerst ein Postfach unter Zugänge.</p>}
    {status?.accounts.filter(account => accounts.some(configured => configured.id === account.account_id)).map(account => {
      const progress = deriveIntakeProgress(account);
      const checked = previews[account.account_id];
      const filtered = progress.filtered + progress.liveFiltered;
      const retryFailed = progress.failed > 0 || progress.liveFailed > 0 || progress.analysisFailed > 0 || progress.categoriesFailed > 0 || account.error;
      return <article className="mail-intake-account" key={account.account_id}>
        <div className="mail-intake-heading"><h3>{account.label}</h3><span>{status.background_paused && ["inventory", "capture", "analysis", "waiting_analysis"].includes(progress.stage)
          ? "Verarbeitung pausiert" : stageLabels[progress.stage]}</span></div>
        {account.stand && <p>{account.stand.satz}</p>}
        {progress.stage === "waiting_analysis" && !status.background_paused && <a className="text-action" href="/memory?view=status">Automatisches Sortieren prüfen →</a>}
        <p>{!account.started && checked ? checked.description : scopeLabel(account)}</p>
        {!account.started && checked && <p>Gefunden: {checked.folders.map(ordnerName).join(", ")}. Diese Ordner liest Kingfisher ein, und neue Mails daraus kommen laufend dazu.</p>}
        {account.paused && <p>Das Einlesen pausiert. Was schon gespeichert ist, bleibt, und es geht dort weiter, wo es aufgehört hat.</p>}
        {!account.started && <button className="secondary-action" type="button" disabled={!account.connected || busy}
          aria-label={`Ordner ansehen: ${account.label}`} onClick={() => {void preview(account);}}>{busyAccount === account.account_id && checkingScope ? "Kingfisher schaut nach …" : checked ? "Ordner noch einmal ansehen" : "Ordner ansehen"}</button>}
        <button className="secondary-action" type="button" disabled={!account.connected || busy || Boolean(status.background_paused && account.started) || (!account.started && !checked?.folders.length)}
          aria-label={`${!account.started ? "Diese Ordner einlesen" : account.paused ? "Einlesen fortsetzen" : "Einlesen pausieren"}: ${account.label}`}
          onClick={() => {void change(account);}}>
          {busyAccount === account.account_id && !checkingScope ? "Wird gespeichert …" : !account.started ? "Diese Ordner einlesen" : account.paused ? "Einlesen fortsetzen" : "Einlesen pausieren"}
        </button>
        {account.started && (retryFailed || filtered > 0) && <>
          <button className="text-action" type="button" disabled={!account.connected || busy}
            onClick={() => {void change(account, true);}}>{filtered > 0
              ? retryFailed ? "Ausgefilterte Mails und Fehler erneut prüfen" : "Ausgefilterte Mails erneut prüfen"
              : "Fehlgeschlagenes noch einmal versuchen"}</button>
          {filtered > 0 && <p>Nur auf deinen Klick: {number(filtered)} ausgefilterte Mails werden mit den aktuellen Regeln erneut geprüft. Auch Mails, die wegen voller Prüfliste dort nicht angezeigt werden, sind dabei. Das geschieht nicht automatisch.</p>}
        </>}
        {!account.connected && <p>Für dieses Postfach fehlen gültige Zugangsdaten. Verbinde es unter Zugänge neu.</p>}
        {account.error && <p role="alert">{errorLabel(account.error)}</p>}
        {account.started && !account.folders.length && <p>Kingfisher schaut nach, welche Ordner es gibt.</p>}
        {account.folders.map((folder, index) => <FolderProgress key={folder.folder} account={account} index={index} />)}
      </article>;
    })}
    {message && <p role="alert">{message}</p>}
    <button className="text-action" type="button" disabled={busy} onClick={() => {void watcher.current?.refresh();}}>Stand neu laden</button>
  </section>;
}
