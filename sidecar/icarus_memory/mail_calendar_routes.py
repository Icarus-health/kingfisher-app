"""Local, durable mail preparations and guarded handoff to calendar previews."""
from contextlib import contextmanager
import hashlib
import json
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .calendar_actions import ActionError, _times
from .mail_thread import thread_context

MAIL_FIELDS=('uid','account_id','message_id','provider_id','sender','reply_to','date','subject',
             'body','preview','truncated','in_reply_to','references','recipients','own_addresses')

def source_binding(message, context):
    material={'mail':{name:getattr(message,name,None) for name in MAIL_FIELDS},'context':context}
    return hashlib.sha256(json.dumps(material,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()

class OpenIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    source_binding:str=Field(pattern='^[0-9a-f]{64}$')

class UpdateIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    stand:str=Field(pattern='^[0-9a-f]{64}$')
    fields:dict[str,str]
    reviewed:bool

class PreviewIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    stand:str=Field(pattern='^[0-9a-f]{64}$')
    source_id:str=Field(min_length=1,max_length=128)
    send_updates:str

def install_routes(app,guard,read_mail,mail_reader):
    from .mail_calendar_preparations import MailCalendarPreparations
    actions=app.state.calendar_actions
    store=MailCalendarPreparations(actions.path)
    app.state.mail_calendar_preparations=store

    @contextmanager
    def snapshot(uid,expected=None):
        # Network mail read before the shared source lock; validate identity and
        # all stored source generations under it. No calendar/model invocation.
        reader=mail_reader();episodes=app.state.episodes;message=read_mail(uid)
        with app.state.conversation_lock:
            if app.state.mail is not reader or app.state.episodes is not episodes or message.uid!=uid:
                raise ActionError('Die Mailquelle hat sich geändert. Bitte erneut öffnen.',409)
            context=thread_context(episodes,message)
            binding=source_binding(message,context)
            if context['status']!='ready' or (expected is not None and binding!=expected):
                raise ActionError('Mail oder bekannter Verlauf haben sich geändert. Bitte neu öffnen und prüfen.',409)
            yield message,context,binding

    @contextmanager
    def checked_record(preparation_id,stand=None):
        record=store.get(preparation_id)
        with snapshot(record['uid'],record['binding']):
            # Fetch again after the mail read and lock to catch intervening edits.
            latest=store.get(preparation_id)
            if latest['binding']!=record['binding'] or (stand is not None and latest['stand']!=stand):
                raise ActionError('Der Terminentwurf wurde inzwischen geändert. Bitte erneut öffnen.',409)
            yield latest

    @contextmanager
    def execution_guard(binding):
        try:
            with checked_record(binding['id'],binding['stand']) as record:
                if not record['reviewed']:
                    raise ActionError('Bitte die Angaben zuerst ausdrücklich prüfen.',409)
                yield
        except HTTPException:
            # No provider write has started when the mail read fails. Do not
            # mislabel an unavailable source as an uncertain calendar outcome.
            raise ActionError('Die Originalmail kann nicht mehr geprüft werden. Bitte Konto und Quelle erneut öffnen.',409) from None
    actions.source_guard=execution_guard

    def public_error(exc):return HTTPException(exc.status,str(exc))

    @app.post('/api/v1/messages/{uid}/calendar-preparation',dependencies=guard,status_code=201)
    def open_preparation(uid:str,body:OpenIn):
        try:
            with snapshot(uid,body.source_binding) as (message,context,binding):
                return store.prepare(uid,binding,context,message.subject)
        except ActionError as exc:raise public_error(exc) from None

    @app.get('/api/v1/mail-calendar-preparations/{preparation_id}',dependencies=guard)
    def get_preparation(preparation_id:str):
        try:
            with checked_record(preparation_id) as record:return record
        except ActionError as exc:raise public_error(exc) from None

    @app.put('/api/v1/mail-calendar-preparations/{preparation_id}',dependencies=guard)
    def update_preparation(preparation_id:str,body:UpdateIn):
        try:
            with checked_record(preparation_id,body.stand):
                return store.update(preparation_id,body.stand,body.fields,body.reviewed)
        except ActionError as exc:raise public_error(exc) from None

    @app.post('/api/v1/mail-calendar-preparations/{preparation_id}/preview',dependencies=guard,status_code=201)
    def preview(preparation_id:str,body:PreviewIn):
        try:
            with checked_record(preparation_id,body.stand) as record:
                if not record['reviewed']:
                    raise ActionError('Bitte Original, bekannten Verlauf und Terminangaben zuerst prüfen.')
                fields=record['fields'];_times(fields['title'],fields['start'],fields['end'])
                return actions.draft(kind='create',source_id=body.source_id,
                    title=fields['title'],start=fields['start'],end=fields['end'],send_updates=body.send_updates,
                    mail_preparation={'id':record['id'],'stand':record['stand']})
        except ActionError as exc:raise public_error(exc) from None
