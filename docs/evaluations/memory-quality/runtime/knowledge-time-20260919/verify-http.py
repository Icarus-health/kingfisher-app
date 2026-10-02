"""Independent HTTP/provider/restart checks using only synthetic persistent data."""
import argparse
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import time
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--repo', required=True)
args = parser.parse_args()
root = Path(__file__).parent.resolve()
repo = Path(args.repo)
data = root/'native-data'
assert not data.exists(), 'Use a fresh isolated data directory for every recorded run'
data.mkdir(mode=0o700)
token = secrets.token_urlsafe(32)
(root/'token').write_text(token)
(root/'token').chmod(0o600)
env = {**os.environ, 'PYTHONPATH':str(repo/'sidecar'), 'ICARUS_DATA_DIR':str(data),
       'ICARUS_SIDECAR_TOKEN':token, 'ICARUS_UI_DIR':str(repo/'app/dist')}
base = 'http://127.0.0.1:18994'
checks = []
process = None
log = (root/'native-server.log').open('w')
def request(path, body=None):
    req = urllib.request.Request(base+path, data=None if body is None else json.dumps(body).encode(),
        headers={'x-icarus-token':token, 'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)
def start():
    global process
    process = subprocess.Popen([str(repo/'.venv/bin/python'), str(root/'serve.py')], env=env, stdout=log, stderr=log)
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError((root/'native-server.log').read_text())
        try:
            request('/health')
            return
        except OSError:
            time.sleep(.1)
    raise RuntimeError('Synthetic server did not start')
def stop():
    if process and process.poll() is None:
        process.terminate()
        process.wait(timeout=10)
def check(name, condition):
    checks.append({'name':name, 'passed':bool(condition)})
    assert condition, name
def last_call():
    return json.loads((data/'provider.jsonl').read_text().splitlines()[-1])
def knowledge_rows(call):
    return [json.loads(line[14:]) for message in call['messages']
            if isinstance(message.get('content'), str) for line in message['content'].splitlines()
            if line.startswith('- [knowledge] ')]
def row_for(call, claim_id):
    return next(row for row in knowledge_rows(call) if row['assertion_id']=='claim:'+claim_id)
def without_reason(row):
    return {k:v for k,v in row.items() if k!='reason'}
def last_reply(payload):
    return [m['content'] for m in payload['messages'] if m['role']=='assistant'][-1]
def sent_text():
    return json.dumps(last_call()['messages'], ensure_ascii=False)
def update_event(identifier, value):
    with sqlite3.connect(data/'episodes.sqlite3') as connection:
        document = json.loads(connection.execute('SELECT document FROM episodes WHERE id=?', (identifier,)).fetchone()[0])
        document['occurred_at'] = value
        connection.execute('UPDATE episodes SET occurred_at=?, document=? WHERE id=?',
                           (value, json.dumps(document), identifier))
def cycle_source(identifier):
    subprocess.run([str(repo/'.venv/bin/python'), '-c',
        'from icarus_memory.episodes import EpisodeStore; import os; from pathlib import Path; '
        's=EpisodeStore(Path(os.environ["ICARUS_DATA_DIR"])/"episodes.sqlite3"); '
        f's.ignore({identifier!r}); s.reopen({identifier!r}); s.close()'], env=env, check=True)

try:
    start()
    state = json.loads((data/'state.json').read_text())
    orion = state['ORION']
    conversation = request('/api/v1/conversations', {'title':'Synthetische M2c-Laufzeitprüfung'})['conversation']['id']
    route = '/api/v1/conversations/'+conversation
    def send(message):
        return request(route+'/messages', {'message':message})
    initial = send('ORION')
    actual = row_for(last_call(), orion['claim_id'])
    check('exact_provider_projection_matches_independently_frozen_expected', without_reason(actual)==orion['expected'])
    item = next(i for i in initial['context']['items'] if i['assertion_id']==actual['assertion_id'])
    check('api_projection_equals_actual_provider_data', item['knowledge_projection']==actual)
    check('event_time_basis_explicit', item['evidence_at_basis']=='occurred_at')
    check('lineage_version_2', initial['context']['knowledge_claim_lineage_version']==2)
    old_reply = last_reply(initial)
    stop()
    start()
    reloaded = request(route)
    check('persisted_projection_survives_process_restart', reloaded['context']['items']==initial['context']['items'])
    continued = send('ORION')
    check('unchanged_history_survives_restart', old_reply in sent_text())
    previous_reply = last_reply(continued)
    update_event(orion['episode_ids'][0], '2024-10-01T09:00:00+00:00')
    stale = request(route)
    check('changed_time_omits_current_card', not any(i['assertion_id']==actual['assertion_id'] for i in stale['context']['items']))
    check('historical_transcript_preserved', any(m['content']==previous_reply for m in stale['messages']))
    changed = send('ORION')
    check('changed_time_resets_provider_history', old_reply not in sent_text() and previous_reply not in sent_text())
    check('fresh_projection_has_new_event_time', row_for(last_call(),orion['claim_id'])['primary_evidence']['occurred_at']=='2024-10-01T09:00:00+00:00')
    changed_reply = last_reply(changed)
    update_event(orion['episode_ids'][0], '2024-10-01T11:00:00+02:00')
    equivalent = send('ORION')
    check('equivalent_timezone_preserves_history', changed_reply in sent_text())
    equivalent_reply = last_reply(equivalent)
    cycle_source(orion['episode_ids'][1])
    check('secondary_withdraw_reopen_omits_old_card', not any(i['assertion_id']==actual['assertion_id'] for i in request(route)['context']['items']))
    generation = send('ORION')
    check('secondary_generation_cycle_resets_history', equivalent_reply not in sent_text())
    (data/'mode').write_text('external')
    send('ORION')
    check('external_provider_receives_no_local_knowledge', not knowledge_rows(last_call()))
    check('external_provider_receives_no_local_assistant_history', 'SYNTHETIC_RESPONSE_' not in sent_text())
    (data/'mode').write_text('local')
    null_payload = send('NEBEL')
    neb = row_for(last_call(), state['NEBEL']['claim_id'])
    check('unknown_event_stays_null', without_reason(neb)==state['NEBEL']['expected'])
    null_item = next(i for i in null_payload['context']['items'] if i['assertion_id']==neb['assertion_id'])
    check('import_fallback_labeled_as_import', null_item['evidence_at_basis']=='recorded_at')
    result = {'synthetic_only':True,'real_model':False,'checks':checks,'initial_api':initial,'final_api':null_payload,
              'provider_calls':[json.loads(line) for line in (data/'provider.jsonl').read_text().splitlines()]}
    (root/'native-result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'checks_passed':len(checks),'synthetic_only':True}))
finally:
    stop()
    log.close()
    if not (root/'native-result.json').exists():
        (root/'native-failed-result.json').write_text(json.dumps({'checks':checks}, indent=2)+'\n')
