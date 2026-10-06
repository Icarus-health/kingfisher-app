"""Explicit review over the existing mail reader and evidence store."""
from copy import deepcopy
from dataclasses import replace
from typing import Literal
import json
from fastapi import HTTPException
from pydantic import BaseModel, Field
from . import config, mail_filter, mail_ingestion


class PolicyIn(BaseModel):
    ai_enabled: bool = False
    block_newsletters: bool = True
    allowed: list[str] = Field(default_factory=list,max_length=100)
    blocked: list[str] = Field(default_factory=list,max_length=100)


class ReviewIn(BaseModel):
    action: Literal['include','exclude']


def register_mail_filter_routes(app,guard,data_dir):
    def save(value):
        previous=app.state.settings.mail_filter
        app.state.settings.mail_filter=value
        try:config.save(data_dir(),app.state.settings)
        except Exception:
            app.state.settings.mail_filter=previous
            raise
    def public():
        return {**mail_filter.policy(app.state.settings),'overflow':app.state.settings.mail_filter.get('overflow',0),'pending':[
            {k:v for k,v in entry.items() if k!='digest'}
            for entry in app.state.settings.mail_filter.get('pending',{}).values()]}
    def entry(identity):
        item=app.state.settings.mail_filter.get('pending',{}).get(identity)
        if not item:raise HTTPException(404,'Diese Nachricht wurde bereits geprüft.')
        return deepcopy(item)
    def read(item):
        try:
            reader=app.state.mail.reader_for(item['account_id'])
            message=(reader.message_in_folder(item['folder'],item['uid']) if 'folder' in item
                     else reader.message(item['uid']))
            if message.uid!=item['uid'] or mail_filter.digest(message)!=item['digest']:
                raise ValueError('changed')
            return reader,message
        except Exception as exc:
            raise HTTPException(409,'Die ursprüngliche Mail ist nicht unverändert erreichbar. Bitte im Postfach prüfen.') from exc

    @app.get('/api/v1/mail-filter',dependencies=guard)
    def get_policy():
        with app.state.conversation_lock:return public()

    @app.put('/api/v1/mail-filter',dependencies=guard)
    def set_policy(body:PolicyIn):
        try:allowed,blocked=mail_filter.rules(body.allowed),mail_filter.rules(body.blocked)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        with app.state.conversation_lock:
            value=deepcopy(app.state.settings.mail_filter)
            value.update(ai_enabled=body.ai_enabled,block_newsletters=body.block_newsletters,
                allowed=allowed,blocked=blocked,revision=value.get('revision',0)+1)
            save(value)
            return public()

    @app.get('/api/v1/mail-filter/review/{identity}',dependencies=guard)
    def show(identity:str):
        with app.state.conversation_lock:item=entry(identity)
        _,message=read(item)
        return {'subject':message.subject,'sender':message.sender,'body':message.body or message.preview,'truncated':message.truncated}

    @app.post('/api/v1/mail-filter/review/{identity}',dependencies=guard)
    def review(identity:str,body:ReviewIn):
        with app.state.conversation_lock:item=entry(identity)
        reader,message=read(item) if body.action=='include' else (None,None)
        with app.state.conversation_lock:
            if entry(identity)!=item:raise HTTPException(409,'Der Prüfstand hat sich geändert.')
            if body.action=='include':
                try:current=app.state.mail.reader_for(item['account_id'])
                except Exception as exc:raise HTTPException(409,'Mailkonto nicht mehr verfügbar.') from exc
                if current is not reader:raise HTTPException(409,'Mailkonto wurde geändert.')
                provider_id=getattr(message,'provider_id','')
                folder=item.get('folder','INBOX')
                source_identity=('gmail:'+provider_id if provider_id else
                          (message.uid if folder.upper()=='INBOX' else json.dumps([folder,message.uid])))
                with app.state.episodes.transaction():
                    result=mail_ingestion.remember(app.state.episodes,replace(message,account_id=item['account_id'],
                        uid=item['account_id']+':'+item['uid']),claims=app.state.claims,source_identity=source_identity)
                    # Keep progress consistent after explicit review; only the exact filtered item changes.
                    generation,separator,uid=item['uid'].rpartition('.')
                    if separator and uid.isdecimal():
                        app.state.episodes._conn.execute("""UPDATE mail_intake_items SET status=?,episode_id=?,grund=NULL,technik=NULL
                            WHERE account=? AND folder=? AND generation=? AND uid=? AND status LIKE 'filtered:%'""",
                            ('captured' if result['new'] else 'duplicate',result['episode']['id'],
                             item['account_id'],folder,generation,int(uid)))
            value=deepcopy(app.state.settings.mail_filter)
            del value['pending'][identity]
            save(value)
            return public()
