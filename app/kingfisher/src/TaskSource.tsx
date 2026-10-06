import { useEffect, useState } from "react";
import { api, type TaskSource as Source } from "./api";
import { Herkunft } from "./HerkunftAnzeige";

export function TaskSource({taskId}: {taskId: string}) {
  const [open, setOpen] = useState(false);
  const [source, setSource] = useState<Source | null>(null);
  const [error, setError] = useState(false);
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    if (!open) return;
    let active = true;
    setSource(null); setError(false);
    api.taskSource(taskId).then(value => { if (active) setSource(value); })
      .catch(() => { if (active) setError(true); });
    return () => { active = false; };
  }, [open, taskId, revision]);
  return <div className="task-source">
    <button type="button" className="secondary-action" aria-expanded={open} onClick={() => setOpen(value => !value)}>{open ? "Quelle schließen" : "Quelle öffnen"}</button>
    {open && <section aria-label="Gespeicherte Aufgabenquelle">
      {!source && !error && <p role="status">Quelle wird geladen …</p>}
      {error && <p role="alert">Die gespeicherte Quelle ist nicht verfügbar. <button type="button" onClick={() => setRevision(value => value + 1)}>Erneut versuchen</button></p>}
      {source && <><h3>{source.title}</h3><p>Gespeicherter Stand · Rohmaterial, keine bestätigte Aussage</p>
        {source.state === "ignored" && <p role="status">Diese Quelle wurde ausgeschlossen und darf nicht als Wissensbeleg verwendet werden.</p>}
        {source.quote && <div><p>Übernommene Textstelle</p><blockquote>{source.quote}</blockquote></div>}
        <p>Aufgenommen: {new Date(source.recorded_at).toLocaleString("de-DE")}</p>
        {source.participants.length > 0 && <p>In der Quelle genannt: {source.participants.join(", ")}</p>}
        <Herkunft provenance={source.provenance} />
        <div className="task-source-body">{source.body}</div>
        {source.truncated && <p>Auszug: Die Quelle ist länger als die angezeigten 20.000 Zeichen.</p>}
      </>}
    </section>}
  </div>;
}
