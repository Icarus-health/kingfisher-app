from datetime import datetime
from hashlib import sha256
import importlib
import json
import os
import socket
from pathlib import Path
import shutil

import pytest

FIXTURE = Path(__file__).resolve().parents[1] / 'docs/fixtures/memory-acceptance-20261104/heldout-v2'
FREEZE_SHA = '5f9e54252b0513d58dffaa0e943e471431e0f3759866af171f559b37e289a39e'


@pytest.fixture
def adapter():
    return importlib.import_module('memory_acceptance_intake')


@pytest.mark.parametrize('filename, change', [
    ('freeze.json', 'changed'),
    ('sources.json', 'omitted'),
    ('native/erle-sichtpruefung-absage.ics', 'changed'),
    ('native/erlenhof-aufgaben.pdf', 'omitted'),
    ('reference.json', 'changed'),
    ('extra.txt', 'extra'),
])
def test_admission_rejects_changes_and_omissions_before_import(adapter, tmp_path, filename, change):
    corpus = tmp_path / 'corpus'
    shutil.copytree(FIXTURE, corpus)
    path = corpus / filename
    if change == 'omitted':
        path.unlink()
    else:
        if path.exists():
            path.chmod(0o600)
        path.write_bytes(b'{}')
    with pytest.raises(ValueError, match=filename.replace('.', r'\.')):
        adapter.load_frozen_sources(corpus)


def test_source_loading_treats_grader_artifacts_as_opaque(adapter, monkeypatch):
    real_loads = json.loads
    opaque = {(FIXTURE / name).read_text() for name in ('reference.json', 'catalog.json', 'state-phases.json')}

    def loads(value, *args, **kwargs):
        if isinstance(value, bytes):
            value = value.decode()
        assert value not in opaque
        return real_loads(value, *args, **kwargs)

    monkeypatch.setattr(json, 'loads', loads)
    corpus = adapter.load_frozen_sources(FIXTURE)
    assert corpus.freeze_sha256 == FREEZE_SHA
    assert corpus.owner_address == 'jona@atelier-kiesel.example'


def test_loaded_sources_cannot_be_changed_below_the_top_level(adapter):
    corpus = adapter.load_frozen_sources(FIXTURE)
    with pytest.raises(TypeError):
        corpus.mail[0]['sender']['address'] = 'changed@sender.example'
    with pytest.raises(TypeError):
        corpus.mail[0]['recipients'][0]['name'] = 'Changed'
    with pytest.raises(TypeError):
        corpus.mail[0]['recipients'][0] = {}
    with pytest.raises(TypeError):
        corpus.native[0]['attachments'][0] = 'N04'


