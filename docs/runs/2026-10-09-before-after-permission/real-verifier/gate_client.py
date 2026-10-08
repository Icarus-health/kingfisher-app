"""Once-only synthetic diagnostic of the unchanged real second gate."""
import hashlib, inspect, json, os, sys, threading, time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
import httpx

ROOT = Path(__file__).resolve().parent
REPO = ROOT / 'repo'
sys.path[:0] = [str(REPO / 'sidecar'), str(REPO / 'scripts')]
from icarus_memory import satzpruefung, satzpruefung_modell
from icarus_memory.local_model_guard import VerifiedLocalProvider, verify_local_model
from icarus_memory.providers import OpenAICompatible

ORIGIN = 'http://127.0.0.1:11439'
MODEL = 'qwen3.5:4b'
CATALOG = ROOT / 'catalog.json'
FREEZE = json.loads((ROOT / 'freeze.json').read_text())
assert not (ROOT / 'report.json').exists(), 'No rerun or overwrite'
assert hashlib.sha256(CATALOG.read_bytes()).hexdigest() == FREEZE['catalog_sha256']
catalog = json.loads(CATALOG.read_text())
assert catalog['synthetic'] and catalog['frozen_before_model_run']
sources = {s['id']: s for s in catalog['sources']}
events, transport = [], []
lock = threading.Lock()
report = {'scope': FREEZE['scope'], 'synthetic_only': True, 'completed': False,
          'code_commit': FREEZE['commit'], 'catalog_sha256': FREEZE['catalog_sha256'],
          'production_settings_loaded': False, 'role_switches': 0, 'reruns': 0,
          'model': MODEL, 'origin': ORIGIN, 'rows': [], 'calls': events,
          'raw_http_calls': transport, 'maintenance': [], 'code_files': {},
          'budgets': {'per_sentence_seconds': satzpruefung_modell.SATZ_BUDGET_S,
                      'per_answer_seconds': satzpruefung_modell.GESAMT_BUDGET_S},
          'budget_scope': 'one real gate invocation per case; unchanged defaults',
          'diagnostic_note': 'All 11 cases reach the model, including centrally rejected controls. Real answer flow can skip centrally rejected candidates. No intake, retrieval, source selection, saved-answer or UI claim.'}
