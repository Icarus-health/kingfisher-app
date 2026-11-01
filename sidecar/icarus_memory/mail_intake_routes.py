"""Authenticated intake controls; connecting an account alone never starts content capture."""
from fastapi import HTTPException, Query
from pydantic import BaseModel, Field
from .mail_intake import Intake
from . import config
from .model_roles import hintergrund_anbieter
from . import hintergrund_cloud
from .connectors.mail import MailError, ist_gesendet_ordner
from .mail_anmeldung import einordnen
from .zeitgrenze import mit_zeitgrenze

#: So lange wartet „Mails einlesen“ höchstens auf die Mailbereiche des Postfachs (Sekunden, Wanduhr).
ZEITGRENZE=15.0


def attachment_support(reader):
    """Reader capability, never a claim that existing mail has been fully read."""
    from .anhaenge import MAX_ANHAENGE, MAX_BYTES, MAX_SEITEN, MAX_ZEICHEN
    supported = callable(getattr(reader, 'message_mit_anhaengen', None))
    description = (f'PDFs und Dokumentbilder werden mitgelesen: höchstens {MAX_ANHAENGE} Anlagen je Mail, '
                   f'{MAX_SEITEN} Seiten, {MAX_BYTES // (1024 * 1024)} MiB und {MAX_ZEICHEN:,} Zeichen je Anlage. '
                   'Scans brauchen lokale Texterkennung; ungelesene Inhalte und Grenzen stehen an der Originalquelle.'
                   if supported else 'Dieser Mailzugang liest bisher den Mailtext, keine Anlagen. Inhalte aus Anlagen können im Gedächtnis fehlen.')
    return {'attachments_supported': supported, 'attachments_description': description}

#: Was gelesen wird, in Alltagssprache; `umfang_beschreibung` wählt nach den Ordnern.
UMFANG_GESAMT='Posteingang, Gesendet und Archiv über den Gmail-Gesamtbestand; ohne Spam und Papierkorb.'
UMFANG_MIT_GESENDET='Posteingang und Gesendet; ohne Spam und Papierkorb.'
UMFANG_NUR_POSTEINGANG='Nur der Posteingang; gesendete und archivierte Mails sind bei diesem Konto nicht dabei.'
#: Antworten von „Gesendete Mails auch einlesen“ (`POST …/ordner-ergaenzen`).
GESENDET_NEU='Gesendete Mails werden jetzt mit eingelesen.'
GESENDET_SCHON='Gesendete Mails sind schon dabei.'
GESENDET_KEINER='Dieses Postfach hat keinen Gesendet-Ordner, den Kingfisher erkennt.'


def gesendet_dabei(folders):
    """Ob gesendete Mails in diesen Ordnern enthalten sind: ein Gesendet-Ordner oder ein Gesamtbestand (Gmail)."""
    return any(f.upper()!='INBOX' for f in folders)


def umfang_beschreibung(folders, reader=None):
    """Drei Fälle in Alltagssprache: Gesamtbestand, „Posteingang und Gesendet“, „Nur der Posteingang“.

    Ein Leser, der seinen Umfang selbst kennt (Microsoft 365: Posteingang und Gesendet), sagt ihn selbst.
    """
    umfang=getattr(reader,'umfang',None)
    if isinstance(umfang,str) and umfang:return umfang
    namen=[f for f in folders if isinstance(f,str)]
    if any(f.upper()!='INBOX' and not ist_gesendet_ordner(f) for f in namen):return UMFANG_GESAMT
    if any(ist_gesendet_ordner(f) for f in namen):return UMFANG_MIT_GESENDET
    return UMFANG_NUR_POSTEINGANG


class StartIn(BaseModel):
    folders: list[str]

class PauseIn(BaseModel):
    paused: bool

class CorrectionIn(BaseModel):
    categories: list[str]
    expected_revision: str | None = Field(default=None, min_length=64, max_length=64,
                                         pattern=r'^[0-9a-f]{64}$')

class CategoryIn(BaseModel):
    id: str
    label: str
    description: str = ''


