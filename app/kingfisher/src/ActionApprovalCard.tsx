import { useState } from "react";
import type { ActionRequest } from "./api";

const labels = {
  approved: "Freigegeben. Das Ergebnis steht im Gespräch.",
  rejected: "Abgelehnt. Nichts ausgeführt.",
  expired: "Freigabe abgelaufen. Bitte einen neuen Vorschlag anfordern.",
  unknown: "Ergebnis unklar. Bitte prüfen, bevor du die Aktion erneut anforderst.",
};

export function ActionApprovalCard({ action, busy, onResolve }: {
  action: ActionRequest;
  busy: boolean;
  onResolve: (id: string, granted: boolean, confirmation: string) => Promise<void>;
}) {
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState(false);
  async function resolve(granted: boolean) {
    setError(false);
    try { await onResolve(action.id, granted, confirmation); }
    catch { setError(true); }
  }
  return <section className="memory-candidate action-approval" aria-label="Aktionsfreigabe">
    <span>AKTION ZUR FREIGABE</span>
    <p className="action-preview">{action.dry_run}</p>
    {action.state === "pending" ? <>
      {action.confirmation_phrase ? <label className="action-confirmation">
        Zur Bestätigung eingeben: <strong>{action.confirmation_phrase}</strong>
        <input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} disabled={busy} autoComplete="off" />
      </label> : null}
      <div className="memory-actions">
        <button type="button" className="memory-confirm" disabled={busy || Boolean(action.confirmation_phrase && confirmation !== action.confirmation_phrase)} onClick={() => resolve(true)}>Freigeben und ausführen</button>
        <button type="button" className="memory-reject" disabled={busy} onClick={() => resolve(false)}>Ablehnen</button>
      </div>
    </> : <p className="memory-notice" role="status">{labels[action.state]}</p>}
    {error ? <p role="alert">Freigabe nicht bestätigt. Bitte den Gesprächsstand neu laden und das Ergebnis prüfen.</p> : null}
  </section>;
}
