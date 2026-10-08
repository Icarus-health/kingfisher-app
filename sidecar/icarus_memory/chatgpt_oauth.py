"""Optional ChatGPT plan usage through the documented public OAuth flow.

Credentials live only in the protected Keychain; signing in never processes a
source. Each renewed authorization invalidates previously created providers.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import secrets
import threading
import time
import uuid
from urllib.parse import urlencode, urlparse

import httpx
import jwt

from .providers import ProviderError

ISSUER = 'https://auth.openai.com'
AUTH_URL = ISSUER + '/api/accounts/authorize'
TOKEN_URL = ISSUER + '/api/accounts/oauth/token'
JWKS_URL = ISSUER + '/.well-known/jwks.json'
DISCOVERY_URL = ISSUER + '/.well-known/openid-configuration'
API_URL = 'https://api.openai.com/v1'
KEY = 'ICARUS_CHATGPT_CONNECTIONS'
SCOPES = {'openid', 'profile', 'email', 'offline_access', 'resource.invoke', 'chatgpt.tokens.use.direct'}
TTL = 600


class ChatGPTError(ProviderError):
    pass


def request_json(method, url, **kwargs):
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.netloc not in {'auth.openai.com', 'api.openai.com'}:
        raise ChatGPTError('Ungültiger OpenAI-Endpunkt.')
    try:
        with httpx.Client(timeout=25, trust_env=False, follow_redirects=False) as client:
            with client.stream(method, url, **kwargs) as response:
                response.raise_for_status()
                body = bytearray()
                for part in response.iter_bytes():
                    body.extend(part)
                    if len(body) > 2_000_000:
                        raise ChatGPTError('Die OpenAI-Antwort ist zu groß.')
                return json.loads(body) if body else {}
    except (httpx.HTTPError, ValueError):
        raise ChatGPTError('OpenAI konnte nicht erreicht werden. Bitte Verbindung oder Anmeldung prüfen.') from None


def redirect_uri(origin):
    try:
        parsed = urlparse(origin)
        port = parsed.port
        if (parsed.scheme == 'http' and parsed.hostname == '127.0.0.1' and port
                and not parsed.username and not parsed.password and not parsed.query
                and not parsed.fragment and parsed.path in ('', '/')):
            return f'http://127.0.0.1:{port}/api/v1/chatgpt/callback'
    except (ValueError, TypeError):
        pass
    raise ChatGPTError('Bitte die Anmeldung aus der lokalen Kingfisher-App starten.')


class ChatGPTOAuth:
    def __init__(self, keychain, request=request_json, clock=time.time):
        self.keychain, self.request, self.clock = keychain, request, clock
        self.lock = threading.RLock()
        self.refresh_lock = threading.Lock()
        self.pending, self.catalogs = {}, {}
        self._cached = None
        self._revoked = set()

    def _read(self):
        if self._cached is not None:
            return json.loads(json.dumps(self._cached))
        if not self.keychain.available:
            return {'accounts': {}, 'active': None}
        raw = self.keychain.get(KEY)
        if not raw:
            return {'accounts': {}, 'active': None}
        try:
            data = json.loads(raw)
            if type(data) is dict and type(data.get('accounts')) is dict:
                self._cached = json.loads(json.dumps(data))
                return data
        except (ValueError, TypeError):
            pass
        raise ChatGPTError('Der gespeicherte ChatGPT-Zugang ist nicht lesbar. Bitte neu einrichten.')

    def _write(self, data):
        if not self.keychain.available:
            raise ChatGPTError('Für die Anmeldung wird ein geschützter Schlüsselspeicher benötigt.')
        try:
            self.keychain.set(KEY, json.dumps(data))
            self._cached = json.loads(json.dumps(data))
        except Exception:
            raise ChatGPTError('Der ChatGPT-Zugang konnte nicht sicher gespeichert werden.') from None

    def _active(self, data):
        return data.get('accounts', {}).get(data.get('active'), {})

    def status(self):
        with self.lock:
            data = self._read()
            active = self._active(data)
            connected = bool(active.get('access_token')) and active.get('grant_id') not in self._revoked
            plan = connected and {'resource.invoke','chatgpt.tokens.use.direct'} <= set(active.get('scope','').split())
            return {'connected': connected, 'plan_usage': bool(plan), 'available': bool(plan),
                    'grant_id': active.get('grant_id') if plan else None,
                    'active_account': data.get('active'), 'secure_storage': bool(self.keychain.available),
                    'accounts': [{'id': k, 'label': v.get('label', 'ChatGPT-Konto'),
                                  'active': k == data.get('active'),
                                  'plan_usage': 'chatgpt.tokens.use.direct' in v.get('scope','').split()}
                                 for k,v in data['accounts'].items()]}

    def available(self, grant_id):
        status = self.status()
        return bool(grant_id and status['available'] and status['grant_id'] == grant_id)

    def begin(self, origin, account_id=None):
        redirect = redirect_uri(origin)
        with self.lock:
            if not self.keychain.available:
                raise ChatGPTError('Für die Anmeldung wird ein geschützter Schlüsselspeicher benötigt.')
            self.pending = {sid:p for sid,p in self.pending.items() if p['expires'] > self.clock()}
            if len(self.pending) >= 4:
                raise ChatGPTError('Bitte eine laufende Anmeldung abschließen oder zehn Minuten warten.')
            data = self._read()
            if account_id is not None and account_id not in data['accounts']:
                raise ChatGPTError('Dieses ChatGPT-Konto ist nicht gespeichert.')
            if not data.get('host_id'):
                data['host_id'] = 'urn:uuid:' + str(uuid.uuid4())
                self._write(data)
            saved = data['accounts'].get(account_id, {})
            verifier, state, nonce = secrets.token_urlsafe(48), secrets.token_urlsafe(32), secrets.token_urlsafe(32)
            challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
            sid = secrets.token_urlsafe(24)
            self.pending[sid] = {'state': state, 'nonce': nonce, 'verifier': verifier, 'redirect': redirect,
                'expires': self.clock()+TTL, 'status':'waiting', 'account_id':account_id,
                'client_id':saved.get('client_id'), 'sub':saved.get('sub')}
            params = {'client_id':saved.get('client_id') or 'dynamic_agent_client',
                      'ext_agent_host_id': data['host_id'], 'response_type':'code', 'redirect_uri':redirect,
                      'scope':' '.join(sorted(SCOPES)), 'resource':API_URL, 'state':state, 'nonce':nonce,
                      'code_challenge_method':'S256', 'code_challenge':challenge}
            if not saved:
                params['agent_name_hint'] = 'Kingfisher'
            # Optional id_token_hint is deliberately omitted: the authorization
            # URL is handed to the UI, where identity tokens do not belong.
            return {'session_id': sid, 'url':AUTH_URL+'?'+urlencode(params)}

    def _identity(self, token, client_id, nonce=None):
        try:
            if not isinstance(token, str) or not 1 <= len(token) <= 24000:
                raise ValueError()
            header = jwt.get_unverified_header(token)
            if header.get('alg') not in {'RS256','ES256'} or not isinstance(header.get('kid'), str):
                raise ValueError()
            keys = self.request('GET', JWKS_URL).get('keys', [])
            matches = [k for k in keys if k.get('kid') == header['kid'] and k.get('use','sig') == 'sig'
                       and k.get('alg', header['alg']) == header['alg']]
            if len(matches) != 1:
                raise ValueError()
            key = jwt.PyJWK.from_dict(matches[0], algorithm=header['alg']).key
            claims = jwt.decode(token, key, algorithms=[header['alg']], audience=client_id, issuer=ISSUER,
                                options={'require':['exp','iat','sub','iss','aud']})
            if not isinstance(claims['sub'], str) or not claims['sub']:
                raise ValueError()
            if isinstance(claims['aud'], list) and len(claims['aud']) > 1 and claims.get('azp') != client_id:
                raise ValueError()
            if nonce is not None and (not isinstance(claims.get('nonce'), str)
                                      or not secrets.compare_digest(claims['nonce'], nonce)):
                raise ValueError()
            return claims
        except Exception:
            raise ChatGPTError('Die Identität des ChatGPT-Kontos konnte nicht bestätigt werden.') from None

    def _tokens(self, token, *, old=None):
        if not isinstance(token, dict):
            raise ChatGPTError('Unvollständige ChatGPT-Anmeldung.')
        access = token.get('access_token')
        refresh = token.get('refresh_token') or (old or {}).get('refresh_token')
        expiry = token.get('expires_in')
        if (not isinstance(access,str) or not 1 <= len(access) <= 24000 or
                any(ord(c)<33 or ord(c)>126 for c in access) or
                not isinstance(refresh,str) or not 1 <= len(refresh) <= 24000 or
                type(expiry) is not int or not 0 < expiry <= 86400):
            raise ChatGPTError('Dauerhafte ChatGPT-Anmeldung fehlt oder ist ungültig.')
        scope = token.get('scope', (old or {}).get('scope',''))
        if not isinstance(scope,str) or len(scope)>4096:
            raise ChatGPTError('Ungültige ChatGPT-Berechtigungen.')
        return {'access_token':access,'refresh_token':refresh,'expires_at':self.clock()+expiry,'scope':scope}

    def callback(self, state, code=None, error=None, client_id=None):
        with self.lock:
            match = next(((sid,p) for sid,p in self.pending.items() if isinstance(state,str)
                and p['status']=='waiting' and p['expires']>self.clock()
                and secrets.compare_digest(p['state'],state)), None)
            if match is None:
                raise ChatGPTError('Diese Anmeldung ist abgelaufen oder bereits verwendet.')
            sid, pending = match
            pending['status'] = 'processing'
        redeemed = None
        try:
            if error or not isinstance(code,str) or not 1 <= len(code) <= 4096:
                raise ChatGPTError('Anmeldung wurde nicht abgeschlossen.')
            issued = client_id or pending['client_id']
            if (not isinstance(issued,str) or not re.fullmatch(r'oaiapp_[A-Za-z0-9_-]{1,200}',issued)
                    or (pending['client_id'] and pending['client_id'] != issued)):
                raise ChatGPTError('Die ChatGPT-Registrierung passt nicht zu dieser Anmeldung.')
            raw = self.request('POST', TOKEN_URL, data={'grant_type':'authorization_code','client_id':issued,
                'code':code,'code_verifier':pending['verifier'],'redirect_uri':pending['redirect'],'resource':API_URL})
            redeemed = {'client_id':issued, 'refresh_token':raw.get('refresh_token')}
            claims = self._identity(raw.get('id_token'), issued, pending['nonce'])
            if pending['sub'] and pending['sub'] != claims['sub']:
                raise ChatGPTError('Die Anmeldung gehört zu einem anderen ChatGPT-Konto.')
            grant = self._tokens(raw)
            with self.lock:
                if pending['expires'] <= self.clock() or pending['status'] != 'processing':
                    raise ChatGPTError('Diese Anmeldung ist abgelaufen.')
                data = self._read()
                account_id = hashlib.sha256((issued+'\0'+claims['sub']).encode()).hexdigest()[:32]
                grant.update(client_id=issued,sub=claims['sub'],id_token=raw['id_token'],
                    label=claims.get('email') if claims.get('email_verified') is True else 'ChatGPT-Konto '+account_id[:6],
                    grant_id=secrets.token_hex(24))
                data['accounts'][account_id] = grant
                data['active'] = account_id
                self._write(data)
                self.catalogs.clear()
                pending['status'] = 'ready'
            return sid
        except Exception:
            with self.lock:
                pending['status'] = 'failed'
            if redeemed:
                self._revoke(redeemed)
            raise ChatGPTError('ChatGPT-Anmeldung nicht abgeschlossen. Bitte Konto und Berechtigungen prüfen und erneut anmelden.') from None
        finally:
            pending.pop('verifier', None)

    def session(self, sid):
        with self.lock:
            p = self.pending.get(sid)
            return {'status':p['status']} if p and p['expires'] > self.clock() else {'status':'expired'}

    def access_token(self, grant_id):
        # Serialize rotation, while local revocation remains immediate.
        with self.refresh_lock:
            with self.lock:
                data = self._read()
                current = dict(self._active(data))
                if not self.available(grant_id):
                    raise ChatGPTError('ChatGPT ist getrennt oder nicht für diese Verarbeitung freigegeben.')
                if current['expires_at'] > self.clock()+120:
                    return current['access_token']
            token = self.request('POST',TOKEN_URL,data={'grant_type':'refresh_token','client_id':current['client_id'],
                'refresh_token':current['refresh_token'],'resource':API_URL})
            replacement = self._tokens(token, old=current)
            if token.get('id_token'):
                identity = self._identity(token['id_token'],current['client_id'])
                if identity['sub'] != current['sub']:
                    raise ChatGPTError('ChatGPT-Konto hat sich geändert. Bitte erneut anmelden.')
                replacement['id_token'] = token['id_token']
            with self.lock:
                if not self.available(grant_id):
                    self._revoke({**current, **replacement})
                    raise ChatGPTError('ChatGPT-Verbindung wurde während der Erneuerung getrennt.')
                data = self._read()
                active = self._active(data)
                active.update(replacement)
                self._write(data)
                if not self.available(grant_id):
                    raise ChatGPTError('ChatGPT-Nutzung ist nicht mehr freigegeben.')
                return replacement['access_token']

    def models(self):
        status = self.status()
        grant_id = status['grant_id']
        if not grant_id:
            raise ChatGPTError('Bitte ChatGPT anmelden und die Nutzung des Abos erlauben.')
        token = self.access_token(grant_id)
        response = self.request('GET',API_URL+'/models',headers={'Authorization':'Bearer '+token})
        values = response.get('models')
        if not isinstance(values,list):
            raise ChatGPTError('Der Modellkatalog konnte nicht gelesen werden.')
        models = [{'id':m['slug'],'label':m.get('display_name') or m['slug']} for m in values
                  if isinstance(m,dict) and m.get('visibility')=='list'
                  and isinstance(m.get('slug'),str) and re.fullmatch(r'[A-Za-z0-9._:/-]{1,128}',m['slug'])]
        with self.lock:
            if not self.available(grant_id):
                raise ChatGPTError('Die ChatGPT-Verbindung hat sich geändert.')
            self.catalogs[grant_id] = {m['id'] for m in models}
        return models

    def provider(self, model):
        from .chatgpt_provider import ChatGPTProvider
        with self.lock:
            grant = self.status()['grant_id']
            if not grant or model not in self.catalogs.get(grant,set()):
                raise ChatGPTError('Bitte ein verfügbares Modell des angemeldeten ChatGPT-Kontos auswählen.')
            return ChatGPTProvider(self,model,grant)

    def _revoke(self, current):
        if not current.get('refresh_token'):
            return True
        try:
            endpoint = self.request('GET',DISCOVERY_URL).get('revocation_endpoint','')
            parsed = urlparse(endpoint)
            if parsed.scheme != 'https' or parsed.netloc != 'auth.openai.com' or parsed.query or parsed.fragment:
                return False
            self.request('POST',endpoint,data={'token':current['refresh_token'],'token_type_hint':'refresh_token',
                                             'client_id':current['client_id']})
            return True
        except Exception:
            return False

    def disconnect(self):
        with self.lock:
            data = self._read()
            current = dict(self._active(data))
            self._revoked.add(current.get('grant_id'))
            for name in ('access_token','refresh_token','id_token','grant_id','scope','expires_at'):
                self._active(data).pop(name,None)
            data['active'] = None
            self.catalogs.clear()
            for p in self.pending.values():
                p['status'] = 'expired'
            try:
                self._write(data)
                saved = True
            except ChatGPTError:
                # Fail closed in this process even when the secret store fails.
                self._cached = data
                saved = False
        with self.refresh_lock:
            revoked = self._revoke(current)
        if not saved:
            return {'remote_revoked':revoked, 'notice':'Verarbeitung gestoppt. Der lokale Zugangsspeicher konnte nicht bereinigt werden. Bitte auch in ChatGPT den Zugang widerrufen und vor einem Neustart den Speicher prüfen.'}
        return {'remote_revoked':revoked,'notice': 'ChatGPT wurde getrennt.' if revoked else
                'Lokal getrennt. Der Widerruf bei OpenAI konnte nicht bestätigt werden; bitte auch in den ChatGPT-Einstellungen trennen.'}