def register(app, guard, data_dir, wire):
    from .storage_capacity import reason as storage_reason, MESSAGES as STORAGE_MESSAGES

    def require_capacity():
        blocked = storage_reason(data_dir())
        if blocked is not None:
            raise HTTPException(507, STORAGE_MESSAGES[blocked])

    def account(account_id):
        entry=next((e for e in app.state.settings.mail_accounts if e.id==account_id and e.configured),None)
        if entry is None:raise HTTPException(404,'Mailkonto ist nicht verbunden.')
        return entry

    def erkannt():
        """Je Konto, ob die letzte Ordnersuche einen Gesendet-Ordner fand (nur für diesen Lauf, nicht gespeichert)."""
        if getattr(app.state,'gesendet_erkannt',None) is None:app.state.gesendet_erkannt={}
        return app.state.gesendet_erkannt

    def status():
        store=Intake(app.state.episodes)
        result=[]
        for entry in app.state.settings.mail_accounts:
            state=store.status(entry.id)
            state.update(label=entry.label,connected=entry.configured)
            try:
                reader = app.state.mail.reader_for(entry.id) if entry.configured else None
            except Exception:
                reader = None
            state.update(attachment_support(reader))
            # Was gelesen wird, und ob Gesendet dabei ist (dann kein Knopf „Gesendete Mails auch einlesen“).
            # `gesendet_erkennbar`: das Ergebnis der letzten Ordnersuche dieses Laufs (None: noch nicht nachgesehen).
            ordner=[f['folder'] for f in state['folders']]
            state.update(umfang=umfang_beschreibung(ordner,reader) if state['started'] else None,
                         gesendet_dabei=gesendet_dabei(ordner) if state['started'] else False,
                         gesendet_erkennbar=erkannt().get(entry.id))
            # Fortschritt des Empfängernachtrags für ältere Mails; fehlt, solange er nicht begonnen hat.
            lauf=getattr(app.state,'nachtrag',None)
            state['empfaengernachtrag']=lauf.status(entry.id) if lauf is not None and state['started'] else None
            if state['started'] and (not app.state.settings.schedule.enabled or entry.id not in app.state.settings.schedule.mail_accounts):
                state.update(paused=True,step='paused')
            result.append(state)
        # Die eine Aussage je Postfach (Fremdprobe 2, Befund 17): dieselbe wie unter „Für Techniker“.
        from .mail_stand import stand as mail_stand
        saetze={eintrag['account_id']:eintrag for eintrag in mail_stand(app,intake_status={s['account_id']:s for s in result})}
        for state in result:
            eintrag=saetze.get(state['account_id'])
            state['stand']={k:eintrag.get(k) for k in ('zustand','satz','gelesen','gesamt','zuletzt','technik','verweis')} if eintrag else None
        provider=hintergrund_anbieter(app)
        plan=app.state.settings.schedule
        from .model_roles import rollen_von
        storage_blocked = storage_reason(data_dir())
        return {'accounts':result,'attachments_supported':any(s['attachments_supported'] for s in result),
                'storage_blocked':storage_blocked,
                'storage_message':STORAGE_MESSAGES.get(storage_blocked),
                # Separate from each mailbox's pause: its resume route cannot
                # release the explicit global background pause.
                'background_paused':bool(getattr(getattr(app.state,'hintergrund',None),'pausiert',False)),
                # Lokal, oder die Cloud-Einordnung neuer Mails mit eigener Einwilligung (`hintergrund_cloud`).
                'analysis_active':bool(plan.enabled and getattr(plan,'with_model',False)
                                       and (getattr(provider,'is_local',False) or hintergrund_cloud.aktiv(app))),
                # Getrennt gemeldet: Das gewählte Modell läuft in Ollamas Cloud und wird deshalb nicht genutzt.
                'analysis_blocked':'cloud_ueber_ollama' if rollen_von(app).cloud_modell_im_weg('hintergrund') else None}

    @app.get('/api/v1/mail/intake',dependencies=guard)
    def get_status():return status()

    @app.get('/api/v1/mail/stand',dependencies=guard)
    def get_mail_stand():
        """Je Postfach eine Aussage in einem Satz: liest, leer, gelesen, angehalten, noch nicht abgerufen oder Fehler."""
        from .mail_stand import stand as mail_stand
        return {'accounts':mail_stand(app)}

    def discover(account_id):
        entry=account(account_id)
        reader=app.state.mail.reader_for(account_id)
        try:
            # Mit Wanduhr: Die Netzzeitgrenze von imaplib fängt keine hängende Namensauflösung, und ohne Antwort
            # stand der Knopf minutenlang auf „Wird gestartet …“ (Fremdprobe, Befund 4).
            available=mit_zeitgrenze(reader.folders,ZEITGRENZE)
        except Exception as exc:
            ursache=exc.__cause__ if isinstance(exc,MailError) and exc.__cause__ is not None else exc
            fehler=einordnen(ursache,getattr(entry,'imap_host',''),getattr(entry,'label',''))
            raise HTTPException(503,fehler.satz) from None
        historical=[f['name'] for f in available if f.get('historical')]
        if not historical:
            raise HTTPException(503,'Im Postfach fehlt der Posteingang; bitte beim Anbieter nachsehen und erneut versuchen.')
        # Gemerkt für den Stand: Gibt es einen Gesendet-Ordner, den Kingfisher erkennt (am Attribut oder am Namen)?
        erkannt()[account_id]=any(f.get('historical') and (f.get('gesendet') or ist_gesendet_ordner(f['name'],f.get('attributes') or ()))
                                 for f in available)
        return reader,historical

    @app.get('/api/v1/mail/erreichbar',dependencies=guard)
    def erreichbar():
        """Antwortet jedes verbundene Postfach gerade? Je Konto eine Anmeldung mit Zeitgrenze, ohne etwas zu lesen.

        Für die Fertig-Seite der Einrichtung und den Mail-Schritt (Fremdprobe, Befund 5): „Dein Briefing ist bereit“
        darf dort nicht stehen, wenn das Postfach nie geantwortet hat. Die Konten werden nebeneinander geprüft, damit
        zwei schweigende Postfächer nicht doppelt so lange dauern.
        """
        from concurrent.futures import ThreadPoolExecutor
        from . import mail_anmeldung
        sammlung=getattr(app.state,'mail',None)
        konten=[]
        for entry in app.state.settings.mail_accounts:
            if not (entry.configured and getattr(entry,'enabled',True)):continue
            try:reader=sammlung.reader_for(entry.id) if sammlung is not None else None
            except Exception:reader=None  # noqa: BLE001 - ohne Zugangsdaten nicht verbunden, also nicht zu prüfen
            if reader is not None:konten.append((entry,reader))

        def pruefen(paar):
            entry,reader=paar
            try:
                mail_anmeldung.pruefe(reader,entry.imap_host,name=entry.label)
            except mail_anmeldung.Anmeldefehler as exc:
                return {'account_id':entry.id,'label':entry.label,'erreichbar':False,'grund':exc.grund,'satz':exc.satz}
            return {'account_id':entry.id,'label':entry.label,'erreichbar':True,'grund':None,'satz':None}
        if not konten:return {'accounts':[]}
        with ThreadPoolExecutor(max_workers=min(4,len(konten))) as pool:
            return {'accounts':list(pool.map(pruefen,konten))}

    @app.get('/api/v1/mail/intake/{account_id}/preview',dependencies=guard)
    def preview(account_id:str):
        reader,folders=discover(account_id)
        return {'folders':folders,**attachment_support(reader),'description':umfang_beschreibung(folders,reader)}

    @app.post('/api/v1/mail/intake/{account_id}/start',dependencies=guard)
    def start(account_id:str,body:StartIn):
        account(account_id)
        require_capacity()
        reader,historical=discover(account_id)
        if body.folders!=historical:
            raise HTTPException(409,'Die Mailbereiche haben sich geändert. Bitte Umfang erneut prüfen.')
        with app.state.conversation_lock:
            account(account_id)
            require_capacity()
            if app.state.mail.reader_for(account_id) is not reader:raise HTTPException(409,'Kontoverbindung wurde geändert.')
            # All Mail already includes inbox and sent for Gmail: one queue avoids label duplicates.
            store=Intake(app.state.episodes)
            old_state=store.status(account_id)
            store.start(account_id,historical)
            store.pause(account_id,True)
            plan=app.state.settings.schedule
            old_accounts=list(plan.mail_accounts);old_enabled=plan.enabled;old_local=getattr(plan,'local_model_only',False)
            try:
                if account_id not in plan.mail_accounts:plan.mail_accounts.append(account_id)
                plan.enabled=True
                plan.local_model_only=True
                config.save(data_dir(),app.state.settings)
            except Exception:
                plan.mail_accounts=old_accounts;plan.enabled=old_enabled;plan.local_model_only=old_local
                store.pause(account_id,old_state['paused'] if old_state['started'] else True)
                raise HTTPException(503,'Aufnahme konnte nicht aktiviert werden.') from None
            store.pause(account_id,False)
            wire(app)
        return status()

    @app.post('/api/v1/mail/intake/{account_id}/pause',dependencies=guard)
    def pause(account_id:str,body:PauseIn):
        account(account_id)
        with app.state.conversation_lock:
            store=Intake(app.state.episodes)
            previous=store.status(account_id)
            if not previous['started']:
                raise HTTPException(409,'Bitte zuerst den Mailumfang prüfen und die Aufnahme starten.')
            if body.paused:
                store.pause(account_id,True)
            else:
                require_capacity()
                plan=app.state.settings.schedule
                old_accounts=list(plan.mail_accounts);old_enabled=plan.enabled;old_local=getattr(plan,'local_model_only',False)
                try:
                    if account_id not in plan.mail_accounts:plan.mail_accounts.append(account_id)
                    plan.enabled=True
                    plan.local_model_only=True
                    config.save(data_dir(),app.state.settings)
                except Exception:
                    plan.mail_accounts=old_accounts;plan.enabled=old_enabled;plan.local_model_only=old_local
                    raise HTTPException(503,'Aufnahme konnte nicht fortgesetzt werden.') from None
                store.pause(account_id,False)
                wire(app)
        return status()

    @app.post('/api/v1/mail/intake/{account_id}/ordner-ergaenzen',dependencies=guard)
    def ordner_ergaenzen(account_id:str):
        """„Gesendete Mails auch einlesen“: Ordner eines laufenden Kontos nachtragen, die das Postfach heute hat.

        Für Konten von vor dem Umbau, die mit nur dem Posteingang gestartet sind. Die Ordner werden neu ermittelt
        (wie beim Vorschau-Knopf) und nur ergänzt; was läuft, läuft weiter, eine Pause bleibt. Die Antwort sagt in
        einem Satz, was passiert ist.
        """
        account(account_id)
        require_capacity()
        reader,historical=discover(account_id)
        with app.state.conversation_lock:
            account(account_id)
            require_capacity()
            if app.state.mail.reader_for(account_id) is not reader:raise HTTPException(409,'Kontoverbindung wurde geändert.')
            store=Intake(app.state.episodes)
            if not store.status(account_id)['started']:
                raise HTTPException(409,'Bitte zuerst den Mailumfang prüfen und die Aufnahme starten.')
            try:
                neu=store.ergaenzen(account_id,historical)
            except ValueError:
                raise HTTPException(409,'Bitte zuerst den Mailumfang prüfen und die Aufnahme starten.') from None
        if neu:
            satz=GESENDET_NEU
            # Gleich lesen, nicht erst beim nächsten Takt: Wer den Knopf drückt, will es jetzt sehen.
            scheduler=getattr(app.state,'scheduler',None)
            if scheduler is not None and hasattr(scheduler,'aufnahme_wecken'):scheduler.aufnahme_wecken()
        elif gesendet_dabei(historical):
            satz=GESENDET_SCHON
        else:
            satz=GESENDET_KEINER
        return {**status(),'ergaenzt':neu,'satz':satz}

    @app.post('/api/v1/mail/intake/{account_id}/retry',dependencies=guard)
    def retry(account_id:str):
        account(account_id)
        with app.state.conversation_lock:
            account(account_id)
            Intake(app.state.episodes).retry(account_id)
        # Gleich wieder versuchen, nicht erst beim nächsten Takt: Wer den Knopf drückt, will es jetzt wissen.
        scheduler=getattr(app.state,'scheduler',None)
        if scheduler is not None and hasattr(scheduler,'aufnahme_wecken'):scheduler.aufnahme_wecken()
        return status()

    @app.get('/api/v1/memory/categories',dependencies=guard)
    def taxonomy():
        from .memory_categories import Categories
        return Categories(app.state.episodes).taxonomy()

    @app.get('/api/v1/memory/areas',dependencies=guard)
    def memory_areas(limit: int = Query(default=50, ge=1, le=100),
                     cursor: int | None = Query(default=None, ge=1),
                     area: str | None = Query(default=None, max_length=40)):
        from .memory_areas import MemoryAreas
        try:
            return MemoryAreas(app.state.episodes).page(limit=limit, cursor=cursor, area=area)
        except ValueError:
            raise HTTPException(422, 'Die Quellenansicht ist ungültig.') from None

    @app.get('/api/v1/memory/people/mentions',dependencies=guard)
    def person_mentions(limit: int = Query(default=100, ge=1, le=200)):
        from .memory_categories import Categories
        return Categories(app.state.episodes).person_mentions(limit)

    @app.post('/api/v1/memory/categories',dependencies=guard)
    def add_category(body:CategoryIn):
        from .memory_categories import Categories
        try:return Categories(app.state.episodes).add_category(body.id,body.label,body.description)
        except ValueError:raise HTTPException(422,'Kategorie ist ungültig oder bereits vorhanden.') from None

    @app.get('/api/v1/episodes/{episode_id}/categories',dependencies=guard)
    def categories(episode_id:str):
        from .memory_categories import Categories
        return Categories(app.state.episodes).list_for(episode_id)

    @app.put('/api/v1/episodes/{episode_id}/categories',dependencies=guard)
    def correct(episode_id:str,body:CorrectionIn):
        from .memory_categories import Categories, CategoryCorrectionConflict
        try:
            with app.state.conversation_lock:
                store=Categories(app.state.episodes)
                store.correct(episode_id,body.categories,expected_revision=body.expected_revision)
                return store.list_for(episode_id)
        except CategoryCorrectionConflict:
            raise HTTPException(409,'Quelle, Bereiche oder deine Zuordnung haben sich geändert. Bitte den aktuellen Stand prüfen.') from None
        except (ValueError,KeyError):raise HTTPException(422,'Quelle oder Kategorien sind nicht verfügbar.') from None
