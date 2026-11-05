import type {TaskResponsibility, TaskResponsibilityCommand, TaskResponsibilityOperation, TaskResponsibilitySnapshot} from './api';

export type ResponsibilityDraft = {
  choice: '' | 'self' | 'person' | 'unknown' | 'undo';
  address: string;
  label: string;
  undoTarget?: number;
};

export function responsibilityLabel(owner: TaskResponsibility | null | undefined) {
  if (owner?.decision === 'person') return owner.label ? `${owner.label} <${owner.address}>` : owner.address ?? 'Person';
  if (owner?.decision === 'self') return 'Ich';
  if (owner?.decision === 'unknown') return 'Ungeklärt';
  return 'Nicht bestätigt';
}

export function responsibilityDraft(owner: TaskResponsibility | null | undefined): ResponsibilityDraft {
  return {choice: owner?.decision ?? '', address: owner?.address ?? '', label: owner?.label ?? ''};
}

export function responsibilityChange(snapshot: TaskResponsibilitySnapshot | null, draft: ResponsibilityDraft): TaskResponsibilityOperation | null {
  if (!snapshot || !draft.choice) return null;
  const current = snapshot.task.responsibility;
  if (draft.choice === 'undo') {
    return draft.undoTarget !== undefined && draft.undoTarget === snapshot.responsibility_event_sequence
      ? {operation: 'undo', target_event_sequence: draft.undoTarget} : null;
  }
  if (draft.choice === 'unknown') return current?.decision === 'unknown' ? null : {operation: 'reset'};
  if (draft.choice === 'self') return current?.decision === 'self' ? null : {operation: 'set', owner: {decision: 'self'}};
  const address = draft.address.trim();
  const label = draft.label.trim();
  if (!/^[^\s<>@]+@[^\s<>@]+\.[^\s<>@]+$/u.test(address) || address.length > 254 || label.length > 120) return null;
  if (current?.decision === 'person' && current.address === address.toLowerCase() && (current.label ?? '') === label) return null;
  return {operation: 'set', owner: {decision: 'person', address, ...(label ? {label} : {})}};
}

export function responsibilityAttempt(snapshot: TaskResponsibilitySnapshot | null, draft: ResponsibilityDraft,
                                      pending: TaskResponsibilityCommand | null, requestId: () => string): TaskResponsibilityCommand | null {
  if (pending) return pending;
  const body = responsibilityChange(snapshot, draft);
  return snapshot && body ? {...body, request_id: requestId(), expected_revision: snapshot.revision, confirmed: true} : null;
}

export function responsibilityFailure(status: number | undefined) {
  if (status === 409) return 'review';
  if (status === 422) return 'edit';
  return 'retry';
}
