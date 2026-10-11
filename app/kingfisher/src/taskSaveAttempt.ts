/** Native WebKit may supply random bytes without exposing randomUUID. */
export function newTaskRequestId(random: Pick<Crypto, 'randomUUID' | 'getRandomValues'> = crypto): string {
  if (typeof random.randomUUID === 'function') return random.randomUUID();
  const bytes = random.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

type RetryStorage = Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>;
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
export class TaskSavePreparationError extends Error {}
export const MANUAL_TASK_REQUEST_KEY = 'kingfisher:manual-task-request';
export const goalTaskRequestKey = (id: string) => `kingfisher:goal-task-request:${encodeURIComponent(id)}`;

/** Persist only an opaque request identity, never task fields. */
export class TaskSaveAttempt {
  private id: string | null = null;
  private pending = false;
  private confirmed = false;
  private readonly newId: () => string;
  private readonly pendingKey: string | undefined;
  private readonly storage: () => RetryStorage;
  private observed = false;
  private observedValue: string | null = null;
  constructor(newId: () => string = newTaskRequestId, pendingKey?: string, storage: () => RetryStorage = () => localStorage) {
    this.newId = newId; this.pendingKey = pendingKey; this.storage = storage;
  }
  get inFlight() {return this.pending;}
  get succeeded() {return this.confirmed;}
  restore(): boolean {
    if (!this.pendingKey) return false;
    try {
      const previous = this.storage().getItem(this.pendingKey);
      this.observed = true; this.observedValue = previous;
      if (previous && !UUID_V4.test(previous)) throw new TaskSavePreparationError('Die gespeicherte Auftragskennung ist ungültig.');
      if (this.id && previous && this.id !== previous) throw new TaskSavePreparationError('Ein anderer Speicherauftrag ist noch ungeklärt.');
      this.id ??= previous;
      return this.id !== null;
    } catch (cause) {if (cause instanceof TaskSavePreparationError) throw cause; throw new TaskSavePreparationError('Der lokale Speicher ist nicht verfügbar. Bitte die Speicherfreigabe prüfen.');}
  }
  resetAfterReview(): void {
    if (this.pending) throw new TaskSavePreparationError('Eine Speicherung läuft noch. Bitte kurz warten.');
    if (this.pendingKey) {
      if (!this.observed) throw new TaskSavePreparationError('Der lokale Speicherstand ist ungeklärt. Bitte das Formular erneut öffnen.');
      const store = this.storage(), previous = store.getItem(this.pendingKey);
      if (previous !== this.observedValue || (this.id && previous && this.id !== previous)) throw new TaskSavePreparationError('Ein anderer Speicherauftrag ist noch ungeklärt.');
      store.removeItem(this.pendingKey);
      this.observedValue = null;
    }
    this.id = null; this.confirmed = false;
  }
  async save<P extends object, T>(payload: P, send: (value: P & {request_id: string}) => Promise<T>): Promise<T | null> {
    if (this.pending || this.confirmed) return null;
    this.pending = true;
    try {
      let store: RetryStorage | null = null;
      try {
        this.restore();
        this.id ??= this.newId();
        if (this.pendingKey) {
          if (!UUID_V4.test(this.id)) throw new TaskSavePreparationError('Die Auftragskennung ist ungültig.');
          store = this.storage();
          store.setItem(this.pendingKey, this.id);
          this.observed = true; this.observedValue = this.id;
        }
      } catch (cause) {if (cause instanceof TaskSavePreparationError) throw cause; throw new TaskSavePreparationError('Der Speicherauftrag konnte nicht vorbereitet werden. Bitte den lokalen Speicher prüfen.');}
      const result = await send({...payload, request_id: this.id});
      this.confirmed = true;
      if (store && this.pendingKey) {
        try {if (store.getItem(this.pendingKey) === this.id) store.removeItem(this.pendingKey);}
        catch { /* Retaining a confirmed request is safe; do not invent a new identity. */ }
      }
      return result;
    } finally {this.pending = false;}
  }
}

export const TASK_SAVE_UNCONFIRMED = 'Die Speicherung wurde nicht bestätigt. Deine Eingaben bleiben erhalten. Beim Wiederholen wird derselbe Speicherauftrag geprüft, auch nach erneutem Öffnen. Bitte die vorhandenen Aufgaben prüfen, bevor du einen neuen Auftrag vorbereitest.';
export const TASK_SAVE_PENDING = 'Ein früherer Speicherauftrag ist noch ungeklärt. Es wird dieselbe Kennung verwendet. Bitte die vorhandenen Aufgaben prüfen; Eingaben des früheren Entwurfs werden hier nicht gespeichert.';
