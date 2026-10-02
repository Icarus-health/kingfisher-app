import { useEffect, useState } from "react";
import { api } from "./api";

const statuses: Record<string, string> = {active: "Aktuell", superseded: "Durch spätere Angabe ersetzt", expired: "Abgelaufen", retracted: "Widerrufen", redacted: "Inhalt entfernt", disputed: "Strittig"};
export function GoalHistory({ id }: { id: string }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<Awaited<ReturnType<typeof api.goalHistory>> | null>(null);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setError(false);setItems(null);
    api.goalHistory(id).then(value => {if (active) setItems(value);}).catch(() => {if (active) setError(true);});
    return () => {active = false;};
  }, [id, open, retry]);
  return <details open={open} onToggle={event => setOpen(event.currentTarget.open)}>
    <summary>Verlauf ansehen</summary>
    {open && <div aria-label="Zielverlauf" role="region">
      {!items && !error && <p role="status">Verlauf wird geladen …</p>}
      {items?.map(item => <div className="identity-source-row" key={item.id}>
        <p><time dateTime={item.recorded_at}>{new Date(item.recorded_at).toLocaleString("de-DE")}</time> · {statuses[item.status] ?? "Unbekannter Status"}</p>
        <p>{item.statement}</p>
        {item.status_changed_at && item.status_changed_at !== item.recorded_at && <p>Status geändert: {new Date(item.status_changed_at).toLocaleString("de-DE")}</p>}
      </div>)}
      {error && <p role="alert">Der Verlauf konnte nicht geladen werden. <button type="button" className="text-action" onClick={() => setRetry(value => value + 1)}>Erneut versuchen</button></p>}
    </div>}
  </details>;
}
