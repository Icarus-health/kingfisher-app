"""Explizites lokales 8K-Profil: vollständige Texte oder Fehler, kein stiller Rückfall.

Ollama >= 0.40.13 unterstützt truncate/shift im nativen Chat. Alle anderen
Anbieter behalten ihren bestehenden Transport und ihre bestehenden Grenzen.
"""
from copy import deepcopy
import json
import os
import re
from urllib.parse import urlsplit,urlunsplit
import uuid

import httpx

from .providers import OpenAICompatible,ProviderError
from .local_model_guard import verify_local_model,_json

FLAG='ICARUS_OLLAMA_8K_PROFILE'
CONTEXT=8192
INPUT_BYTES=16000
OUTPUT_TOKENS=1200


def canonical(name):
    return name if ':' in name.rsplit('/',1)[-1] else name+':latest'


def selected(provider):
    expected=os.environ.get(FLAG,'').strip()
    return bool(expected and type(provider) is OpenAICompatible and provider.is_local
                and isinstance(provider.model,str) and canonical(provider.model)==canonical(expected))


def verify_profile(provider):
    """Metadaten vor jedem modellladenden Nebeneffekt; kein Input wird gesendet."""
    if not selected(provider):return None
    permitted=getattr(provider,'_verified_local_permitted',lambda:True)
    if not permitted():raise ProviderError('Die lokale Verarbeitung ist nicht mehr freigegeben.')
    parsed=urlsplit(provider.base_url)
    origin=urlunsplit((parsed.scheme,parsed.netloc,'','',''))
    try:
        with httpx.Client(timeout=5.0,trust_env=False,follow_redirects=False) as client:
            identity=verify_local_model(provider,client=client,expected_num_ctx=CONTEXT)
            version=_json(client,'GET',origin+'/api/version').get('version')
        if not permitted():raise ProviderError('Die lokale Verarbeitung ist nicht mehr freigegeben.')
        match=re.fullmatch(r'(\d+)\.(\d+)\.(\d+)(?:\+[A-Za-z0-9.-]+)?',version) if isinstance(version,str) else None
        if not match or tuple(map(int,match.groups()))<(0,40,13):
            raise ProviderError('Das gewählte Kontextprofil benötigt stabiles Ollama ab 0.40.13.')
        previous=getattr(provider,'_small_context_identity',None)
        if previous is not None and previous!=identity:
            raise ProviderError('Die Identität des gewählten Kontextprofils hat sich geändert.')
        provider._small_context_identity=identity
        return identity
    except (httpx.HTTPError,ValueError,TypeError) as error:
        raise ProviderError('Das lokale 8K-Kontextprofil konnte nicht bestätigt werden.') from error


def check_deadline(provider):
    if selected(provider):
        from .providers import _json_transport_timeout
        _json_transport_timeout(5.0)


def verify_lifecycle(provider):
    """Wartezeit, Metadaten und vorbereitende Hilfsaufrufe verbrauchen dieselbe Frist."""
    check_deadline(provider)
    identity=verify_profile(provider)
    check_deadline(provider)
    return identity


def _encoded(value):
    try:return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':')).encode('utf-8')
    except (ValueError,TypeError,UnicodeError) as error:
        raise ProviderError('Ungültiger Modelleingang für das lokale Kontextprofil.') from error


def _arguments(value):
    def pairs(entries):
        result={}
        for key,item in entries:
            if key in result:raise ValueError('Duplicate argument key')
            result[key]=item
        return result
    def constant(value):raise ValueError('Nonfinite argument')
    if not isinstance(value,str):raise ProviderError('Historische Werkzeugargumente müssen JSON-Text sein.')
    try:result=json.loads(value,object_pairs_hook=pairs,parse_constant=constant)
    except (ValueError,TypeError) as error:raise ProviderError('Ungültige historische Werkzeugargumente.') from error
    if not isinstance(result,dict):raise ProviderError('Werkzeugargumente müssen Objekte sein.')
    return result


