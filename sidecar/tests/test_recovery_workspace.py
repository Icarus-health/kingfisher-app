"""Synthetic recovery copies must preserve records without inheriting authority."""
import hashlib
import importlib
import json
import sqlite3
import stat

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory import config
from icarus_memory.identitaet import eigene_adressen
from icarus_memory.mac_calendar import MacCalendar
from icarus_memory.procedures import ProcedureStore
from icarus_memory.recovery_preflight import preflight
from icarus_memory.regeln import RegelStore
from icarus_memory.restore_boundary import mark_pending
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore
from icarus_memory.workspace_views import WorkspaceViews

STAMP = '20261104T120000Z'


@pytest.fixture
def tmp_path(tmp_path):
    # macOS /tmp is a symlink; the contract intentionally requires real paths.
    return tmp_path.resolve()


def api():
    return importlib.import_module('icarus_memory.recovery_workspace')


def hashes(folder):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.iterdir() if p.is_file() and not p.is_symlink()}


def skill(**changes):
    return dict(name='synthetic-review', title='Künstlichen Entwurf prüfen',
                description='Einen Entwurf anhand seiner Belege prüfen.', area='mail',
                triggers=['belegprüfung'], steps=['Zuerst die Belege prüfen.'],
                positive='Schreibe eine Mail für die Belegprüfung.', negative='Schreibe eine private Urlaubsmail.', **changes)


