"""CPU-only 10k lifecycle acceptance over real intake, worker and vector stores."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
from threading import RLock
import time

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'sidecar'))
from icarus_memory.episodes import EpisodeStore
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_intake import Intake
from icarus_memory.providers import Reply
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.working_memory_worker import run, Zwischenstand
from icarus_memory.working_memory_semantic_index import DurableSemanticIndex

AT = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)
IMMUTABLE_FIELDS = ('id', 'kind', 'title', 'body', 'digest', 'provenance',
                    'recorded_at', 'occurred_at', 'participants', 'contacts')


def original_inventory(episodes):
    """Hash every original, including ignored and superseded source versions.

    Lifecycle state, support generations and current-head pointers are
    intentionally outside this content inventory: those are expected to change.
    Body, origin, timestamps, contacts and identity must remain byte-faithful.
    Both the JSON original and its scalar SQL columns are checked.
    """
    inventory = {}
    with episodes._lock:
        rows = episodes._conn.execute('SELECT * FROM episodes ORDER BY id').fetchall()
    for row in rows:
        document = json.loads(row['document'])
        for field in ('id', 'kind', 'title', 'body', 'digest', 'recorded_at', 'occurred_at'):
            assert row[field] == document[field], f'original_column_mismatch:{row["id"]}:{field}'
        expected_digest = 'sha256:' + hashlib.sha256(document['body'].encode()).hexdigest()
        assert document['digest'] == expected_digest, f'original_digest_mismatch:{row["id"]}'
        frozen = {field: document[field] for field in IMMUTABLE_FIELDS}
        frozen['source_key'] = row['source_key']
        inventory[row['id']] = hashlib.sha256(json.dumps(
            frozen, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    return inventory


def check_inventory(episodes, expected, *, exact=True):
    current = original_inventory(episodes)
    assert all(current.get(identifier) == digest for identifier, digest in expected.items()), \
        'original_content_changed_or_missing'
    if exact:
        assert set(current) == set(expected), 'unexpected_original_added_or_removed'
    return current


def inventory_digest(inventory):
    return hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def check_mail_payloads(episodes, numbers):
    """Compare every requested original with the explicit synthetic reader gold."""
    expected = set(numbers)
    found, keys, origins = set(), set(), set()
    with episodes._lock:
        rows = episodes._conn.execute('SELECT title,document,source_key FROM episodes').fetchall()
    for row in rows:
        document = json.loads(row['document'])
        number = int(row['title'].removeprefix('Archiv '))
        if number not in expected:
            continue
        assert number not in found, f'duplicate_original_number:{number}'
        assert document['title'] == f'Archiv {number}'
        assert document['body'] == f'Der Schlüssel quasararchiv{number:05d} gehört zu Archiv {number}.', \
            f'original_payload_mismatch:{number}'
        assert document['kind'] == 'message'
        assert datetime.fromisoformat(document['occurred_at']) == AT
        origin = document['provenance']
        assert origin['source_type'] == 'email'
        assert origin['source_ref'] == f'synthetic-account:msg-{number}'
        assert datetime.fromisoformat(origin['captured_at']) == AT
        assert document['participants'] == [f'Person {number} <p{number}@synthetic.invalid>']
        key = 'mail:' + hashlib.sha256(json.dumps(
            ['synthetic-account', f'gmail:provider-{number}']).encode()).hexdigest()
        assert row['source_key'] == key, f'provider_identity_mismatch:{number}'
        assert key not in keys and origin['source_ref'] not in origins
        found.add(number); keys.add(key); origins.add(origin['source_ref'])
    assert found == expected, 'original_payloads_missing'
    return len(found)

class Reader:
    def __init__(self, count):
        self.count = count
        self.label_count = min(1000, count // 10)
        self.fail = {42}
        self.reads = 0

    def inventory_page(self, folder, after_uid=0, before_uid=None, limit=100, uidvalidity=None):
        available = min(self.count, self.label_count) if folder == 'Archive' else self.count
        upper = available if before_uid is None else min(before_uid, available)
        end = min(upper, after_uid + limit)
        return dict(folder=folder, uidvalidity='7', upper_uid=upper,
                    uids=list(range(after_uid + 1, end + 1)), next_uid=end, done=end >= upper)
    def message_in_folder(self, folder, uid):
        n = int(uid.split('.')[1])
        self.reads += 1
        if n in self.fail:
            raise OSError('synthetic transport failure, no secret')
        return Message(uid, f'Archiv {n}', f'Person {n} <p{n}@synthetic.invalid>', AT,
                       f'msg-{n}', False, body=f'Der Schlüssel quasararchiv{n:05d} gehört zu Archiv {n}.',
                       message_id=f'msg-{n}', provider_id=f'provider-{n}')

class Classifier:
    is_local = True
    model = 'cpu-synthetic-source-classifier'
    calls = 0
    def complete_json(self, messages, *, max_tokens, schema):
        self.calls += 1
        blocks = json.loads(messages[-1]['content'])['blocks']
        return Reply(text=json.dumps({'items': [{'block_id': b['block_id'], 'kind': 'fact'} for b in blocks]}))

def drain(ep, provider, stand):
    memory = WorkingMemoryStore(ep)
    limit = max(50, memory.progress()['total'] // 100)
    for n in range(limit):
        if memory.progress()['remaining'] == 0:
            return n
        result = run(ep, provider, RLock(), limit=200, stand=stand)
        assert result.ok, result
    raise AssertionError(memory.progress())

def vectorize(cache, limit=None):
    total = 0
    while limit is None or total < limit:
        batch = cache.pending(min(64, limit - total) if limit else 64)
        if not batch.refs:
            return total
        vectors = []
        for ref in batch.refs:
            digest = hashlib.sha256(ref['episode_id'].encode()).digest()
            vectors.append([1.0 if (digest[n] % 2) else -1.0 for n in range(16)])
        total += cache.commit(batch, vectors)
    return total


def run_lifecycle(root, *, size=10000, progress=None):
    resources = []
    try:
        return _run_lifecycle(root, size=size, progress=progress, resources=resources)
    finally:
        for resource in reversed(resources):
            resource.close()


def _run_lifecycle(root, *, size, progress, resources):
    if type(size) is not int or size < 64:
        raise ValueError('sources must be an integer >= 64')
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    log = lambda kind, **values: progress({'step': kind, **values}) if progress else None
    started = time.perf_counter()
    report = {'suite': 'memory-core-lifecycle-v2',
              'synthetic_only': True, 'network_used': False, 'llm_called': False,
              'embedding_quality_tested': False, 'assertions': {}}
    path = root / 'episodes.sqlite3'
    assert not path.exists(), 'Never silently reuse a former corpus.'
    ep = EpisodeStore(path)
    resources.append(ep)
    intake, reader, provider, stand = Intake(ep), Reader(size), Classifier(), Zwischenstand()
    intake.start('synthetic-account', ['INBOX'])
    for tick in range(max(100, size // 10)):
        intake.step('synthetic-account', reader, batch=50)
        result = run(ep, provider, RLock(), limit=200, stand=stand)
        assert result.ok
        if tick == max(1, size // 400):
            count = ep._conn.execute('SELECT count(*) FROM episodes').fetchone()[0]
            saved = WorkingMemoryStore(ep).progress()
            ep.close()
            ep = EpisodeStore(path)
            resources.append(ep)
            intake, stand = Intake(ep), Zwischenstand()
            assert ep._conn.execute('SELECT count(*) FROM episodes').fetchone()[0] == count
            assert WorkingMemoryStore(ep).progress() == saved
            log('restart', originals=count, progress=saved)
        if tick % 25 == 0:
            log('intake', tick=tick, reads=reader.reads, classified=provider.calls)
        row = intake.status('synthetic-account')['folders'][0]
        if row['inventory_complete'] and row['pending'] == 0:
            break
    else:
        raise AssertionError('Intake did not finish in bounded ticks')
    assert row['total'] == size and row['captured'] == size - 1 and row['failed'] == 1, row
    # The real intake deliberately waits above 200 unclassified history
    # sources. Drain that backlog before releasing the queued fetch retry.
    drain(ep, provider, stand)
    reader.fail = set()
    intake.retry('synthetic-account')
    intake.step('synthetic-account', reader, batch=50)
    drain(ep, provider, stand)
    row = intake.status('synthetic-account')['folders'][0]
    assert row['captured'] == size and row['pending'] == 0 and row['failed'] == 0, row
    memory = WorkingMemoryStore(ep)
    assert memory.progress() == dict(total=size, done=size, skipped=0, retry=0, remaining=0)
    assert provider.calls == size
    assert ep._conn.execute('SELECT count(*) FROM episodes').fetchone()[0] == size
    assert check_mail_payloads(ep, range(1, size + 1)) == size
    initial_originals = original_inventory(ep)
    preserved_checks = {'full_intake': inventory_digest(initial_originals)}
    report['assertions']['full_intake_restart_transport_retry'] = {'passed': True, 'ticks': tick + 1,
                                                                 'classification_calls': provider.calls}
    log('all_classified', progress=memory.progress())

    # Replaying the same provider IDs through a second label preserves originals and classifications.
    intake.start('synthetic-account', ['INBOX', 'Archive'])
    for _ in range(max(35, reader.label_count // 20)):
        intake.step('synthetic-account', reader, batch=50)
    state = intake.status('synthetic-account')
    archive = next(r for r in state['folders'] if r['folder'] == 'Archive')
    assert archive['duplicates'] == reader.label_count and archive['captured'] == 0, archive
    check_inventory(ep, initial_originals)
    preserved_checks['label_replay'] = inventory_digest(initial_originals)
    drain(ep, provider, stand)
    assert provider.calls == size
    assert ep._conn.execute('SELECT count(*) FROM episodes').fetchone()[0] == size
    report['assertions']['cross_label_duplicates'] = {'passed': True, 'duplicates': reader.label_count, 'extra_classification_calls': 0}

    # Durable vectors survive interruption without embedding completed sources again.
    cache = DurableSemanticIndex(ep, 'cpu-test:' + 'a' * 64)
    resources.append(cache)
    assert vectorize(cache, size // 2) == size // 2
    cache.close(); ep.close()
    ep = EpisodeStore(path)
    resources.append(ep)
    memory, intake, stand = WorkingMemoryStore(ep), Intake(ep), Zwischenstand()
    cache = DurableSemanticIndex(ep, 'cpu-test:' + 'a' * 64)
    resources.append(cache)
    assert cache.coverage()['indexed'] == size // 2
    check_inventory(ep, initial_originals)
    preserved_checks['vector_restart'] = inventory_digest(initial_originals)
    assert vectorize(cache) == size - size // 2
    assert cache.coverage()['indexed'] == size and cache.coverage()['pending'] == 0
    report['assertions']['durable_vector_restart'] = {'passed': True, 'first': size // 2, 'after_restart': size - size // 2, 'total': size}

    # Late live arrivals are accepted and classified once without replaying the historic bank.
    reader.count = size + 10
    intake.step('synthetic-account', reader, batch=50)
    drain(ep, provider, stand)
    assert provider.calls == size + 10
    assert vectorize(cache) == 10
    with_arrivals = check_inventory(ep, initial_originals, exact=False)
    new_original_ids = set(with_arrivals) - set(initial_originals)
    assert len(new_original_ids) == 10
    assert check_mail_payloads(ep, range(size + 1, size + 11)) == 10
    preserved_checks['new_arrivals'] = inventory_digest(
        {identifier: with_arrivals[identifier] for identifier in initial_originals})
    report['assertions']['incremental_arrivals'] = {'passed': True, 'new': 10, 'extra_classification_calls': 10, 'extra_vectors': 10}

    # Source replacement immediately invalidates old lexical/vector evidence, even before new indexing.
    old_ref = memory.search('quasararchiv00001')['refs'][0]
    old = ep.get(old_ref['episode_id'])
    key = ep._conn.execute('SELECT source_key FROM episodes WHERE id=?', (old.id,)).fetchone()[0]
    updated, created = ep.record(old.kind, old.title, 'Der neue Schlüssel supersedingquasar gehört zu Archiv 1.',
                                 old.provenance, source_key=key, participants=old.participants,
                                 occurred_at=old.occurred_at, at=AT)
    assert created
    ep.advance_source_head(key, old.id, updated.id)
    assert memory.resolve(old_ref) is None
    assert memory.search('quasararchiv00001')['refs'] == []
    assert ep.get(old.id).body == old.body
    with_replacement = check_inventory(ep, with_arrivals, exact=False)
    assert set(with_replacement) - set(with_arrivals) == {updated.id}
    assert ep.get(updated.id).body == 'Der neue Schlüssel supersedingquasar gehört zu Archiv 1.'
    preserved_checks['source_replacement'] = inventory_digest(
        {identifier: with_replacement[identifier] for identifier in initial_originals})
    drain(ep, provider, stand)
    assert provider.calls == size + 11
    assert memory.search('supersedingquasar')['refs'][0]['episode_id'] == updated.id
    assert vectorize(cache) == 1
    assert cache.coverage()['indexed'] == size + 10
    report['assertions']['replacement_preserves_old_original_invalidates_old_ref'] = {'passed': True, 'extra_classification_calls': 1, 'extra_vectors': 1}

    # Explicit withdrawal is immediate and remains through database restart.
    withdrawing = memory.search('quasararchiv00002')['refs'][0]
    ep.ignore(withdrawing['episode_id'])
    assert memory.resolve(withdrawing) is None
    assert memory.search('quasararchiv00002')['refs'] == []
    assert ep.get(withdrawing['episode_id']).body
    cache.close(); ep.close()
    ep = EpisodeStore(path)
    resources.append(ep)
    assert WorkingMemoryStore(ep).resolve(withdrawing) is None
    assert WorkingMemoryStore(ep).search('quasararchiv00002')['refs'] == []
    assert ep._conn.execute('PRAGMA quick_check').fetchone()[0] == 'ok'
    log('before_final_preservation_check')
    final_originals = check_inventory(ep, with_replacement)
    preserved_checks['withdrawal_restart'] = inventory_digest(
        {identifier: final_originals[identifier] for identifier in initial_originals})
    assert len(set(preserved_checks.values())) == 1
    report['original_preservation'] = {
        'all_initial_payloads_checked': size,
        'initial_original_sha256': inventory_digest(initial_originals),
        'initial_inventory_by_stage': preserved_checks,
        'new_mail_payloads_checked': 10,
        'replacement_originals_checked': 1,
        'final_original_count': len(final_originals),
        'all_originals_preserved': True,
        'scope': 'body, digest, identity, origin, timestamps, participants, contacts; all stored versions'}
    report['assertions']['withdrawal_restart_original_preserved'] = {'passed': True}
    report['final_progress'] = WorkingMemoryStore(ep).progress()
    report['source_count'] = ep._conn.execute('SELECT count(*) FROM episodes').fetchone()[0]
    report['seconds'] = round(time.perf_counter() - started, 3)
    ep.close()

    log('finished', **report)
    return report


def main():
    import argparse
    import tempfile
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=int, default=10000)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Existing evidence must not be overwritten')
    with tempfile.TemporaryDirectory(prefix='kingfisher-core-lifecycle-') as root:
        report = run_lifecycle(root, size=args.sources,
            progress=lambda event: print(json.dumps(event), flush=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
