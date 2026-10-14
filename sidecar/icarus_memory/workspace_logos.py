"""Explicit public-domain favicon lookup, pinned TLS destination and local cache."""
import base64
import http.client
import ipaddress
import re
import socket
import ssl


def normalize_domain(value):
    if not isinstance(value,str):
        raise ValueError('Bitte nur die öffentliche Firmendomain eingeben.')
    try:
        domain=value.strip().lower().encode('idna').decode('ascii')
    except UnicodeError:
        raise ValueError('Ungültige Domain.') from None
    if not re.fullmatch(r'(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}',domain):
        raise ValueError('Bitte nur die öffentliche Firmendomain eingeben, ohne Adresse oder Zugangsdaten.')
    return domain


def public_ip(domain):
    try:
        addresses={info[4][0] for info in socket.getaddrinfo(domain,443,type=socket.SOCK_STREAM)}
    except socket.gaierror:
        raise ValueError('Die Domain ist gerade nicht erreichbar.') from None
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('Interne oder nicht öffentliche Ziele sind gesperrt.')
    return sorted(addresses,key=lambda address:(':' in address,address))[0]


class PinnedTLS(http.client.HTTPSConnection):
    def __init__(self,domain,address):
        super().__init__(domain,443,timeout=6,context=ssl.create_default_context())
        self.address=address

    def connect(self):
        raw=socket.create_connection((self.address,443),self.timeout)
        try:
            self.sock=self._context.wrap_socket(raw,server_hostname=self.host)
        except Exception:
            raw.close()
            raise


def fetch_logo(domain):
    domain=normalize_domain(domain)
    address=public_ip(domain)
    for path in ('/favicon.ico','/favicon.png'):
        connection=PinnedTLS(domain,address)
        try:
            connection.request('GET',path,headers={'User-Agent':'Kingfisher/1.0 (public site icon)', 'Accept':'image/png,image/jpeg,image/webp,image/x-icon'})
            response=connection.getresponse()
            if response.status==404:
                continue
            if response.status!=200:
                raise ValueError('Kein direkt erreichbares Firmenbild; bitte ein eigenes Logo hochladen.')
            raw=response.read(262145)
            if not 12<=len(raw)<=262144:
                raise ValueError('Das Firmenbild ist leer oder größer als 256 KB.')
            if raw.startswith(b'\x89PNG\r\n\x1a\n'): mime='image/png'
            elif raw.startswith(b'\xff\xd8\xff'): mime='image/jpeg'
            elif raw.startswith(b'RIFF') and raw[8:12]==b'WEBP': mime='image/webp'
            elif raw.startswith(b'\x00\x00\x01\x00'): mime='image/x-icon'
            else: raise ValueError('Das Firmenbild hat kein unterstütztes Bildformat. Ein eigenes Logo kann hochgeladen werden.')
            return f'data:{mime};base64,'+base64.b64encode(raw).decode('ascii')
        except (OSError,http.client.HTTPException):
            raise ValueError('Firmenbild gerade nicht erreichbar. Ein eigenes Logo kann hochgeladen werden.') from None
        finally:
            connection.close()
    raise ValueError('Kein Firmenbild gefunden. Bitte ein eigenes Logo hochladen.')


def register(app,guard):
    from fastapi import HTTPException
    from pydantic import BaseModel,ConfigDict,StrictInt,Field
    class Input(BaseModel):
        model_config=ConfigDict(extra='forbid')
        domain:str=Field(min_length=1,max_length=253)
        revision:StrictInt
    @app.post('/api/v1/workspace-logos/{identifier:path}',dependencies=guard)
    def load(identifier:str,body:Input):
        with app.state.conversation_lock:
            consent=app.state.workspace_views.get('preferences','online')
            if not consent['data'] or not consent['data']['logos']:
                raise HTTPException(403,'Online-Firmenbilder sind ausgeschaltet.')
            previous=app.state.workspace_views.get('organisation_logo',identifier)
            if body.revision!=previous['revision']:
                raise HTTPException(409,'Der Bildstand hat sich geändert. Bitte erneut prüfen.')
        try:
            domain=normalize_domain(body.domain)
            data_url=fetch_logo(domain)
            with app.state.conversation_lock:
                if app.state.workspace_views.get('preferences','online')!=consent:
                    raise HTTPException(409,'Die Online-Freigabe wurde geändert. Das Bild wurde nicht übernommen.')
                return app.state.workspace_views.put('organisation_logo',identifier,
                    {'domain':domain,'data_url':data_url},body.revision)
        except ValueError as exc:
            from .workspace_views import ViewChanged
            raise HTTPException(409 if isinstance(exc,ViewChanged) else 422,str(exc)) from exc