@pytest.fixture
def rich(tmp_path):
    folder = tmp_path / 'historical'
    folder.mkdir()
    provenance = Provenance(source_type=SourceType.USER_STATED)
    episodes = EpisodeStore(folder / 'episodes.sqlite3')
    source, _ = episodes.record(EpisodeKind.DOCUMENT, 'Künstliche Quelle', 'Unveränderter Originaltext.', provenance)
    ignored, _ = episodes.record(EpisodeKind.DOCUMENT, 'Entzogene Quelle', 'Zurückgezogener Beispieltext.', provenance)
    episodes.ignore(ignored.id)
    episodes.close()
    workspace = WorkspaceStore(folder / 'workspace.sqlite3')
    project = workspace.add_project('Künstliches Projekt', provenance)
    workspace.close()
    tasks = TaskStore(folder / 'tasks.sqlite3')
    task = tasks.add('Künstliche Aufgabe', provenance, project_id=project.id)
    tasks.auto_setzen(True)
    tasks.close()
    procedures = ProcedureStore(folder / 'procedures.sqlite3')
    previous = procedures.propose(skill())
    procedures.accept(previous['id'])
    active = procedures.propose({**skill(), 'steps': ['Belege und Entwurf getrennt prüfen.']})
    procedures.accept(active['id'])
    pending = procedures.propose({**skill(), 'steps': ['Belege lesen und offene Fragen markieren.']})
    revoked = procedures.propose({**skill(), 'name': 'revoked-review'})
    procedures.accept(revoked['id']); procedures.revoke(revoked['id'])
    rejected = procedures.propose({**skill(), 'name': 'rejected-review'})
    procedures.reject(rejected['id'])
    originals = {entry['id']: procedures.get(entry['id']) for entry in (previous, active, pending, revoked, rejected)}
    procedures.close()
    rules = RegelStore(folder / 'regeln.sqlite3')
    rule = rules.anlegen('Künstliche Dauerfreigabe', 'synthetic', 'auto')
    old_rule = rules.anlegen('Schon widerrufen', 'synthetic-old', 'auto')
    old_rule = rules.widerrufen(old_rule.id)
    rules.close()
    calendar = MacCalendar(folder / 'mac-calendar.sqlite3')
    calendar.change(lambda s: s.update(enabled=True, authorize=True, generation=7, status='granted',
                                      selected=['synthetic-cal'], calendars=[{'id': 'synthetic-cal', 'title': 'Beispiel'}],
                                      events=[{'uid': 'synthetic-event', 'title': 'Gespeicherter Termin'}]))
    views = WorkspaceViews(folder / 'workspace-views.sqlite3')
    views.put('folder', 'local-folder', {'name': 'Lokale Ablage', 'parent_id': None}, 0)
    views.put('preferences', 'online', {'logos': True, 'maps': True}, 0)
    views.close()
    settings = config.Settings.from_dict({
        'provider': 'anthropic', 'model': 'old-model', 'endpoint': 'https://example.invalid',
        'mail': {'imap_host': 'mail.example.invalid', 'user': 'legacy@example.invalid', 'sender': 'legacy@example.invalid'},
        'calendar': {'url': 'https://example.invalid/cal', 'user': 'calendar@example.invalid'},
        'mail_accounts': [{'id': 'mail-one', 'user': 'own@example.invalid', 'sender': 'own@example.invalid', 'imap_host': 'mail.example.invalid', 'enabled': True}],
        'calendar_sources': [{'id': 'cal-one', 'user': 'other@example.invalid', 'url': 'https://example.invalid/cal', 'enabled': True}],
        'schedule': {'enabled': True, 'with_model': True, 'sources': {'/private/data': 'files'}},
        'mcp_server': [{'name': 'unsafe', 'command': 'never-execute'}], 'file_roots': ['/private/data'],
        'folder_sync': {'enabled': True}, 'transcript_sync': {'enabled': True},
        'routing_enabled': True, 'model_roles': {'answer': {'consent': True}},
        'cloud_models': {'mistral': 'old'}, 'world_sources': [{'url': 'https://example.invalid/feed'}],
        'wetter': {'aktiv': True}, 'wegezeit': {'aktiv': True}, 'welt': {'aktiv': True},
        'akten_export': {'aktiv': True, 'ordner': '/private/export'}, 'mitteilungen': {'an': True},
        'konten': {'eigene': [{'id': 'club', 'name': 'Verein'}], 'bereich_je_konto': {'mail-one': 'club'}},
        'einrichtung': {'name': 'Künstlicher Name', 'abgeschlossen': True}, 'onboarded': True,
    })
    config.save(folder, settings)
    (folder / 'schluessel.icarus').write_bytes(b'synthetic-old-secrets-do-not-copy')
    (folder / '.kingfisher.env').write_text('OPENAI_API_KEY=synthetic-do-not-copy\n')
    with sqlite3.connect(folder / 'cloud-memory-jobs.sqlite3') as conn:
        conn.execute('CREATE TABLE history(id TEXT PRIMARY KEY, status TEXT)')
        conn.execute("INSERT INTO history VALUES ('historical-job','complete')")
    mark_pending(folder, 'synthetic-working-copy-test')
    return dict(folder=folder, source=source, ignored=ignored, project=project, task=task,
                active=active, originals=originals, old_rule=old_rule, rule=rule, settings=settings)


def prepare(rich, target, **changes):
    return api().prepare_working_copy(rich['folder'], target,
        **({'fingerprint': preflight(rich['folder'])['report_fingerprint'], 'selection': 'restored',
            'acknowledge_unknown': True} | changes))


