#!/usr/bin/env python3
"""Quellenaufnahme für den eingefrorenen synthetischen Holdout, ohne Modell."""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.parser import BytesParser
from hashlib import sha256
import json
from pathlib import Path
import socket
from types import MappingProxyType
from typing import Mapping
from unittest.mock import patch

FIXTURE = Path(__file__).resolve().parents[1] / 'docs/fixtures/memory-acceptance-20261104/heldout-v2'
FREEZE_SHA = '5f9e54252b0513d58dffaa0e943e471431e0f3759866af171f559b37e289a39e'
ACCOUNT = 'heldout-v2'
CALENDAR = 'heldout-v2-ics'
MAIL_PATH = 'MailConnector.message_mit_anhaengen → Intake.step'
WITHHELD = 'N06'
_SOURCE_ONLY_INSTANCE = ContextVar('heldout_source_only_instance', default=None)


class OfflineViolation(BaseException):
    """Sicherheitsgrenze, die ein fehlertoleranter Import nicht verschlucken darf."""


class NoModel:
    is_local = True
    name = model = 'heldout-source-only'

    def complete(self, *args, **kwargs):
        raise OfflineViolation('Modellaufruf in der reinen Quellenaufnahme.')

    complete_json = complete
    embed = complete


@contextmanager
def offline_boundary():
    """Sperrt ausgehende Python-Sockets und Namensauflösung für den isolierten Lauf."""
    def forbidden(*args, **kwargs):
        raise OfflineViolation('Netzwerkzugriff in der reinen Quellenaufnahme.')

    with ExitStack() as stack:
        for target, names in (
            (socket.socket, ('connect', 'connect_ex', 'sendto')),
            (socket, ('create_connection', 'getaddrinfo', 'gethostbyname', 'gethostbyname_ex')),
        ):
            for name in names:
                stack.enter_context(patch.object(target, name, forbidden))
        yield


@dataclass(frozen=True)
class FrozenSources:
    root: Path
    freeze_sha256: str
    clock: datetime
    timezone: str
    owner_address: str
    mail: tuple[Mapping, ...]
    native: tuple[Mapping, ...]
    originals: Mapping[str, bytes]
    file_digests: Mapping[str, str]


def _digest(data):
    return sha256(data).hexdigest()


