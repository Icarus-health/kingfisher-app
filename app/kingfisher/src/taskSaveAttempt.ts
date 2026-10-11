/** Native WebKit may supply random bytes without exposing randomUUID. */
export function newTaskRequestId(random: Pick<Crypto, 'randomUUID' | 'getRandomValues'> = crypto): string {
  if (typeof random.randomUUID === 'function') return random.randomUUID();
  const bytes = random.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

/** One explicit draft keeps its identity across uncertain save responses. */
export class TaskSaveAttempt {
  private id: string | null = null;
  private pending = false;
  private confirmed = false;
  private readonly newId: () => string;
  constructor(newId: () => string = newTaskRequestId) {this.newId = newId;}
  get inFlight() {return this.pending;}
  get succeeded() {return this.confirmed;}
  async save<P extends object, T>(payload: P, send: (value: P & {request_id: string}) => Promise<T>): Promise<T | null> {
    if (this.pending || this.confirmed) return null;
    this.id ??= this.newId();
    this.pending = true;
    try {
      const result = await send({...payload, request_id: this.id});
      this.confirmed = true;
      return result;
    } finally {this.pending = false;}
  }
}

export const TASK_SAVE_UNCONFIRMED = 'Die Speicherung wurde nicht bestätigt. Deine Eingaben bleiben erhalten. Beim Wiederholen wird derselbe Speicherauftrag geprüft. Vor dem Schließen bitte die vorhandenen Aufgaben prüfen.';