def test_working_copy_preserves_records_and_resets_only_execution_authority(rich, tmp_path):
    before = hashes(rich['folder'])
    target = prepare(rich, tmp_path / 'working')
    data = target / 'data'
    assert hashes(rich['folder']) == before
    assert not (data / 'schluessel.icarus').exists()
    assert not (data / '.kingfisher.env').exists()
    episodes = EpisodeStore(data / 'episodes.sqlite3')
    assert episodes.get(rich['source'].id).to_dict() == rich['source'].to_dict()
    assert episodes.get(rich['ignored'].id).state.value == 'ignored'
    episodes.close()
    workspace = WorkspaceStore(data / 'workspace.sqlite3')
    assert workspace.project(rich['project'].id).to_dict() == rich['project'].to_dict()
    workspace.close()
    tasks = TaskStore(data / 'tasks.sqlite3')
    assert tasks.get(rich['task'].id).to_dict() == rich['task'].to_dict()
    assert tasks.auto_an() is False
    created = tasks.add('Nach der Wiederherstellung', Provenance(source_type=SourceType.USER_STATED))
    tasks.close()
    tasks = TaskStore(data / 'tasks.sqlite3')
    assert tasks.get(created.id).title == 'Nach der Wiederherstellung'
    tasks.close()
    procedures = ProcedureStore(data / 'procedures.sqlite3')
    for identifier, original in rich['originals'].items():
        actual = procedures.get(identifier)
        if identifier == rich['active']['id']:
            assert actual['state'] == 'pending' and actual['base_version'] == 1
            for field in ('id', 'version', 'markdown', 'created_at', 'sources'):
                assert actual[field] == original[field]
        else:
            assert actual == original
    assert not procedures.select('Schreibe eine Mail für die Belegprüfung.', area='mail')['contextual']
    procedures.accept(rich['active']['id'])
    procedures.close()
    procedures = ProcedureStore(data / 'procedures.sqlite3')
    assert procedures.get(rich['active']['id'])['state'] == 'active'
    procedures.close()
    rules = RegelStore(data / 'regeln.sqlite3')
    assert not rules.alle(nur_aktive=True)
    assert rules.holen(rich['old_rule'].id).widerrufen_am == rich['old_rule'].widerrufen_am
    rules.close()
    calendar = MacCalendar(data / 'mac-calendar.sqlite3').read()
    assert calendar['enabled'] is False and calendar['authorize'] is False
    assert calendar['status'] == 'offline' and calendar['generation'] == 8
    assert calendar['events'][0]['uid'] == 'synthetic-event' and calendar['selected'] == ['synthetic-cal']
    views = WorkspaceViews(data / 'workspace-views.sqlite3')
    assert views.get('preferences', 'online')['data'] == {'logos': False, 'maps': False}
    assert views.get('folder', 'local-folder')['data']['name'] == 'Lokale Ablage'
    views.close()
    assert (data / 'cloud-memory-jobs.sqlite3').read_bytes() == (rich['folder'] / 'cloud-memory-jobs.sqlite3').read_bytes()
    assert hashes(rich['folder']) == before


def test_settings_keep_own_identity_without_old_permissions(rich, tmp_path):
    data = prepare(rich, tmp_path / 'working') / 'data'
    clean = config.load(data)
    assert eigene_adressen(clean) == eigene_adressen(rich['settings'])
    assert not clean.mail.configured and not clean.calendar.configured
    assert clean.mail_accounts and all(not a.enabled for a in clean.mail_accounts)
    assert clean.calendar_sources and all(not a.enabled for a in clean.calendar_sources)
    assert clean.konten == rich['settings'].konten
    for field in ('provider', 'model', 'endpoint', 'file_roots', 'mcp_server', 'routing_enabled',
                  'routing_profiles', 'model_roles', 'cloud_models', 'folder_sync', 'transcript_sync',
                  'world_sources', 'wetter', 'wegezeit', 'welt', 'akten_export', 'mitteilungen'):
        assert not getattr(clean, field), field
    assert not clean.schedule.enabled and not clean.schedule.with_model
    assert not clean.schedule.sources and not clean.schedule.mail_accounts
    assert json.loads((data / 'fassung.json').read_text())['pruefen'] is False


