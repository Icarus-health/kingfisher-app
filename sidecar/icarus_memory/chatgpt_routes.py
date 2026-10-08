"""Authenticated connection controls; the OAuth callback accepts one-use state."""
from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from .chatgpt_oauth import ChatGPTOAuth, ChatGPTError


class Begin(BaseModel):
    model_config = ConfigDict(extra='forbid')
    origin: str = Field(max_length=100)
    consent: bool = False
    account_id: str | None = Field(default=None,max_length=64)


def register(app, guard, data_dir):
    from .secrets import Keychain
    oauth = ChatGPTOAuth(getattr(app.state,'keychain',None) or Keychain(data_dir=data_dir()))
    app.state.chatgpt_oauth = oauth

    def safe(call):
        try:
            return call()
        except ChatGPTError as exc:
            raise HTTPException(409,str(exc)) from None
        except Exception:
            raise HTTPException(409,'Der ChatGPT-Zugang konnte nicht sicher geändert werden. Bitte erneut versuchen.') from None

    @app.get('/api/v1/chatgpt',dependencies=guard)
    def status():
        return safe(oauth.status)

    @app.post('/api/v1/chatgpt/begin',dependencies=guard)
    def begin(body:Begin,request:Request):
        if not body.consent:
            raise HTTPException(422,'Bitte die Übertragung an OpenAI ausdrücklich erlauben.')
        if body.origin != f'http://{request.headers.get("host","")}':
            raise HTTPException(422,'Bitte die Anmeldung aus der lokalen Kingfisher-App starten.')
        return safe(lambda:oauth.begin(body.origin,body.account_id))

    @app.get('/api/v1/chatgpt/callback')
    def callback(request:Request):
        query = request.query_params
        request.scope['query_string'] = b''
        try:
            oauth.callback(query.get('state',''),query.get('code'),query.get('error'),query.get('client_id'))
            message,code = 'Anmeldung abgeschlossen. Du kannst dieses Fenster schließen und zu Kingfisher zurückkehren. Die Mailverarbeitung startet erst nach deiner gesonderten Freigabe.',200
        except Exception:
            message,code = 'Die Anmeldung wurde nicht abgeschlossen oder ist abgelaufen. Bitte in Kingfisher erneut beginnen.',400
        return HTMLResponse('<!doctype html><html lang="de"><meta charset="utf-8"><title>Kingfisher</title><h1>Kingfisher</h1><p>'+message+'</p></html>',
            status_code=code,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer',
                                     'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'"})

    @app.get('/api/v1/chatgpt/sessions/{sid}',dependencies=guard)
    def session(sid:str):
        return safe(lambda:oauth.session(sid))

    @app.get('/api/v1/chatgpt/models',dependencies=guard)
    def models():
        return {'models':safe(oauth.models)}

    @app.delete('/api/v1/chatgpt',dependencies=guard)
    def disconnect():
        jobs = getattr(app.state,'cloud_memory_jobs',None)
        if jobs is not None:
            jobs.pause(revoke=True)
        return safe(oauth.disconnect)
