export function TaskRetryReview({reviewed, busy, onReviewed, onPrepareNew}: {
  reviewed: boolean; busy: boolean; onReviewed: (value: boolean) => void; onPrepareNew: () => void;
}) {
  return <div className="decision-form-actions task-retry-review">
    <label><input type="checkbox" checked={reviewed} disabled={busy} onChange={event => onReviewed(event.target.checked)} />Ich habe die vorhandenen Aufgaben geprüft.</label>
    <button type="button" className="secondary-action" disabled={busy || !reviewed} onClick={onPrepareNew}>Neuen Speicherauftrag vorbereiten</button>
  </div>;
}
import './TaskRetryReview.css';