def test_selected_group_is_used_without_fallback_or_merging(rich, tmp_path):
    root = rich['folder']
    # The chosen group has only one DB. Other restored records must not leak into it.
    group_tasks = root / f'tasks.vor-wiederherstellung-{STAMP}.sqlite3'
    store = TaskStore(group_tasks)
    selected = store.add('Explizit gewählter Vergleichsstand', Provenance(source_type=SourceType.USER_STATED))
    store.close()
    before = hashes(root)
    target = prepare(rich, tmp_path / 'group-working', selection=STAMP)
    tasks = TaskStore(target / 'data/tasks.sqlite3')
    assert tasks.get(selected.id) is not None
    assert tasks.get(rich['task'].id) is None
    tasks.close()
    assert not (target / 'data/episodes.sqlite3').exists()
    contract = api().read_working_contract(target / 'data')
    assert contract['selection'] == STAMP
    receipt = json.loads((target / 'recovery-receipt.json').read_text())
    assert 'episodes.sqlite3' in receipt['missing_files']
    assert hashes(root) == before


@pytest.mark.parametrize('changes', [
    {'fingerprint': '0' * 64}, {'selection': '20250101T000000Z'},
    {'selection': '../escape'}, {'acknowledge_unknown': False}, {'acknowledge_unknown': 1},
])
def test_missing_consent_fingerprint_or_selection_never_publishes(rich, tmp_path, changes):
    before = hashes(rich['folder']); target = tmp_path / 'not-published'
    with pytest.raises(ValueError):
        prepare(rich, target, **changes)
    assert not target.exists() and hashes(rich['folder']) == before


@pytest.mark.parametrize('fault', ['symlink', 'sidecar', 'corrupt', 'directory'])
def test_ambiguous_present_area_is_never_skipped(rich, tmp_path, fault):
    root = rich['folder']; bad = root / 'knowledge.sqlite3'
    if fault == 'symlink': bad.symlink_to(root / 'episodes.sqlite3')
    elif fault == 'sidecar': (root / 'tasks.sqlite3-wal').write_bytes(b'ambiguous')
    elif fault == 'corrupt': bad.write_bytes(b'not-a-database')
    else: bad.mkdir()
    before = hashes(root)
    with pytest.raises(ValueError): prepare(rich, tmp_path / 'not-published')
    assert not (tmp_path / 'not-published').exists() and hashes(root) == before


def test_target_existing_inside_source_or_symlink_is_rejected(rich, tmp_path):
    existing = tmp_path / 'existing'; existing.mkdir(); (existing / 'keep').write_text('keep')
    alias = tmp_path / 'alias'; alias.symlink_to(rich['folder'], target_is_directory=True)
    for target in (existing, rich['folder'] / 'nested', alias / 'nested'):
        with pytest.raises(ValueError): prepare(rich, target)
    assert (existing / 'keep').read_text() == 'keep'
    assert not (rich['folder'] / 'nested').exists()


def test_reset_failure_and_changed_source_leave_no_published_target(rich, tmp_path, monkeypatch):
    module = api(); original = module._reset_permissions
    before = hashes(rich['folder'])
    def fail(_): raise OSError('synthetic reset failure')
    monkeypatch.setattr(module, '_reset_permissions', fail)
    with pytest.raises((ValueError, OSError)): prepare(rich, tmp_path / 'failed')
    assert not (tmp_path / 'failed').exists() and hashes(rich['folder']) == before
    def changed(data):
        original(data)
        with sqlite3.connect(rich['folder'] / 'tasks.sqlite3') as conn:
            conn.execute("UPDATE tasks SET title='Externally changed synthetic task'")
    monkeypatch.setattr(module, '_reset_permissions', changed)
    with pytest.raises(ValueError): prepare(rich, tmp_path / 'changed')
    assert not (tmp_path / 'changed').exists()
    assert not list(tmp_path.glob('.*.staging-*'))


def test_copy_error_cleans_staging_and_does_not_change_the_original(rich, tmp_path, monkeypatch):
    module = api(); original = module._copy_verified; before = hashes(rich['folder'])
    def interrupted(source, destination, evidence):
        original(source, destination, evidence)
        raise OSError('synthetic copy interruption')
    monkeypatch.setattr(module, '_copy_verified', interrupted)
    with pytest.raises(OSError): prepare(rich, tmp_path / 'failed-copy')
    assert not (tmp_path / 'failed-copy').exists()
    assert not list(tmp_path.glob('.*.staging-*'))
    assert hashes(rich['folder']) == before


