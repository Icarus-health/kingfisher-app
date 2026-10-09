"""Persistent bounded mailbox intake. Originals and processing progress share a transaction."""
from dataclasses import replace
from contextlib import nullcontext
import json
import time
from collections import Counter

from . import logbuch
from .mail_filter import excluded_folder, intake_screen
from .episodes import sql_nicht_ignoriert
from .mail_ingestion import remember
from .connectors.mail import MailboxGenerationChanged, MailError
from .mail_intake_grund import einordnen as grund_einordnen
from .migrations import IndexContract

#: Der Stand nach Migration 11 (bis Schema 16).
TABLES_V11 = {
    'mail_intake_analysis': {'episode_id','generation','status'},
    'mail_intake_folders': {'account','folder','generation','upper_uid','scan_uid','live_uid','inventory_complete','paused','error','updated'},
    'mail_intake_items': {'account','folder','generation','uid','lane','status','episode_id','attempts','retry_at'},
}
#: Seit Migration 17 trägt ein gescheiterter Eintrag seinen Grund (`grund`, ein Kürzel aus `mail_intake_grund`) und die
#: technische Angabe dazu (`technik`, nur Fehlerklassen und eigene Meldungen, nie Text vom Server oder aus der Mail).
TABLES = {**TABLES_V11, 'mail_intake_items': TABLES_V11['mail_intake_items'] | {'grund','technik'}}
#: Vorsilbe des Status ausgefilterter Nachrichten, danach die Kategorie (spam, newsletter, blocked, unclear).
#: Bewusst im vorhandenen Statusfeld: kein neues Schema, und alle Abfragen nach pending/failed/captured übergehen es.
FILTERED='filtered:'
#: Einträge je Lesefenster von `Intake.status`; klein genug, dass die Episodensperre nur Millisekunden gehalten wird.
STATUS_WINDOW=1000
# At most this many distinct failed category sources are reopened for a fresh projection per status request.
# Each check may fingerprint an original (up to the category body bound), so keep frequent UI polling cheap.
CATEGORY_DIAGNOSTIC_BUDGET=16
#: Nachrichten je Hintergrundtakt (alle 30 s). Vorher 8, weil jede Nachricht eine eigene TLS-Verbindung mit Anmeldung
#: brauchte (rechnerisch rund 1000 je Stunde). Über eine Sitzung kostet sie nur noch den Abruf; 25 bleiben kurz genug,
#: dass der Takt die Nachanalyse neuer Uploads (teilt sich dessen Sperre) nur Sekunden warten lässt. Abgerufen wird
#: außerhalb jeder Sperre, `conversation_lock` gilt nur für das Schreiben der einzelnen Nachricht.
BACKGROUND_BATCH=25
PRIMARY_KEYS = {'mail_intake_analysis': {'episode_id'},'mail_intake_folders': {'account','folder'}, 'mail_intake_items': {'account','folder','generation','uid'}}
INDEXES = {'idx_mail_intake_queue': IndexContract('mail_intake_items',('account','status','retry_at','lane','uid')),
           'idx_mail_intake_episode': IndexContract('mail_intake_items',('episode_id',))}


def migrate(conn):
    conn.execute("CREATE TABLE mail_intake_analysis(episode_id TEXT PRIMARY KEY,generation INTEGER NOT NULL,status TEXT NOT NULL)")
    conn.execute('''CREATE TABLE mail_intake_folders (
        account TEXT NOT NULL, folder TEXT NOT NULL, generation TEXT,
        upper_uid INTEGER NOT NULL DEFAULT 0, scan_uid INTEGER NOT NULL DEFAULT 0,
        live_uid INTEGER NOT NULL DEFAULT 0, inventory_complete INTEGER NOT NULL DEFAULT 0,
        paused INTEGER NOT NULL DEFAULT 0, error TEXT, updated REAL NOT NULL DEFAULT 0,
        PRIMARY KEY(account,folder))''')
    conn.execute('''CREATE TABLE mail_intake_items (
        account TEXT NOT NULL, folder TEXT NOT NULL, generation TEXT NOT NULL, uid INTEGER NOT NULL,
        lane TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', episode_id TEXT,
        attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0,
        PRIMARY KEY(account,folder,generation,uid))''')
    conn.execute('CREATE INDEX idx_mail_intake_queue ON mail_intake_items(account,status,retry_at,lane,uid)')
    conn.execute('CREATE INDEX idx_mail_intake_episode ON mail_intake_items(episode_id)')


