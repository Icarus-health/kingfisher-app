"""Documented Responses API transport for a selected ChatGPT OAuth grant."""
import json
import httpx

from .providers import ProviderError, Reply

RESPONSES_URL = 'https://api.openai.com/v1/responses'
MAX_TEXT = 16000
MAX_STREAM = 1_000_000


def bounded_lines(response):
    """Bound bytes before buffering a complete SSE line (including no-newline attacks)."""
    pending = bytearray()
    total = 0
    for chunk in response.iter_bytes(chunk_size=4096):
        total += len(chunk)
        if total > MAX_STREAM:
            raise ProviderError('Die ChatGPT-Antwort überschreitet die sichere Größe.')
        pending.extend(chunk)
        while b'\n' in pending:
            line, _, rest = pending.partition(b'\n')
            pending = bytearray(rest)
            yield line.rstrip(b'\r').decode('utf-8')
    if pending:
        yield pending.rstrip(b'\r').decode('utf-8')


class ChatGPTProvider:
    name = 'chatgpt'
    is_local = False
    is_remote = True

    def __init__(self, oauth, model, grant_id, client_factory=None):
        self.oauth, self.model, self.grant_id = oauth, model, grant_id
        self.client_factory = client_factory or (lambda: httpx.Client(timeout=120,trust_env=False,follow_redirects=False))
        self.usage = {'input_tokens':0,'output_tokens':0}

    @property
    def base_url(self):
        return 'https://api.openai.com/v1'

    def available(self):
        return self.oauth.available(self.grant_id)

    def complete(self, messages, tools):
        if tools:
            raise ProviderError('Dieser ChatGPT-Arbeitsgang verwendet keine Werkzeuge.')
        return self.complete_json(messages,max_tokens=1200,schema=None)

    def complete_json(self, messages, *, max_tokens, schema):
        return self.complete_json_guarded(messages,max_tokens=max_tokens,schema=schema)

    def complete_json_guarded(self,messages,*,max_tokens,schema,before_send=None,still_permitted=None):
        if not self.available():
            raise ProviderError('Die ChatGPT-Verbindung wurde getrennt oder geändert.')
        token = self.oauth.access_token(self.grant_id)
        inputs = []
        for message in messages:
            role = message.get('role')
            if role not in {'system','developer','user','assistant'} or not isinstance(message.get('content'),str):
                raise ProviderError('Nicht unterstützte Nachricht für die ChatGPT-Verarbeitung.')
            inputs.append({'role':'developer' if role=='system' else role,'content':message['content']})
        # Preview contract disallows max_output_tokens/temperature. Schema is an
        # instruction, with the authoritative strict validation in local analysis.
        if schema is not None:
            inputs.insert(0,{'role':'developer','content':'Antworte ausschließlich mit JSON nach diesem Schema. '
                'Keine Werkzeuge. Keine zusätzlichen Texte. Schema: '+json.dumps(schema,ensure_ascii=False)})
        payload = {'model':self.model,'input':inputs,'store':False,'stream':True}
        text, completed = '', False
        try:
            with self.client_factory() as client:
                # A refresh/client preparation may take time. Recheck the exact
                # job permission at the request boundary, not just before refresh.
                if before_send is not None:
                    before_send()
                with client.stream('POST',RESPONSES_URL,headers={'Authorization':'Bearer '+token},json=payload) as response:
                    if response.status_code == 429:
                        raise ProviderError('ChatGPT-Kontingent oder Anfragelimit erreicht. Bitte Nutzung in ChatGPT prüfen und später fortsetzen.')
                    if response.status_code in {401,403}:
                        raise ProviderError('ChatGPT-Zugriff fehlt oder ist abgelaufen. Bitte erneut anmelden.')
                    response.raise_for_status()
                    for line in bounded_lines(response):
                        if not self.available() or (still_permitted is not None and not still_permitted()):
                            raise ProviderError('ChatGPT-Verarbeitung wurde widerrufen.')
                        if not line.startswith('data:'):
                            continue
                        raw = line[5:].strip()
                        if raw == '[DONE]':
                            continue
                        event = json.loads(raw)
                        kind = event.get('type')
                        if completed:
                            raise ProviderError('Ungültige Fortsetzung der ChatGPT-Antwort.')
                        if kind in {'response.failed','response.incomplete','error'}:
                            raise ProviderError('ChatGPT hat die Auswertung nicht vollständig abgeschlossen.')
                        if kind in {'response.output_item.added','response.output_item.done'} and event.get('item',{}).get('type') not in {'message','reasoning'}:
                            raise ProviderError('Unerlaubter Werkzeugaufruf in der ChatGPT-Auswertung.')
                        if kind == 'response.output_text.delta':
                            delta = event.get('delta')
                            if not isinstance(delta,str) or len(text)+len(delta)>MAX_TEXT:
                                raise ProviderError('Die ChatGPT-Antwort ist zu groß oder ungültig.')
                            text += delta
                        if kind == 'response.completed':
                            result = event.get('response',{})
                            if result.get('status') != 'completed':
                                raise ProviderError('ChatGPT hat die Auswertung nicht vollständig abgeschlossen.')
                            if any(item.get('type') not in {'message','reasoning'} for item in result.get('output',[])):
                                raise ProviderError('Unerlaubter Werkzeugaufruf in der ChatGPT-Auswertung.')
                            usage = result.get('usage') or {}
                            for key in self.usage:
                                if type(usage.get(key)) is int and usage[key]>=0:
                                    self.usage[key] += usage[key]
                            completed = True
        except (httpx.HTTPError,ValueError,TypeError,AttributeError):
            raise ProviderError('ChatGPT-Auswertung unterbrochen. Bitte Verbindung und Anmeldung prüfen.') from None
        if not completed or not self.available() or (still_permitted is not None and not still_permitted()):
            raise ProviderError('ChatGPT-Auswertung ist unvollständig oder die Freigabe wurde geändert.')
        return Reply(text=text,model=self.model)