for module in (satzpruefung, satzpruefung_modell):
    p = Path(inspect.getfile(module)); assert p.is_relative_to(REPO)
    report['code_files'][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
for obj in (OpenAICompatible, VerifiedLocalProvider):
    p = Path(inspect.getfile(obj)); assert p.is_relative_to(REPO)
    report['code_files'][p.name] = hashlib.sha256(p.read_bytes()).hexdigest()

def save():
    with lock:
        contents = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    temp = ROOT / 'report.new'; temp.write_text(contents); temp.replace(ROOT / 'report.json')

# Observe raw synthetic requests/replies while retaining the exact product client,
# endpoint, deadline, payload, parser and local-weight checks.
original_client = OpenAICompatible._client
def observing_client(self, timeout):
    client = original_client(self, timeout)
    def request_hook(request):
        assert str(request.url) == ORIGIN + '/v1/chat/completions'
        entry = {'state': 'requested', 'url': str(request.url),
                 'request': json.loads(request.content), 'timeout_seconds': timeout}
        with lock: transport.append(entry)
        request.extensions['diagnostic_entry'] = entry
    def response_hook(response):
        response.read()
        entry = response.request.extensions['diagnostic_entry']
        with lock:
            entry.update(state='response', status=response.status_code,
                         raw_reply=response.text)
    client.event_hooks['request'].append(request_hook)
    client.event_hooks['response'].append(response_hook)
    return client
OpenAICompatible._client = observing_client

class Meter:
    def __init__(self, inner):
        self.inner = inner
        self.model, self.name, self.is_local = inner.model, inner.name, inner.is_local
    def complete_json(self, messages, **kwargs):
        event = {'state': 'pending', 'request': messages, 'kwargs': kwargs,
                 'started': time.monotonic()}
        with lock: events.append(event)
        try:
            reply = self.inner.complete_json(messages, **kwargs)
        except Exception as error:
            with lock:
                event.update(state='error', error_type=type(error).__name__,
                             error=str(error), seconds=time.monotonic() - event['started'])
            raise
        with lock:
            event.update(state='ok', raw_reply=reply.text, reply_model=reply.model,
                         seconds=time.monotonic() - event['started'])
        return reply

try:
    provider = OpenAICompatible(MODEL, api_key='synthetic-local', base_url=ORIGIN + '/v1')
    provider._verified_local_transport = True
    identity = verify_local_model(provider)
    report['verified_identity_before'] = {'name': identity.name, 'digest': identity.digest}
    # This request loads existing weights without a source, candidate or prompt.
    start = time.monotonic()
    with httpx.Client(trust_env=False, follow_redirects=False, timeout=60) as http:
        payload = {'model': MODEL, 'prompt': '', 'stream': False, 'keep_alive': '15s'}
        response = http.post(ORIGIN + '/api/generate', json=payload)
        response.raise_for_status()
        report['maintenance'].append({'purpose': 'empty model preload', 'request': payload,
                                     'reply': response.json(), 'seconds': time.monotonic() - start})
    verified = VerifiedLocalProvider(provider)
    meter = Meter(verified)
    gate = satzpruefung_modell.tor('an', meter)
    assert gate.aktiv and gate.modell == MODEL
    report['gate'] = gate.als_dict(); save()
    for case in catalog['cases']:
        source_rows = [sources[sid] for sid in case['source_ids']]
        central_sources = {str(i): satzpruefung.Beleg(str(i), s['text'])
                           for i, s in enumerate(source_rows, 1)}
        central = satzpruefung.satz_pruefen(
            satzpruefung.Satz(case['candidate'], tuple(central_sources)), central_sources)
        evidence = [SimpleNamespace(nummer=i, kopf=s['title'], text=s['text'],
                                    pruef_text=s['text'], ref={'start': 0, 'end': len(s['text'])})
                    for i, s in enumerate(source_rows, 1)]
        index = len(events); transport_index = len(transport); start = time.monotonic()
        judgments = satzpruefung_modell.urteilen([(case['candidate'], evidence)], gate)
        seconds = time.monotonic() - start
        assert len(judgments) == 1
        judgment = judgments[0]
        row = {**case, 'sources': source_rows,
               'central_verdict': {'passed': central.bestanden, 'reasons': list(central.gruende)},
               'actual_model_verdict': {'value': judgment.wert, 'reason': judgment.anlass,
                                        'explanation': judgment.grund},
               'combined_passed': central.bestanden and judgment.wert == satzpruefung_modell.JA,
               'gate_seconds': seconds, 'provider_event_start': index,
               'http_event_start': transport_index}
        report['rows'].append(row); save()
        # Product deadline threads are daemons; do not let a late request overlap
        # the next case. This is observation only and never changes the verdict.
        deadline = time.monotonic() + 6
        while any(e['state'] == 'pending' for e in events[index:]):
            if time.monotonic() >= deadline:
                raise RuntimeError('A timed-out provider request remained pending; no further cases sent')
            time.sleep(.05)
        row['provider_event_end'] = len(events)
        row['http_event_end'] = len(transport)
        row['provider_counts'] = dict(Counter(e['state'] for e in events[index:]))
        save()
        print(case['id'], 'central=' + str(central.bestanden),
              'model=' + judgment.wert, judgment.anlass,
              'combined=' + str(row['combined_passed']), flush=True)
    final_identity = verify_local_model(provider)
    report['verified_identity_after'] = {'name': final_identity.name, 'digest': final_identity.digest}
    assert final_identity == identity
    report['provider_counts'] = dict(Counter(e['state'] for e in events))
    report['model_verdict_counts'] = dict(Counter(r['actual_model_verdict']['value'] for r in report['rows']))
    report['false_combined_accepts'] = [r['id'] for r in report['rows'] if not r['expected_supported'] and r['combined_passed']]
    report['supported_combined_accepts'] = [r['id'] for r in report['rows'] if r['expected_supported'] and r['combined_passed']]
    report['completed'] = True
except BaseException as error:
    report['runtime_error'] = {'type': type(error).__name__, 'message': str(error)}
    raise
finally:
    OpenAICompatible._client = original_client
    save()