def test_baseline_reads_frozen_sources_through_product_paths(adapter, tmp_path, monkeypatch):
    from icarus_memory import server
    from icarus_memory.anhaenge import gespeicherter_bericht
    from icarus_memory.connectors import calendar
    from icarus_memory.episodes import EpisodeState

    def forbidden(*args, **kwargs):
        pytest.fail('Offline preparation tried to access the host keychain or start the scheduler.')

    monkeypatch.setattr(server, 'Keychain', forbidden)
    monkeypatch.setattr('icarus_memory.scheduler.Scheduler.start', forbidden)
    monkeypatch.setenv('OPENAI_API_KEY', 'must-not-enter-the-instance')
    corpus = adapter.load_frozen_sources(FIXTURE)
    parse_events = calendar.parse_events
    baseline_ics = (FIXTURE / 'native/erle-sichtpruefung.ics').read_bytes()

    def baseline_only(raw, *args, **kwargs):
        assert raw == baseline_ics
        return parse_events(raw, *args, **kwargs)

    before = {p: sha256(p.read_bytes()).hexdigest() for p in FIXTURE.rglob('*') if p.is_file()}
    source_rows = json.loads((FIXTURE / 'sources.json').read_bytes())
    with adapter.source_only_instance(corpus, directory=tmp_path) as instance, \
            monkeypatch.context() as during_baseline:
        # Erst nach dem Instanzaufbau ersetzen. Dieser importiert das Paket
        # vorab, damit die eingefrorene Uhr in allen Produktmodulen gilt.
        during_baseline.setattr(calendar, 'parse_events', baseline_only)
        assert 'OPENAI_API_KEY' not in os.environ
        report = adapter.prepare_baseline(instance, corpus)
        receipts = {r['fixture_id']: r for r in report['receipts']}
        assert len(receipts) == 110
        assert report['product_quality'] == 'NOT EVALUATED'
        assert report['bulk_import_authorized'] is False
        assert receipts['N06']['coverage'] == 'withheld'
        assert receipts['N06']['episodes'] == []
        assert report['coverage'] == {'admitted': 105, 'partial': 4, 'withheld': 1}

        def episode(fixture_id):
            [row] = receipts[fixture_id]['episodes']
            return instance.episodes.get(row['id'])

        for source in source_rows['mails']:
            receipt = receipts[source['id']]
            mail = episode(source['id'])
            assert receipt['coverage'] == 'admitted'
            assert receipt['mail_folder'] == source['folder']
            assert receipt['wire_sha256']
            assert mail.title == source['title']
            assert mail.occurred_at == datetime.fromisoformat(source['at'])
            assert mail.recorded_at == corpus.clock
            assert mail.body.rstrip('\n') == source['body']
            assert {(c['rolle'], c['adresse']) for c in mail.contacts} == {
                ('von', source['sender']['address']), *(('an', r['address']) for r in source['recipients']),
            }
            assert any(c['ich'] and c['adresse'] == corpus.owner_address for c in mail.contacts)
            assert mail.provenance.source_ref.endswith(f'<{source["id"]}@messlatte.example>')
        assert episode('E01-03').contacts[0]['ich'] is True
        with instance.episodes._lock:
            transport_rows = {r['episode_id']: (r['account'], r['folder'], r['uid'], r['generation'])
                              for r in instance.episodes._conn.execute(
                                  'SELECT episode_id,account,folder,uid,generation FROM mail_intake_items')}
        assert len(transport_rows) == 102
        for row in report['receipts']:
            for stored in row['episodes']:
                snap = instance.episodes.support_snapshot(stored['id'])
                if row['fixture_id'] == 'N10':
                    assert stored['source_key'] is None
                    assert stored['source_key_status'] == 'unversioned'
                else:
                    assert stored['source_key'] == snap.source_key
                    assert stored['source_key']
                if stored['id'] in transport_rows:
                    transport = row['mail_transport']
                    assert (transport['account_id'], transport['folder'], transport['uid'],
                            transport['uidvalidity']) == transport_rows[stored['id']]
                    assert transport['uidvalidity'] == '1'

        for parent_id, child_id, filename in (
            ('N01', 'N02', 'erle-lizenzbogen.pdf'),
            ('N03', 'N04', 'erlenhof-aufgaben.pdf'),
        ):
            parent, child = episode(parent_id), episode(child_id)
            assert receipts[parent_id]['coverage'] == 'admitted'
            assert receipts[child_id]['coverage'] == 'admitted'
            assert receipts[child_id]['parent_episode_ids'] == [parent.id]
            assert receipts[child_id]['parent_mail_transport'] == receipts[parent_id]['mail_transport']
            assert instance.episodes.mail_attachment_children(parent.id) == [child.id]
            assert receipts[child_id]['embedded_sha256'] == before[FIXTURE / 'native' / filename]
            assert child.provenance.source_ref.startswith(parent.provenance.source_ref + '#anhang:')
            assert gespeicherter_bericht(parent)['vollstaendig'] is True
            assert 'Seite 1' in child.body
            assert child.occurred_at == parent.occurred_at
        assert episode('N03').occurred_at == datetime.fromisoformat('2026-11-03T12:00:00+01:00')

        event = episode('N05')
        assert event.state is EpisodeState.NEW
        assert event.occurred_at == datetime.fromisoformat('2026-11-27T09:00:00+00:00')
        assert 'Bestätigter Termin' in event.body
        assert event.provenance.source_ref.endswith(':erle-visit-1@fixtures.example')
        assert 'Checkliste' in episode('N07').body
        assert 'bestätigte Sprecherzuordnung' in episode('N08').body
        assert 'Sprecher unbekannt' in episode('N09').body
        assert 'Birkensteg' in episode('N10').body
        assert episode('N07').occurred_at is None
        assert episode('N10').occurred_at is None
        for fixture_id in ('N07', 'N08', 'N09', 'N10'):
            assert receipts[fixture_id]['coverage'] == 'partial'
            assert receipts[fixture_id]['original_at'].startswith('2026-11-03')
        assert all(episode(i).occurred_at != corpus.clock for i in ('N05', 'N07', 'N08', 'N09', 'N10'))
        assert all(not item.produced and item.state is EpisodeState.NEW for item in instance.episodes.each_episode())
        ids = {item.id for item in instance.episodes.each_episode()}
        assert len(ids) == 109
        replay = adapter.prepare_baseline(instance, corpus)
        for first, second in zip(report['receipts'], replay['receipts'], strict=True):
            assert first['fixture_id'] == second['fixture_id']
            assert first['episodes'] == second['episodes']
            assert first.get('mail_transport') == second.get('mail_transport')
        assert {item.id for item in instance.episodes.each_episode()} == ids
    assert {p: sha256(p.read_bytes()).hexdigest() for p in before} == before


def test_cli_refuses_nonempty_target_before_starting(adapter, tmp_path):
    sentinel = tmp_path / 'original.txt'
    sentinel.write_text('original')
    with pytest.raises(SystemExit) as error:
        adapter.main(['--target', str(tmp_path)])
    assert error.value.code == 2
    assert list(tmp_path.iterdir()) == [sentinel]