def test_target_created_during_preparation_is_never_replaced(rich, tmp_path, monkeypatch):
    module = api(); publish = module._publish; target = tmp_path / 'racing-target'
    def concurrent_target(stage, destination):
        target.mkdir()
        publish(stage, destination)
    monkeypatch.setattr(module, '_publish', concurrent_target)
    with pytest.raises(OSError): prepare(rich, target)
    assert target.is_dir() and list(target.iterdir()) == []
    assert not list(tmp_path.glob('.*.staging-*'))


def test_source_directory_alias_never_qualifies_as_reviewed_source(rich, tmp_path):
    alias = tmp_path / 'source-alias'; alias.symlink_to(rich['folder'], target_is_directory=True)
    with pytest.raises(ValueError):
        api().prepare_working_copy(alias, tmp_path / 'failed', fingerprint=preflight(rich['folder'])['report_fingerprint'],
                                  selection='restored', acknowledge_unknown=True)
    assert not (tmp_path / 'failed').exists()


def test_contract_environment_and_private_receipt_are_bound_to_the_copy(rich, tmp_path, monkeypatch):
    module = api(); target = prepare(rich, tmp_path / "working copy 'quoted' $(never-execute)")
    contract = module.read_working_contract(target / 'data')
    assert set(contract) == {'version', 'mode', 'policy_version', 'restore_id', 'source_fingerprint',
                             'selection', 'unknown_history_acknowledged', 'permissions_reset', 'operational'}
    assert contract['mode'] == 'working_copy' and contract['operational'] is True
    assert contract['source_fingerprint'] == preflight(rich['folder'])['report_fingerprint']
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'synthetic-old-key')
    monkeypatch.setenv('HTTPS_PROXY', 'https://example.invalid')
    monkeypatch.setenv('KINGFISHER_MCP_TUER', '1')
    monkeypatch.setenv('OTEL_EXPORTER_OTLP_ENDPOINT', 'https://example.invalid')
    monkeypatch.setenv('LC_ALL', 'C')
    env = module.launch_environment(target)
    assert env['LC_ALL'] == 'C'
    assert env['ICARUS_DATA_DIR'] == str(target / 'data')
    assert "$(never-execute)" in env['ICARUS_DATA_DIR']
    assert env['ICARUS_RECOVERY_BOOT_ID'] == contract['restore_id']
    assert not any(k in env for k in ('ANTHROPIC_API_KEY', 'HTTPS_PROXY', 'KINGFISHER_MCP_TUER', 'OTEL_EXPORTER_OTLP_ENDPOINT'))
    assert module.boot_allowed(target / 'data', env)
    for key in ('HTTPS_PROXY', 'ICARUS_PROVIDER', 'ICARUS_MAIL_HOST', 'HARNESS_PORT', 'KINGFISHER_MCP_TUER', 'OTEL_EXPORTER_OTLP_ENDPOINT'):
        assert not module.boot_allowed(target / 'data', env | {key: 'synthetic'})
    assert not module.boot_allowed(target / 'data', env | {'ICARUS_RECOVERY_BOOT_ID': '0' * 32})
    assert not module.boot_allowed(target / 'data', env | {'ICARUS_DATA_DIR': str(rich['folder'])})
    assert not module.boot_allowed(target / 'data', env | {'ICARUS_SECRETS_PASSPHRASE': 'different'})
    incomplete = dict(env); del incomplete['ICARUS_SIDECAR_TOKEN']
    assert not module.boot_allowed(target / 'data', incomplete)
    for name in ('settings.env', 'recovery-receipt.json'):
        assert stat.S_IMODE((target / name).stat().st_mode) == 0o600
    receipt = json.loads((target / 'recovery-receipt.json').read_text())
    assert receipt['reset_counts']['skills'] == 1 and receipt['reset_counts']['rules'] == 1
    assert 'Unveränderter Originaltext' not in json.dumps(receipt)
    assert 'synthetic-old-secrets' not in json.dumps(receipt)
    second = prepare(rich, tmp_path / 'another')
    other = module.launch_environment(second)
    assert env['ICARUS_SIDECAR_TOKEN'] != other['ICARUS_SIDECAR_TOKEN']
    assert env['ICARUS_SECRETS_PASSPHRASE'] != other['ICARUS_SECRETS_PASSPHRASE']
    assert env['ICARUS_RECOVERY_BOOT_ID'] != other['ICARUS_RECOVERY_BOOT_ID']