def _messages(messages):
    if not isinstance(messages,list):raise ProviderError('Nachrichten müssen eine Liste sein.')
    result=[];pending={};seen=set()
    for original in messages:
        if not isinstance(original,dict) or set(original)-{'role','content','tool_calls','tool_call_id','tool_name'}:
            raise ProviderError('Nicht unterstütztes Nachrichtenformat im kleinen Kontextprofil.')
        message=deepcopy(original);role=message.get('role')
        if role not in {'system','user','assistant','tool'} or not isinstance(message.get('content'),str):
            raise ProviderError('Das kleine Kontextprofil unterstützt nur Textnachrichten.')
        if role=='tool':
            identifier=message.get('tool_call_id')
            if (not isinstance(identifier,str) or identifier not in pending or identifier!=next(iter(pending))
                    or 'tool_calls' in message):raise ProviderError('Unvollständige Werkzeugzuordnung.')
            name=pending.pop(identifier)
            if message.get('tool_name',name)!=name:raise ProviderError('Widersprüchlicher Werkzeugname.')
            message['tool_name']=name
        else:
            if pending or 'tool_call_id' in message or 'tool_name' in message:
                raise ProviderError('Fehlendes oder falsch zugeordnetes Werkzeugergebnis.')
            if 'tool_calls' in message:
                calls=message['tool_calls']
                if role!='assistant' or not isinstance(calls,list) or not calls:
                    raise ProviderError('Ungültige historische Werkzeugaufrufe.')
                for call in calls:
                    if (not isinstance(call,dict) or set(call)-{'id','type','function'} or call.get('type')!='function'
                            or not isinstance(call.get('id'),str) or not call['id'] or call['id'] in seen):
                        raise ProviderError('Ungültige historische Werkzeugkennung.')
                    function=call.get('function')
                    if (not isinstance(function,dict) or set(function)!={'name','arguments'}
                            or not isinstance(function['name'],str) or not function['name']):
                        raise ProviderError('Ungültige historische Werkzeugfunktion.')
                    function['arguments']=_arguments(function['arguments'])
                    seen.add(call['id']);pending[call['id']]=function['name']
        result.append(message)
    if pending:raise ProviderError('Werkzeugergebnisse fehlen.')
    return result


class InputTooLarge(ProviderError):
    """Die vollständige Anfrage passt nicht; reine Budgetvorschau darf dies melden."""


def _native_payload(provider,payload):
    """Reiner gemeinsamer Builder für Vorschau und tatsächlichen Transport."""
    if not isinstance(payload,dict) or payload.get('model')!=provider.model:
        raise ProviderError('Das Anfrageziel entspricht nicht dem geprüften lokalen Kontextprofil.')
    if len(_encoded(payload))>INPUT_BYTES:raise InputTooLarge('Eingabe über der lokalen 16.000-Byte-Kontextgrenze; nichts gekürzt.')
    if set(payload)-{'model','messages','max_tokens','response_format','reasoning_effort','temperature','tools'}:
        raise ProviderError('Nicht unterstützte Anfrageoption im kleinen Kontextprofil.')
    if payload.get('reasoning_effort','none')!='none':raise ProviderError('Nicht unterstützter Denkmodus.')
    tokens=payload.get('max_tokens',1024)
    if type(tokens) is not int or not 1<=tokens<=OUTPUT_TOKENS:raise ProviderError('Ungültiges Ausgabebudget.')
    native={'model':payload['model'],'messages':_messages(payload.get('messages')),
        'stream':False,'think':False,'truncate':False,'shift':False,'keep_alive':'15s',
        'options':{'num_ctx':CONTEXT,'num_predict':tokens,'temperature':payload.get('temperature',1.0),
                   'top_p':1.0,'presence_penalty':0.0,'frequency_penalty':0.0}}
    if 'tools' in payload:
        tools=payload['tools']
        if not isinstance(tools,list):raise ProviderError('Ungültige Werkzeugdefinitionen.')
        for tool in tools:
            function=tool.get('function') if isinstance(tool,dict) else None
            if (not isinstance(tool,dict) or set(tool)!={'type','function'} or tool['type']!='function'
                    or not isinstance(function,dict) or set(function)-{'name','description','parameters'}
                    or not isinstance(function.get('name'),str) or not function['name']
                    or not isinstance(function.get('parameters'),dict)):
                raise ProviderError('Nicht unterstützte Werkzeugdefinition.')
        native['tools']=deepcopy(tools)
    if 'response_format' in payload:
        format=payload['response_format']
        if format=={'type':'json_object'}:native['format']='json'
        elif isinstance(format,dict) and set(format)=={'type','json_schema'} and format['type']=='json_schema':
            specification=format['json_schema']
            if (not isinstance(specification,dict) or set(specification)!={'name','strict','schema'}
                    or not isinstance(specification['name'],str) or specification['strict'] is not True
                    or not isinstance(specification['schema'],dict)):
                raise ProviderError('Nicht unterstütztes JSON-Schemaformat.')
            native['format']=deepcopy(specification['schema'])
        else:raise ProviderError('Nicht unterstütztes Antwortformat.')
    if len(_encoded(native))>INPUT_BYTES:raise InputTooLarge('Native Eingabe über der lokalen Kontextgrenze; nichts gekürzt.')
    return native,tokens