def test_model_invocation_fails_loudly(adapter):
    with pytest.raises(adapter.OfflineViolation, match='Modell'):
        adapter.NoModel().complete([])


def test_socket_attempt_fails_before_dns_or_connection(adapter):
    with adapter.offline_boundary():
        with pytest.raises(adapter.OfflineViolation, match='Netzwerk'):
            socket.getaddrinfo('imap.heldout.example', 993)
        with socket.socket() as sock:
            with pytest.raises(adapter.OfflineViolation, match='Netzwerk'):
                sock.connect(('127.0.0.1', 993))


def test_reply_metadata_passes_through_the_real_mail_reader(adapter):
    from icarus_memory.connectors.mail import MailConfig, MailConnector
    from messlatte.postfach import Postfach, postfach_installieren

    # Der eingefrorene Bestand hat keine ausdrücklichen Reply-Header. Die
    # optionale RFC822-Zuordnung wird deshalb getrennt, ohne Fixture-Änderung geprüft.
    source = {
        'id': 'synthetic-reply',
        'at': '2026-11-03T10:00:00+01:00',
        'folder': 'Sent',
        'sender': {'name': 'Sina Probe', 'address': 'sina@sender.example'},
        'recipients': [{'name': 'Ali Probe', 'address': 'ali@recipient.example'}],
        'cc': [{'name': 'Kim Probe', 'address': 'kim@recipient.example'}],
        'reply_to': 'synthetic-parent',
        'title': 'Antwort',
        'body': 'Eine synthetische Antwort.',
    }
    mailbox = Postfach()
    mailbox.ablegen_mail(adapter._source_mail(source))
    with adapter.offline_boundary(), postfach_installieren(mailbox):
        reader = MailConnector(MailConfig(imap_host='imap.heldout.example', username='sina@sender.example',
                                          password='unbenutzt'))
        message = reader.message_mit_anhaengen('Sent', '1.1')
    assert message.in_reply_to == '<synthetic-parent@messlatte.example>'
    assert message.references == ('<synthetic-parent@messlatte.example>',)
    assert {(r['rolle'], r['adresse']) for r in message.recipients} == {
        ('an', 'ali@recipient.example'), ('cc', 'kim@recipient.example'),
    }


@pytest.mark.parametrize('through_alias', [False, True])
def test_cli_rejects_resolved_target_in_frozen_tree(adapter, tmp_path, monkeypatch, through_alias):
    fixture_copy = tmp_path / 'fixture'
    shutil.copytree(FIXTURE, fixture_copy)
    monkeypatch.setattr(adapter, 'FIXTURE', fixture_copy)
    before = {path.relative_to(fixture_copy) for path in fixture_copy.rglob('*')}
    root = fixture_copy
    if through_alias:
        root = tmp_path / 'alias'
        root.symlink_to(fixture_copy, target_is_directory=True)
    with pytest.raises(SystemExit) as error:
        adapter.main(['--target', str(root / 'native' / 'output')])
    assert error.value.code == 2
    assert {path.relative_to(fixture_copy) for path in fixture_copy.rglob('*')} == before


def test_direct_prepare_rejects_an_instance_with_a_provider(adapter, tmp_path):
    from messlatte.instanz import instanz_starten

    class UnapprovedProvider:
        is_local = True
        name = model = 'synthetic-unapproved'

    corpus = adapter.load_frozen_sources(FIXTURE)
    with instanz_starten(stichtag=corpus.clock, zeitzone=corpus.timezone, verzeichnis=tmp_path,
                         eigene=(corpus.owner_address,), provider=UnapprovedProvider()) as instance:
        with pytest.raises(adapter.OfflineViolation, match='quellengeschützte'):
            adapter.prepare_baseline(instance, corpus)
        assert list(instance.episodes.each_episode()) == []


@pytest.mark.parametrize('attempt', ['Modell', 'Netzwerk'])
def test_direct_prepare_aborts_an_attempt_in_the_product_path(adapter, tmp_path, monkeypatch, attempt):
    from icarus_memory.connectors.mail import MailConnector

    corpus = adapter.load_frozen_sources(FIXTURE)
    with adapter.source_only_instance(corpus, directory=tmp_path) as instance:
        def attempt_from_reader(*args, **kwargs):
            if attempt == 'Modell':
                instance.agent.provider.complete([])
            else:
                with socket.socket() as sock:
                    sock.connect(('127.0.0.1', 993))

        monkeypatch.setattr(MailConnector, 'message_mit_anhaengen', attempt_from_reader)
        with pytest.raises(adapter.OfflineViolation, match=attempt):
            adapter.prepare_baseline(instance, corpus)
        assert list(instance.episodes.each_episode()) == []