def _freeze_json(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(map(_freeze_json, value))
    return value


def load_frozen_sources(root=None) -> FrozenSources:
    """Prüft den gepinnten Manifest-Hash und jedes Artefakt vor der Aufnahme."""
    root = FIXTURE if root is None else Path(root)

    def read(name):
        path = root / name
        if any((root / part).is_symlink() for part in (Path(name), *Path(name).parents)):
            raise ValueError(f'Verknüpfung im Testbestand: {name}')
        try:
            return path.read_bytes()
        except OSError as exc:
            raise ValueError(f'Testartefakt fehlt oder ist nicht lesbar: {name}') from exc

    if root.is_symlink():
        raise ValueError('Der Testbestand muss ein echtes Verzeichnis sein.')
    freeze = read('freeze.json')
    digest = _digest(freeze)
    if digest != FREEZE_SHA:
        raise ValueError('freeze.json stimmt nicht mit dem gepinnten SHA-256 überein.')
    manifest = json.loads(freeze)
    expected = manifest['files']
    paths = {path.relative_to(root).as_posix() for path in root.rglob('*')
             if path.is_symlink() or not path.is_dir()}
    extra = paths - (set(expected) | {'freeze.json'})
    if extra:
        raise ValueError(f'Nicht eingefrorene Artefakte: {", ".join(sorted(extra))}')

    data = {}
    for name, expected_digest in expected.items():
        raw = read(name)
        if _digest(raw) != expected_digest:
            raise ValueError(f'SHA-256 stimmt nicht: {name}')
        if name == 'sources.json' or name.startswith('native/'):
            data[name] = raw

    sources = json.loads(data.pop('sources.json'))
    mail, native = tuple(sources['mails']), tuple(sources['native'])
    ids = {row['id'] for row in (*mail, *native)}
    if (len(mail) != 100 or len(native) != 10 or len(ids) != 110
            or {row['file'] for row in native} != set(data)
            or {row['id'] for row in native if row['source_kind'] == 'calendar_ics_update'} != {WITHHELD}):
        raise ValueError('sources.json: Quelleninventar weicht vom Freeze ab.')
    return FrozenSources(root.resolve(), digest, datetime.fromisoformat(sources['clock']),
                         sources['timezone'], sources['owner']['address'], _freeze_json(sources['mails']),
                         _freeze_json(sources['native']), MappingProxyType(data), MappingProxyType(expected))


def _fresh_target(path, fixture):
    target = Path(path).resolve()
    if target.is_relative_to(fixture.resolve()):
        raise ValueError('Ziel muss außerhalb des eingefrorenen Testbestands liegen.')
    if Path(path).is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise ValueError('Zielverzeichnis muss neu oder leer sein.')
    return target


@contextmanager
def source_only_instance(sources: FrozenSources, *, directory=None):
    """Baut eine frische Messinstanz mit Modellwächtern für alle übergebenen Rollen."""
    from messlatte.instanz import instanz_starten

    target = _fresh_target(directory, sources.root) if directory is not None else None
    provider = NoModel()
    with ExitStack() as instance_scope:
        with offline_boundary():
            instance = instance_scope.enter_context(instanz_starten(
                stichtag=sources.clock, zeitzone=sources.timezone, verzeichnis=target,
                eigene=(sources.owner_address,), provider=provider,
                frage_provider=provider, pruef_provider=provider))
        token = _SOURCE_ONLY_INSTANCE.set((instance, sources, provider))
        try:
            yield instance
        finally:
            _SOURCE_ONLY_INSTANCE.reset(token)


def _source_mail(source):
    from messlatte.daten import Adresse, Mail

    def address(value):
        return Adresse(value['name'], value['address'])

    return Mail(id=source['id'], zeit=datetime.fromisoformat(source['at']), szenario=ACCOUNT,
                von=address(source['sender']), an=tuple(map(address, source['recipients'])),
                cc=tuple(map(address, source.get('cc', ()))), betreff=source['title'],
                text=source['body'], ordner=source['folder'], antwort_auf=source.get('reply_to'))


def _episode_row(episodes, episode_id):
    snapshot = episodes.support_snapshot(episode_id)
    episode = snapshot.episode

    def iso(value):
        return value.isoformat() if value is not None else None

    return {'id': episode.id, 'kind': episode.kind.value, 'source_key': snapshot.source_key or None,
            'source_key_status': 'persisted' if snapshot.source_key else 'unversioned',
            'source_ref': episode.provenance.source_ref, 'source_type': episode.provenance.source_type.value,
            'body_digest': episode.digest, 'occurred_at': iso(episode.occurred_at),
            'captured_at': iso(episode.provenance.captured_at), 'recorded_at': iso(episode.recorded_at)}


def _mail_receipts(instance, sources, receipts):
    from icarus_memory.anhaenge import gespeicherter_bericht
    from icarus_memory.connectors.mail import MailConfig, MailConnector
    from icarus_memory.mail_intake import Intake
    from messlatte.postfach import Postfach, postfach_installieren, rohmail

    native = {row['id']: row for row in sources.native}
    mailbox = Postfach()
    for source in sorted(sources.mail, key=lambda row: (row['at'], row['id'])):
        raw = rohmail(_source_mail(source))
        mailbox.ablegen(source['folder'], source['id'], raw)
        receipts[source['id']].update(wire_sha256=_digest(raw), mail_folder=source['folder'],
                                      original_body_sha256=_digest(source['body'].encode('utf-8')))
    attachments = {}
    for source in (row for row in sources.native if row['source_kind'] == 'mail_with_attachment'):
        raw = sources.originals[source['file']]
        mailbox.ablegen('INBOX', source['id'], raw)
        receipts[source['id']].update(wire_sha256=_digest(raw), mail_folder='INBOX')
        # Beleg für die Byte-Identität der PDF. Gelesen und aufgenommen wird
        # sie ausschließlich im nachfolgenden Produktabruf aus dieser EML.
        message = BytesParser(policy=policy.default).parsebytes(raw)
        for child_id in source['attachments']:
            child = native[child_id]
            filename = Path(child['file']).name
            payloads = [part.get_payload(decode=True) for part in message.iter_attachments()
                        if part.get_filename() == filename]
            if payloads != [sources.originals[child['file']]] or child['parent_id'] != source['id']:
                raise ValueError(f'{child_id}: Die Anlage entspricht nicht dem eingefrorenen PDF.')
            receipts[child_id]['embedded_sha256'] = _digest(payloads[0])
            attachments[child_id] = (source['id'], filename)

    episodes = instance.episodes
    intake = Intake(episodes)
    intake.start(ACCOUNT, tuple(mailbox.ordner))
    reader = MailConnector(MailConfig(imap_host='imap.heldout.example', username=sources.owner_address,
                                      password='unbenutzt'))
    with postfach_installieren(mailbox):
        # Jeder Schritt holt höchstens 50. Ein einzelner fehlgeschlagener
        # Abruf bleibt sichtbar, ohne auf den Hintergrund-Wiederholer zu warten.
        for _ in range(mailbox.anzahl() // 50 + 4):
            if not intake.step(ACCOUNT, reader, batch=50, claims=instance.claims,
                               permission_lock=instance.app.state.conversation_lock):
                break

    status = intake.status(ACCOUNT)
    # Der Produktfortschritt bindet Konto, Ordner und UID an die Episode.
    # Diese Zuordnung bleibt auch bei identischem Betreff/Text eindeutig.
    with episodes._lock:
        stored = {(row['folder'], row['uid']): row for row in intake.db.execute(
            'SELECT i.account,i.folder,i.generation,i.uid,i.episode_id,i.status,i.grund FROM mail_intake_items i '
            'JOIN mail_intake_folders f ON f.account=i.account AND f.folder=i.folder AND f.generation=i.generation '
            'WHERE i.account=?', (ACCOUNT,))}
    for identity, fixture_id in mailbox.welt_id.items():
        receipt = receipts[fixture_id]
        receipt['path'] = MAIL_PATH
        row = stored.get(identity)
        if row is not None:
            receipt['mail_transport'] = {'account_id': row['account'], 'folder': row['folder'],
                                         'uid': row['uid'], 'uidvalidity': row['generation']}
        if row is None or not row['episode_id']:
            reason = (row['grund'] or row['status']) if row is not None else status.get('error')
            receipt['reasons'].append(reason or 'Kein Eintrag im Mailaufnahmestand.')
            continue
        episode = episodes.get(row['episode_id'])
        receipt['episodes'] = [_episode_row(episodes, episode.id)]
        report = gespeicherter_bericht(episode)
        if 'source:truncated' in episode.tags or (report and not report['vollstaendig']):
            receipt['reasons'].append((report or {}).get('hinweis') or 'Mailabruf unvollständig.')

    for child_id, (parent_id, filename) in attachments.items():
        receipt = receipts[child_id]
        receipt['path'] = MAIL_PATH + ' → anhaenge.aus_mail/aufnehmen'
        parent_receipt = receipts[parent_id]
        parent_episodes = parent_receipt['episodes']
        receipt['parent_mail_transport'] = parent_receipt.get('mail_transport')
        receipt['parent_episode_ids'] = [row['id'] for row in parent_episodes]
        if parent_episodes:
            parent = parent_episodes[0]
            children = (episodes.get(id_) for id_ in episodes.mail_attachment_children(parent['id']))
            for child in children:
                if child.provenance.source_ref.rsplit(':', 1)[-1] == filename:
                    receipt['episodes'].append(_episode_row(episodes, child.id))
                    if 'source:truncated' in child.tags:
                        receipt['reasons'].append('Anlage nur teilweise oder ohne lesbaren Text erfasst.')
        if len(receipt['episodes']) != 1:
            receipt['reasons'].append('Keine eindeutige gespeicherte Anlage unter der erwarteten Elternquelle.')
    return status


def _file_receipt(instance, sources, source, receipt, adapter):
    from icarus_memory.ingest import ingest_directory
    from icarus_memory.source_versions import source_key, track_document
    from icarus_memory.transkript_routes import nach_aufnahme

    root = instance.verzeichnis / 'heldout-input' / source['id']
    filename = Path(source['file']).name
    path = root / filename
    raw = sources.originals[source['file']]
    if any(p.is_symlink() for p in (path, root, root.parent)):
        raise ValueError(f'{source["id"]}: Verknüpfung im Aufnahmeordner.')
    root.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open('xb') as output:
            output.write(raw)
    if set(root.iterdir()) != {path} or path.read_bytes() != raw:
        raise ValueError(f'{source["id"]}: Aufnahmeordner enthält fremde oder geänderte Dateien.')

    receipt['path'] = f'ingest_directory({adapter})'
    episodes, claims = instance.episodes, instance.claims
    report = ingest_directory(
        episodes, root, adapter, roots=[instance.verzeichnis],
        on_source=lambda r, ref, e: track_document(episodes, claims, r, ref, e),
        on_transcript=nach_aufnahme(instance.app) if adapter == 'transkripte' else None)
    ref_prefix = 'datei' if adapter == 'dateien' else 'transkript'
    head = episodes.source_head(source_key(root.resolve(), f'{ref_prefix}:{filename}'))
    if head:
        receipt['episodes'] = [_episode_row(episodes, head)]
    receipt['reasons'].extend([*map(str, report.skipped_reasons), *report.errors])
    if not head and not receipt['reasons']:
        receipt['reasons'].append('Keine Episode für die Datei gefunden.')


def _calendar_receipt(instance, sources, source, receipt):
    from icarus_memory.calendar_memory import fenster, quelle_schluessel
    from icarus_memory.connectors.calendar import parse_events

    receipt['path'] = 'connectors.calendar.parse_events → KalenderGedaechtnis.abgleichen'
    start, end = fenster(sources.clock)
    events = parse_events(sources.originals[source['file']], start, end)
    result = instance.app.state.calendar_memory.abgleichen(CALENDAR, 'Heldout v2', events, start, end)
    for event in events:
        head = instance.episodes.source_head(quelle_schluessel(CALENDAR, event.uid))
        if head:
            receipt['episodes'].append(_episode_row(instance.episodes, head))
    receipt['reasons'].extend(result.fehler)
    if len(events) != 1 or len(receipt['episodes']) != 1:
        receipt['reasons'].append('Kein eindeutiger Termin im Gedächtnisfenster aufgenommen.')


def _docx_receipt(instance, sources, source, receipt):
    from httpx import HTTPStatusError

    route = '/api/v1/sources/documents'
    receipt['path'] = 'POST /api/v1/sources/documents/preview-docx → POST /api/v1/sources/documents'
    try:
        preview = instance.anfrage('POST', route + '/preview-docx',
                                   {'content_base64': base64.b64encode(sources.originals[source['file']]).decode('ascii')})
        imported = instance.anfrage('POST', route, {'filename': Path(source['file']).name,
                                                     'body': preview['body'], 'project_id': None})
    except HTTPStatusError as exc:
        receipt['reasons'].append(f'Produktimport abgelehnt (HTTP {exc.response.status_code}).')
        return
    receipt['episodes'] = [_episode_row(instance.episodes, imported['id'])]


@offline_boundary()
def prepare_baseline(instance, sources: FrozenSources) -> dict:
    """Nimmt Quellen in einer aktiven `source_only_instance` auf. N06 bleibt zurück."""
    active = _SOURCE_ONLY_INSTANCE.get()
    if active is None or active[0] is not instance or active[1] is not sources:
        raise OfflineViolation('Aufnahme erfordert eine aktive quellengeschützte Messinstanz.')
    state = instance.app.state
    if (state.agent is not instance.agent or instance.agent.provider is not active[2]
            or state.settings.model_roles or state.settings.schedule.enabled):
        raise OfflineViolation('Die quellengeschützte Messinstanz wurde für Modellarbeit umgestellt.')

    receipts = {}
    for source in (*sources.mail, *sources.native):
        file = source.get('file')
        receipts[source['id']] = {'fixture_id': source['id'], 'path': None, 'file': file,
                                  'file_sha256': sources.file_digests.get(file), 'episodes': [],
                                  'original_at': source.get('at') or source.get('source_at'),
                                  'fixture_captured_at': source.get('captured_at'),
                                  'parent_fixture_id': source.get('parent_id'), 'reasons': []}

    mail = _mail_receipts(instance, sources, receipts)
    for source in sources.native:
        kind = source['source_kind']
        receipt = receipts[source['id']]
        if source['id'] == WITHHELD:
            receipt['reasons'].append('Für spätere Kalenderänderung reserviert. Nur Datei-Hash geprüft.')
        elif kind == 'calendar_ics':
            _calendar_receipt(instance, sources, source, receipt)
        elif kind == 'text_document':
            _file_receipt(instance, sources, source, receipt, 'dateien')
        elif kind in {'provided_transcript', 'provided_transcript_uncertain'}:
            _file_receipt(instance, sources, source, receipt, 'transkripte')
        elif kind == 'docx_document':
            _docx_receipt(instance, sources, source, receipt)
        elif kind not in {'mail_with_attachment', 'pdf_attachment'}:
            receipt['reasons'].append(f'Kein passender Produktpfad für {kind}.')

        if kind in {'text_document', 'provided_transcript', 'provided_transcript_uncertain', 'docx_document'}:
            for episode in receipt['episodes']:
                actual_at = episode['occurred_at']
                if actual_at is None or datetime.fromisoformat(actual_at) != datetime.fromisoformat(receipt['original_at']):
                    receipt['reasons'].append('Der Dateipfad übernimmt die externe Quellenzeit nicht exakt.')

    for row in receipts.values():
        if row['fixture_id'] == WITHHELD:
            row['coverage'] = 'withheld'
        elif not row['episodes']:
            row['coverage'] = 'missing'
        else:
            row['coverage'] = 'partial' if row['reasons'] else 'admitted'

    return {'freeze_sha256': sources.freeze_sha256, 'file_digests': dict(sources.file_digests),
            'clock': sources.clock.isoformat(), 'timezone': sources.timezone,
            'product_quality': 'NOT EVALUATED', 'bulk_import_authorized': False,
            'coverage': dict(Counter(row['coverage'] for row in receipts.values())),
            'mail_intake': mail, 'receipts': list(receipts.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path,
                        help='Neues oder leeres Verzeichnis. Ohne Angabe bleibt nur der JSON-Bericht.')
    args = parser.parse_args(argv)
    try:
        target = _fresh_target(args.target, FIXTURE) if args.target is not None else None
    except (OSError, ValueError) as exc:
        parser.error(f'--target: {exc}')

    sources = load_frozen_sources()
    with source_only_instance(sources, directory=target) as instance:
        report = prepare_baseline(instance, sources)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