def migrate_grund(conn):
    """Migration 17: Wer scheitert, sagt warum (Fremdprobe 3, Befund 2). Vorher verschluckte die Aufnahme den Grund."""
    conn.execute('ALTER TABLE mail_intake_items ADD COLUMN grund TEXT')
    conn.execute('ALTER TABLE mail_intake_items ADD COLUMN technik TEXT')


class Intake:
    def __init__(self, episodes):
        self.episodes = episodes
        self.db = episodes._conn

    def accounts(self):
        with self.episodes._lock:
            return [r[0] for r in self.db.execute('SELECT DISTINCT account FROM mail_intake_folders')]

    def start(self, account, folders):
        if not account or not folders or len(folders)>20 or any(not isinstance(f,str) or not f or len(f)>512 or excluded_folder(f) for f in folders):
            raise ValueError('Ungültige Mailbereiche')
        with self.episodes.transaction():
            for folder in dict.fromkeys(folders):
                self.db.execute('INSERT INTO mail_intake_folders(account,folder) VALUES(?,?) ON CONFLICT DO NOTHING',(account,folder))
            self.db.execute('UPDATE mail_intake_folders SET paused=0 WHERE account=?',(account,))

    def pause(self, account, paused):
        with self.episodes.transaction():
            self.db.execute('UPDATE mail_intake_folders SET paused=? WHERE account=?',(int(paused),account))

    def retry(self, account):
        """„Erneut versuchen“: Gescheiterte gelten wieder als offen und kommen beim nächsten Takt zuerst dran.

        Sie stehen dann als „wird gelesen“ da, nicht mehr als gescheitert: Das stimmt, sobald der nächste Takt läuft,
        und scheitern sie wieder, steht der Grund neu da. Die Zahl der Versuche bleibt (sie ordnet die Reihenfolge).
        """
        with self.episodes.transaction():
            self.db.execute("UPDATE mail_intake_items SET status='pending',retry_at=0,grund=NULL,technik=NULL WHERE account=? AND status='failed'",(account,))
            # Ausgefilterte werden nach den (vielleicht geänderten) Regeln neu geprüft.
            self.db.execute("UPDATE mail_intake_items SET status='pending',retry_at=0 WHERE account=? AND status>=? AND status<?",(account,FILTERED,FILTERED[:-1]+';'))
            self.db.execute('UPDATE mail_intake_folders SET error=NULL WHERE account=?',(account,))
            for table in ('working_memory_sources','memory_category_sources'):
                self.db.execute(f"UPDATE {table} SET retry_after=0 WHERE status='failed' AND episode_id IN (SELECT episode_id FROM mail_intake_items WHERE account=?)",(account,))

    def _active(self, account, permitted):
        if not permitted():return False
        with self.episodes._lock:
            row=self.db.execute('SELECT MIN(paused) FROM mail_intake_folders WHERE account=?',(account,)).fetchone()
        return row is not None and row[0]==0

    def aktiv(self, account, permitted):
        """Ob die Aufnahme des Kontos läuft (freigegeben und nicht pausiert); für nachrangige Hintergrundarbeit."""
        return self._active(account,permitted)

    def _inventory(self, account, reader, row, live, permitted, gate):
        folder=row['folder']; generation=row['generation']
        page=reader.inventory_page(folder,
            after_uid=row['live_uid'] if live else row['scan_uid'],
            before_uid=None if live or generation is None else row['upper_uid'],
            limit=200, uidvalidity=generation)
        with gate:
            if not self._active(account,permitted):return
            with self.episodes.transaction():
                if generation is not None and page['uidvalidity']!=generation:
                    raise ValueError('generation changed')
                if generation is None:
                    generation=page['uidvalidity']
                    self.db.execute('UPDATE mail_intake_folders SET generation=?,upper_uid=?,live_uid=? WHERE account=? AND folder=?',
                                    (generation,page['upper_uid'],page['upper_uid'],account,folder))
                for uid in page['uids']:
                    self.db.execute('INSERT INTO mail_intake_items(account,folder,generation,uid,lane) VALUES(?,?,?,?,?) ON CONFLICT DO NOTHING',
                                    (account,folder,generation,uid,'live' if live else 'history'))
                if live:
                    self.db.execute('UPDATE mail_intake_folders SET live_uid=?,error=NULL,updated=? WHERE account=? AND folder=?',
                                    (page['next_uid'],time.time(),account,folder))
                else:
                    self.db.execute('UPDATE mail_intake_folders SET scan_uid=?,inventory_complete=?,error=NULL,updated=? WHERE account=? AND folder=?',
                                    (page['next_uid'],int(page['done']),time.time(),account,folder))

    def _captured(self, item, episode_id, created):
        self.db.execute("UPDATE mail_intake_items SET status=?,episode_id=?,attempts=attempts+1,grund=NULL,technik=NULL WHERE account=? AND folder=? AND generation=? AND uid=?",
                        ('captured' if created else 'duplicate',episode_id,item['account'],item['folder'],item['generation'],item['uid']))
        if item['lane'] == 'live':
            from .task_rechecks import enqueue
            enqueue(self.episodes, episode_id)

    def background_step(self, account, reader, settings, *, permitted, permission_lock, claims, provider=None, hold=None):
        """Ein Hintergrundtakt mit den Filterregeln der Einstellungen (`mail_filter.intake_screen`)."""
        # AI screening is bounded to two messages; the ordinary no-model fetch stays fast.
        batch = 2 if settings.mail_filter.get('ai_enabled') else BACKGROUND_BATCH
        return self.step(account,reader,batch=batch,permitted=permitted,permission_lock=permission_lock,
                         claims=claims,screen=intake_screen(settings,provider),hold=hold)

    def _filtered(self, item, category):
        # Kein Fakt im Bestand: Nur der Vermerk, warum. „Erneut versuchen“ prüft es noch einmal.
        self.db.execute("UPDATE mail_intake_items SET status=?,attempts=attempts+1,grund=NULL,technik=NULL WHERE account=? AND folder=? AND generation=? AND uid=?",
                        (FILTERED+category,item['account'],item['folder'],item['generation'],item['uid']))

    def step(self, account, reader, *, batch=8, permitted=lambda:True, permission_lock=None, claims=None, screen=None, hold=None):
        """Ein begrenzter Durchgang; Bestandsaufnahme und Abrufe teilen sich eine Verbindung.

        `screen(message)` liefert eine `mail_filter.Decision`. Ausgefilterte Nachrichten werden
        nicht aufgenommen, aber gezählt (Status `filtered:<Kategorie>`) und im Status gezeigt.
        """
        if not 1<=batch<=50:raise ValueError('batch must be 1..50')
        sitzung=getattr(reader,'session',None)
        with (sitzung() if sitzung is not None else nullcontext()):
            return self._step(account,reader,batch,permitted,permission_lock,claims,screen,hold)

    def _step(self, account, reader, batch, permitted, permission_lock, claims, screen, hold):
        gate=permission_lock if permission_lock is not None else nullcontext()
        with gate:
            if not self._active(account,permitted):return []
        with self.episodes._lock:
            # Least-recently updated folder first; bounded calls even for many folders.
            rows=[dict(r) for r in self.db.execute('SELECT * FROM mail_intake_folders WHERE account=? AND paused=0 ORDER BY updated,folder LIMIT 2',(account,))]
        for row in rows:
            try:
                if row['generation'] is not None:
                    self._inventory(account,reader,row,True,permitted,gate)
                if not row['inventory_complete']:
                    self._inventory(account,reader,row,False,permitted,gate)
            except MailboxGenerationChanged:
                with self.episodes.transaction():
                    # Old sources survive; old pending work cannot be fetched under a new generation.
                    self.db.execute("UPDATE mail_intake_folders SET generation=NULL,upper_uid=0,scan_uid=0,live_uid=0,inventory_complete=0,error='generation_changed',updated=? WHERE account=? AND folder=?",(time.time(),account,row['folder']))
            except Exception:
                with self.episodes.transaction():
                    self.db.execute("UPDATE mail_intake_folders SET error='inventory_unavailable',updated=? WHERE account=? AND folder=?",(time.time(),account,row['folder']))
        with self.episodes._lock:
            # Reserve at least half for history; a single bad UID never blocks either lane.
            history_quota = 0 if self._history_backlog(account) > 200 else batch
            selected=[]
            lanes=[('live',max(1,batch//2)),('history',history_quota)]
            # Nur bei Einzelschritten wechselt die Reihenfolge; den Zähler über alle Erledigten sonst nicht bilden (O(Bestand) je Schritt).
            if batch==1 and history_quota and self.db.execute("SELECT COUNT(*) FROM mail_intake_items WHERE account=? AND status IN ('captured','duplicate')",(account,)).fetchone()[0]%2:
                lanes=[('history',1),('live',1)]
            for lane,quota in lanes:
                # Neue Post in Eingangsreihenfolge; der Verlauf von neu nach alt (höhere UID = später eingegangen):
                # Fürs Briefing zählt das Jüngste, das Alte findet der Suchindex auch später (docs/46-hintergrund.md).
                reihenfolge='i.uid' if lane=='live' else 'i.uid DESC'
                selected += [dict(r) for r in self.db.execute(f'''SELECT i.* FROM mail_intake_items i
                    JOIN mail_intake_folders f ON f.account=i.account AND f.folder=i.folder AND f.generation=i.generation
                    WHERE i.account=? AND f.paused=0 AND i.lane=? AND i.status IN ('pending','failed') AND i.retry_at<=?
                    ORDER BY i.attempts,{reihenfolge} LIMIT ?''',(account,lane,time.time(),min(quota,batch-len(selected))))]
        captured=[]; neu=0
        for item in selected:
            with gate:
                if not self._active(account,permitted):break
            beim_speichern=False
            try:
                # Für die Aufnahme mit Anhängen (PDF-Rechnungen, `anhaenge.py`), wo der Leser das kann.
                holen=getattr(reader,'message_mit_anhaengen',None) or reader.message_in_folder
                message=holen(item['folder'],f"{item['generation']}.{item['uid']}")
                with gate:
                    if not self._active(account,permitted):break
                    if message.uid!=f"{item['generation']}.{item['uid']}":raise MailError('Die gelieferte Mail passt nicht zur angefragten Kennung.')
                # Model/network calls must not hold the conversation/permission lock.
                decision=screen(message) if screen is not None else None
                with gate:
                    if not self._active(account,permitted):break
                    if decision is not None and not decision.include:
                        if hold is not None:
                            hold(replace(message,account_id=account,uid=f'{account}:{message.uid}'),decision,item['folder'])
                        with self.episodes.transaction():self._filtered(item,decision.category)
                        continue
                    provider_id=getattr(message,'provider_id','')
                    # Cross-folder identity only comes from the provider, never a foreign Message-ID header.
                    identity = 'gmail:'+provider_id if provider_id else (message.uid if item['folder'].upper()=='INBOX' else json.dumps([item['folder'],message.uid]))
                    qualified=replace(message,account_id=account,uid=f'{account}:{message.uid}')
                    beim_speichern=True
                    with self.episodes.transaction():
                        result=remember(self.episodes,qualified,claims=claims,source_identity=identity)
                        self._captured(item,result['episode']['id'],result['new'])
                    captured.append(result['episode']['id']); neu+=bool(result['new'])
                    captured.extend(result.get('anhaenge') or ())
            except Exception as fehler:
                # Nie still: Grund und technische Angabe bleiben am Eintrag (Fremdprobe 3, Befund 2), der Stand sagt sie.
                grund,technik=grund_einordnen(fehler,beim_speichern=beim_speichern)
                with self.episodes.transaction():
                    self.db.execute("UPDATE mail_intake_items SET status='failed',attempts=attempts+1,retry_at=?,grund=?,technik=? WHERE account=? AND folder=? AND generation=? AND uid=?",
                        (time.time()+min(3600,30*2**min(item['attempts'],7)),grund,technik,account,item['folder'],item['generation'],item['uid']))
        if neu:logbuch.vermerke('quellen',sorte='mail',anzahl=neu)
        return captured

    def _history_backlog(self, account):
        """Same bounded, content-free backlog check for capture and its status."""
        with self.episodes._lock:
            return self.db.execute(f"""SELECT COUNT(*) FROM (SELECT DISTINCT i.episode_id
                FROM mail_intake_items i JOIN episodes e ON e.id=i.episode_id
                LEFT JOIN working_memory_sources w ON w.episode_id=i.episode_id
                WHERE {sql_nicht_ignoriert('e')} AND i.account=? AND i.episode_id IS NOT NULL AND w.episode_id IS NULL LIMIT 201)""", (account,)).fetchone()[0]

    def _windows(self, account, row):
        """UID-Fenster von je `STATUS_WINDOW` Einträgen des Verlaufs; jedes wird unter eigener kurzer Sperre gelesen."""
        after=0
        while True:
            with self.episodes._lock:
                end=self.db.execute("""SELECT MAX(uid) FROM (SELECT uid FROM mail_intake_items WHERE account=? AND folder=? AND generation=? AND uid>?
                    ORDER BY uid LIMIT ?)""",(account,row['folder'],row['generation'],after,STATUS_WINDOW)).fetchone()[0]
            if end is None:return
            yield after,end
            after=end

    def _window_counts(self, account, row, after, end, category_diagnostics):
        """Zähler eines Fensters; Kategoriefehler lesen bei Bedarf aktuelle Originale."""
        where=(account,row['folder'],row['generation'],after,end)
        with self.episodes._lock:
            counts=self.db.execute('SELECT status,COUNT(*) FROM mail_intake_items WHERE account=? AND folder=? AND generation=? AND uid>? AND uid<=? AND lane=\'history\' GROUP BY status',where).fetchall()
            # Fingerprint-invalidated rows are pending, never complete.
            analysis=self.db.execute("""SELECT CASE WHEN e.state='ignored' THEN 'excluded'
                WHEN a.generation=e.support_generation THEN a.status ELSE 'pending' END,COUNT(DISTINCT i.episode_id)
                FROM mail_intake_items i JOIN episodes e ON e.id=i.episode_id
                LEFT JOIN mail_intake_analysis a ON a.episode_id=i.episode_id
                WHERE i.account=? AND i.folder=? AND i.generation=? AND i.uid>? AND i.uid<=? AND i.lane='history' AND i.episode_id IS NOT NULL
                GROUP BY 1""",where).fetchall()
            categories=self.db.execute("""SELECT CASE
                WHEN e.state='ignored' THEN 'excluded'
                WHEN c.support_generation=e.support_generation AND c.taxonomy_version >= v.corpus_version
                THEN c.status ELSE 'pending' END,COUNT(DISTINCT i.episode_id)
                FROM mail_intake_items i JOIN episodes e ON e.id=i.episode_id
                CROSS JOIN memory_category_scan v
                LEFT JOIN memory_category_sources c ON c.episode_id=i.episode_id
                WHERE i.account=? AND i.folder=? AND i.generation=? AND i.uid>? AND i.uid<=? AND i.lane='history' AND i.episode_id IS NOT NULL
                GROUP BY 1""",where).fetchall()
            failed_category_sources=self.db.execute("""SELECT DISTINCT i.episode_id,CASE
                WHEN e.state='ignored' THEN 'excluded'
                WHEN c.support_generation=e.support_generation AND c.taxonomy_version >= v.corpus_version
                THEN c.status ELSE 'pending' END
                FROM mail_intake_items i JOIN episodes e ON e.id=i.episode_id
                CROSS JOIN memory_category_scan v
                JOIN memory_category_sources c ON c.episode_id=i.episode_id
                WHERE i.account=? AND i.folder=? AND i.generation=? AND i.uid>? AND i.uid<=?
                  AND i.lane='history' AND c.status='failed'""",where).fetchall()
        # The source projection is authoritative: it includes the current fingerprint, targeted taxonomy
        # rechecks, dismissal, and source-head availability. A request-wide budget bounds source reads;
        # remaining persisted failures are reported as unverified, never as a current cause.
        if failed_category_sources:
            from .memory_categories import Categories, FAILURE_CODES
            projected = Categories(self.episodes)
            category_counts = Counter(dict(categories))
            category_failures = Counter()
            for episode_id, old_status in failed_category_sources:
                cached = category_diagnostics['projected'].get(episode_id)
                if cached is None and category_diagnostics['remaining'] > 0:
                    category_diagnostics['remaining'] -= 1
                    current = projected.list_for(episode_id)
                    new_status = current['status']
                    code = current.get('failure_code')
                    safe_code = code if code in FAILURE_CODES else 'unknown'
                    cached = (new_status, safe_code if new_status == 'failed' else None)
                    category_diagnostics['projected'][episode_id] = cached
                if cached is None:
                    category_counts[old_status] -= 1
                    if category_counts[old_status] <= 0:
                        category_counts.pop(old_status, None)
                    category_counts['unverified'] += 1
                    continue
                new_status, safe_code = cached
                category_counts[old_status] -= 1
                if category_counts[old_status] <= 0:
                    category_counts.pop(old_status, None)
                category_counts[new_status] += 1
                if new_status == 'failed':
                    category_failures[safe_code or 'unknown'] += 1
            categories = list(category_counts.items())
            category_failures = list(category_failures.items())
        else:
            category_failures = []
        return counts,analysis,categories,category_failures

    def _folder_status(self, account, row, category_diagnostics):
        counts,analysis,category_counts,category_failures=Counter(),Counter(),Counter(),Counter()
        for after,end in self._windows(account,row):
            for total,rows in zip((counts,analysis,category_counts,category_failures),self._window_counts(account,row,after,end,category_diagnostics)):
                for key,number in rows:total[key]+=number
        with self.episodes._lock:
            live_counts=dict(self.db.execute("SELECT status,COUNT(*) FROM mail_intake_items WHERE account=? AND folder=? AND generation=? AND lane='live' AND status IN ('pending','failed') GROUP BY status",(account,row['folder'],row['generation'])).fetchall())
            filtered_rows=self.db.execute("SELECT lane,status,COUNT(*) FROM mail_intake_items WHERE account=? AND folder=? AND generation=? AND status>=? AND status<? GROUP BY lane,status",
                (account,row['folder'],row['generation'],FILTERED,FILTERED[:-1]+';')).fetchall()
            filtered={status:number for lane,status,number in filtered_rows if lane=='history'}
            live_filtered={status:number for lane,status,number in filtered_rows if lane=='live'}
            # Gescheiterte beider Wege (Verlauf und neue Post) je Grund, dazu die jüngste technische Angabe.
            gescheitert=dict(self.db.execute("SELECT COALESCE(grund,'unbekannt'),COUNT(*) FROM mail_intake_items WHERE account=? AND folder=? AND generation=? AND status='failed' GROUP BY 1",
                (account,row['folder'],row['generation'])).fetchall())
            technik=self.db.execute("SELECT technik FROM mail_intake_items WHERE account=? AND folder=? AND generation=? AND status='failed' AND technik IS NOT NULL ORDER BY retry_at DESC LIMIT 1",
                (account,row['folder'],row['generation'])).fetchone()
        return dict(folder=row['folder'],inventory_complete=bool(row['inventory_complete']),total=sum(counts.values()),
            filtered=sum(filtered.values()),filtered_by={k[len(FILTERED):]:v for k,v in filtered.items()},
            captured=counts['captured'],duplicates=counts['duplicate'],failed=counts['failed'],pending=counts['pending'],
            live_pending=sum(live_counts.values()),live_failed=live_counts.get('failed',0),
            live_filtered=sum(live_filtered.values()),live_filtered_by={k[len(FILTERED):]:v for k,v in live_filtered.items()},
            failed_by=gescheitert,failed_technik=technik[0] if technik else None,
            analyzed=analysis['complete'],deferred=analysis['deferred'],excluded=analysis['dismissed']+analysis['excluded'],analysis_failed=analysis['failed'],categorized=category_counts['complete'],
            categories_pending=category_counts['pending'],categories_failed=category_counts['failed'],
            categories_deferred=category_counts['deferred'],categories_failed_by=dict(category_failures),
            categories_unverified=category_counts['unverified'])

    def status(self, account):
        """Zähler je Ordner. Liest in kleinen Fenstern statt in einem Zug unter der Episodensperre.

        Früher hielt eine einzige Sperre alle Verbund-Abfragen über den ganzen Bestand (bei 50 000
        Mails rund eine Sekunde); jede Antwort im Gespräch und jede Aufnahme wartete solange. Jetzt
        gilt die Sperre nur je Fenster (`STATUS_WINDOW` Einträge, wenige Millisekunden). Die Summe ist
        deshalb kein atomarer Schnappschuss: Läuft die Aufnahme zwischen zwei Fenstern weiter, kann ein
        Eintrag im Nachbarfenster schon den neuen Stand haben. Für eine Fortschrittsanzeige genügt das,
        die nächste Abfrage stimmt wieder; Zähler im Schema vorzuhalten wäre eine Migration für dieselbe Anzeige.
        """
        with self.episodes._lock:
            rows=[dict(r) for r in self.db.execute('SELECT * FROM mail_intake_folders WHERE account=? ORDER BY folder',(account,))]
        category_diagnostics={'remaining':CATEGORY_DIAGNOSTIC_BUDGET,'projected':{}}
        folders=[self._folder_status(account,row,category_diagnostics) for row in rows]
        error=next((r['error'] for r in rows if r['error']),None)
        paused=bool(rows) and all(r['paused'] for r in rows)
        history_waiting=any(f['pending'] or f['failed'] for f in folders) and self._history_backlog(account)>200
        step='paused' if paused else 'inventory' if any(not f['inventory_complete'] for f in folders) else 'waiting_analysis' if history_waiting else 'capture' if any(f['pending'] or f['live_pending'] for f in folders) else 'analysis'
        # Wann das Einlesen zuletzt im Postfach war (für „abgerufen um 14:43“, mail_stand.py).
        aktualisiert=max((r['updated'] for r in rows if r.get('updated')),default=None)
        return dict(account_id=account,started=bool(rows),paused=paused,folders=folders,step=step,error=error,
                    scope=', '.join(r['folder'] for r in rows),aktualisiert=aktualisiert,history_waiting_for_analysis=history_waiting)
