"""Authenticated setup/selection; one-use OAuth callback needs no browser cookie."""
import copy
import json
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import config
from .google_oauth import GoogleOAuth, GoogleError


class ClientIn(BaseModel):
    installed: dict


class BeginIn(BaseModel):
    kind: str
    origin: str = Field(max_length=100)


class SelectIn(BaseModel):
    calendar_ids: list[str] = Field(default_factory=list, max_length=100)


def install_routes(app, guard, data_dir, rebuild):
    from .secrets import Keychain
    oauth = GoogleOAuth(getattr(app.state, "keychain", None) or Keychain(data_dir=data_dir()))
    app.state.google_oauth = oauth

    @app.get('/api/v1/google/config', dependencies=guard)
    def status():
        return {'configured': oauth.configured(), 'secure_storage': oauth.keychain.available}

    @app.put('/api/v1/google/config', dependencies=guard)
    def configure(body: ClientIn):
        try:
            oauth.configure(body.model_dump())
        except (GoogleError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from None
        return status()

    @app.post('/api/v1/google/begin', dependencies=guard)
    def begin(body: BeginIn, request: Request):
        # Only the origin serving this authenticated UI may receive the callback.
        # Host is forwarded unchanged by the loopback Docker port mapping.
        expected_origin = f'http://{request.headers.get("host", "")}'
        if body.origin != expected_origin:
            raise HTTPException(422, 'Bitte die Anmeldung aus der lokalen Kingfisher-Oberfläche starten.')
        try:
            return oauth.begin(body.kind, body.origin)
        except GoogleError as exc:
            raise HTTPException(422, str(exc)) from None

    @app.get('/api/v1/google/callback')
    def callback(request: Request):
        query = request.query_params
        state, code, error = query.get('state', ''), query.get('code'), query.get('error')
        # Uvicorn access logging uses the scope at response time, not the cached
        # QueryParams. Never retain OAuth codes in the access URL.
        request.scope['query_string'] = b''
        try:
            oauth.callback(state, code, error)
            message = 'Anmeldung erhalten. Kehre zu Kingfisher zurück und bestätige dort das Konto beziehungsweise die Kalenderauswahl.'
            status_code = 200
        except GoogleError:
            message = 'Anmeldung nicht abgeschlossen oder abgelaufen. Bitte in Kingfisher erneut beginnen.'
            status_code = 400
        return HTMLResponse('<!doctype html><html lang="de"><meta charset="utf-8"><title>Kingfisher</title><h1>Kingfisher</h1><p>' + message + '</p></html>',
            status_code=status_code, headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer',
                'Content-Security-Policy': "default-src 'none'; frame-ancestors 'none'"})

    @app.get('/api/v1/google/sessions/{sid}', dependencies=guard)
    def session(sid: str):
        return oauth.status(sid)

    @app.post('/api/v1/google/sessions/{sid}/connect', dependencies=guard)
    def connect(sid: str, body: SelectIn):
        with app.state.conversation_lock, oauth.lock:
            try:
                item, selected = oauth.consume(sid, body.calendar_ids)
            except GoogleError as exc:
                raise HTTPException(422, str(exc)) from None
            settings = app.state.settings
            original = copy.deepcopy(settings)
            created = []
            try:
                if item['kind'] == 'mail':
                    if any(m.user.casefold() == item['email'].casefold() for m in settings.mail_accounts):
                        raise HTTPException(409, 'Dieses Mailkonto ist bereits eingerichtet. Entferne den alten Zugang vor einer neuen Verbindung.')
                    entry = config.MailAccountSettings(id='mail-' + uuid.uuid4().hex,
                        label=item['email'], user=item['email'], sender=item['email'],
                        imap_host='imap.gmail.com', smtp_host='smtp.gmail.com', auth_method='google_oauth')
                    key = config.integration_secret_name('mail', entry.id)
                    created.append(key)
                    oauth.keychain.set(key, json.dumps(item['grant']))
                    settings.mail_accounts.append(entry)
                else:
                    for calendar_id, name in selected:
                        if any(c.kind == 'google' and c.user == item['email'] and c.url == calendar_id for c in settings.calendar_sources):
                            raise HTTPException(409, 'Ein ausgewählter Kalender ist bereits eingerichtet. Entferne den alten Zugang vor einer neuen Verbindung.')
                        entry = config.CalendarSourceSettings(id='calendar-' + uuid.uuid4().hex,
                            label=name, kind='google', user=item['email'], url=calendar_id)
                        key = config.integration_secret_name('calendar', entry.id)
                        created.append(key)
                        oauth.keychain.set(key, json.dumps(item['grant']))
                        settings.calendar_sources.append(entry)
                config.save(data_dir(), settings)
            except Exception:
                app.state.settings = original
                for key in created:
                    oauth.keychain.delete(key)
                raise
            item.pop('grant', None)
            item['status'] = 'connected'
            rebuild()
            return {'connected': True, 'kind': item['kind']}