def prepare(provider,payload):
    """Den endgültigen logischen Eingang prüfen, bevor Ampel/Modellvorbereitung läuft."""
    if not selected(provider):return None
    native,tokens=_native_payload(provider,payload)
    identity=verify_profile(provider)
    return Request(native,identity,tokens)


class Request:
    def __init__(self,payload,identity,tokens):
        self.payload=payload;self.identity=identity;self.tokens=tokens

    def send(self,provider,timeout):
        """Innerhalb der bestehenden Ampel; Frist erst nach Warte-/Prüfzeit bestimmen."""
        timeout()  # Abgelaufene JSON-Arbeit darf auch keine Metadaten mehr vorbereiten.
        if verify_profile(provider)!=self.identity:raise ProviderError('Kontextprofil während der Anfrage geändert.')
        parsed=urlsplit(provider.base_url);origin=urlunsplit((parsed.scheme,parsed.netloc,'','',''))
        with provider._client(timeout()) as client:
            response=client.post(origin+'/api/chat',json=self.payload)
            response.raise_for_status();data=response.json()
        if verify_profile(provider)!=self.identity:raise ProviderError('Kontextprofil während der Antwort geändert.')
        return _response(data,self.tokens)


def _response(data,tokens):
    if not isinstance(data,dict):raise ProviderError('Ungültige native Antwort.')
    message=data.get('message')
    if (data.get('done') is not True or data.get('done_reason')!='stop' or not isinstance(message,dict)
            or not isinstance(message.get('content'),str)):
        raise ProviderError('Das lokale Modell hat nicht vollständig geantwortet.')
    prompt=data.get('prompt_eval_count');completion=data.get('eval_count')
    if (type(prompt) is not int or not 0<prompt<CONTEXT-OUTPUT_TOKENS
            or type(completion) is not int or not 0<=completion<=tokens):
        raise ProviderError('Kontext-/Ausgabereserve ist nicht nachgewiesen.')
    calls=[];seen=set();raw=message.get('tool_calls',[])
    if not isinstance(raw,list):raise ProviderError('Ungültige native Werkzeugantwort.')
    for call in raw:
        function=call.get('function') if isinstance(call,dict) else None
        identifier=call.get('id') if isinstance(call,dict) else None
        if identifier is None or identifier=='':identifier='kf-context-'+uuid.uuid4().hex
        if (not isinstance(identifier,str) or identifier in seen or not isinstance(function,dict)
                or not isinstance(function.get('name'),str) or not function['name']
                or not isinstance(function.get('arguments'),dict) or call.get('type','function')!='function'):
            raise ProviderError('Ungültige native Werkzeugantwort.')
        seen.add(identifier)
        calls.append({'id':identifier,'type':'function','function':{'name':function['name'],
            'arguments':_encoded(function['arguments']).decode('utf-8')}})
    if not calls and not message['content'].strip():raise ProviderError('Das lokale Modell hat keine sichtbare Antwort geliefert.')
    return {'choices':[{'finish_reason':'stop','message':{'content':message['content'],'tool_calls':calls}}],
            'usage':{'prompt_tokens':prompt,'completion_tokens':completion,'total_tokens':prompt+completion}}
