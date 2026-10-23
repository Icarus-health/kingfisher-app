import type {Task} from './api';

export type TaskSelection = {view: 'mine' | 'waiting' | 'done'; projectId: string; q: string};
type Page = {tasks: Task[]; total: number; next_cursor: string | null};
export type TaskPageState = {tasks: Task[] | null; total: number; loading: boolean; error: string; notice: string; canPrevious: boolean; canNext: boolean; page: number; selectionKey: string};
export const initialTaskPage = (): TaskPageState => ({tasks: null, total: 0, loading: false, error: '', notice: '', canPrevious: false, canNext: false, page: 1, selectionKey: ''});

/** Navigation is snapshot-bound; old requests never replace a newer selection. */
export class TaskPager {
  private version = 0;
  private selection: TaskSelection | null = null;
  private cursor: string | null = null;
  private history: Array<string | null> = [];
  private result: Page | null = null;
  private loading = false;
  private fetchPage: (selection: TaskSelection, cursor: string | null) => Promise<Page>;
  private emit: (state: TaskPageState) => void;
  constructor(fetchPage: (selection: TaskSelection, cursor: string | null) => Promise<Page>, emit: (state: TaskPageState) => void) {
    this.fetchPage = fetchPage; this.emit = emit;
  }

  cancel() {this.version++; this.loading = false;}
  select(selection: TaskSelection) {this.selection = selection; return this.load(null, []);}
  refresh() {return this.load(null, []);}
  /** Lädt die aktuelle Seite still neu (Fenster wieder im Blick): Die Liste bleibt stehen, bis die neue da ist. */
  reload() {return this.selection && !this.loading ? this.load(this.cursor, this.history, '', true) : Promise.resolve();}
  next() {return !this.loading && this.result?.next_cursor ? this.load(this.result.next_cursor, [...this.history, this.cursor]) : Promise.resolve();}
  previous() {return !this.loading && this.result && this.history.length ? this.load(this.history[this.history.length - 1], this.history.slice(0, -1)) : Promise.resolve();}

  private async load(cursor: string | null, history: Array<string | null>, notice = '', quiet = false): Promise<void> {
    if (!this.selection) return;
    const version = ++this.version;
    const selection = this.selection;
    const previous = this.result;
    this.loading = true;
    if (!quiet) this.result = null;
    const selectionKey = JSON.stringify(selection);
    if (!quiet) this.emit({...initialTaskPage(), loading: true, notice, selectionKey});
    try {
      const result = await this.fetchPage(selection, cursor);
      if (version !== this.version) return;
      this.cursor = cursor; this.history = history; this.result = result; this.loading = false;
      this.emit({tasks: result.tasks, total: result.total, loading: false, error: '', notice, canPrevious: history.length > 0, canNext: Boolean(result.next_cursor), page: history.length + 1, selectionKey});
    } catch (error) {
      if (version !== this.version) return;
      if (cursor && (error as {status?: number})?.status === 409) {
        await this.load(null, [], 'Die Aufgaben wurden inzwischen geändert. Die Liste wurde neu geladen.');
        return;
      }
      this.loading = false;
      // Ein stilles Nachladen, das scheitert, lässt die sichtbare Liste stehen; der nächste Anlass versucht es erneut.
      if (quiet && previous) { this.result = previous; return; }
      this.emit({...initialTaskPage(), error: 'Die Aufgaben sind gerade nicht erreichbar. Bitte die Liste neu laden.', notice, selectionKey});
    }
  }
}