@pytest.mark.parametrize('fault', ['extra', 'version-bool', 'missing', 'false-consent', 'bad-id', 'oversized', 'duplicate', 'deeply-nested', 'symlink'])
def test_invalid_working_contract_never_grants_boot(rich, tmp_path, fault):
    module = api(); target = prepare(rich, tmp_path / 'working'); data = target / 'data'
    marker = data / 'restore-state.json'; env = module.launch_environment(target)
    contract = json.loads(marker.read_text())
    if fault == 'extra': contract['allow_cloud'] = True
    elif fault == 'version-bool': contract['version'] = True
    elif fault == 'missing': del contract['permissions_reset']
    elif fault == 'false-consent': contract['unknown_history_acknowledged'] = False
    elif fault == 'bad-id': contract['restore_id'] = '../outside'
    if fault == 'oversized': marker.write_text(' ' * 8193)
    elif fault == 'duplicate': marker.write_text(json.dumps(contract)[:-1] + ',"version":1}')
    elif fault == 'deeply-nested': marker.write_text('[' * 4000 + '0' + ']' * 4000)
    elif fault == 'symlink':
        destination = target / 'other.json'; marker.rename(destination); marker.symlink_to(destination)
    else: marker.write_text(json.dumps(contract))
    assert module.read_working_contract(data) is None
    assert not module.boot_allowed(data, env)


def test_decoder_recursion_failure_stays_closed(tmp_path, monkeypatch):
    module = api()
    (tmp_path / 'restore-state.json').write_text('{}')
    def exhausted(*args, **kwargs):
        raise RecursionError('synthetic decoder limit')
    monkeypatch.setattr(module.json, 'loads', exhausted)
    assert module.read_working_contract(tmp_path) is None


def test_launch_file_is_closed_private_and_never_shell_evaluated(rich, tmp_path):
    module = api(); target = prepare(rich, tmp_path / 'working')
    settings = target / 'settings.env'; original = settings.read_text()
    for addition in ('\nHTTPS_PROXY=https://example.invalid\n', '\nICARUS_RECOVERY_BOOT_ID=duplicate\n', '\nexport EXTRA=1\n'):
        settings.write_text(original + addition)
        with pytest.raises(ValueError): module.launch_environment(target)
    settings.write_text(original); settings.chmod(0o644)
    with pytest.raises(ValueError): module.launch_environment(target)
    settings.chmod(0o600); elsewhere = target / 'elsewhere.env'; settings.rename(elsewhere); settings.symlink_to(elsewhere)
    with pytest.raises(ValueError): module.launch_environment(target)


def test_no_database_cannot_become_an_operational_copy(tmp_path):
    source = tmp_path / 'historical'; source.mkdir(); mark_pending(source, 'synthetic')
    config.save(source, config.Settings())
    with pytest.raises(ValueError):
        api().prepare_working_copy(source, tmp_path / 'empty', fingerprint=preflight(source)['report_fingerprint'],
                                  selection='restored', acknowledge_unknown=True)
    assert not (tmp_path / 'empty').exists()
