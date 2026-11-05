"""Replay the same frozen MIME twice through real parsing/intake, without models."""
from pathlib import Path
import sys
import json
from dataclasses import replace
from hashlib import sha256

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'
sys.path[:0] = [str(SOURCE / 'sidecar'), str(SOURCE / 'scripts'), str(SOURCE)]
from memory_acceptance_intake import load_frozen_sources, source_only_instance, offline_boundary, ACCOUNT
from messlatte.postfach import Postfach, postfach_installieren
from icarus_memory.connectors.mail import MailConfig, MailConnector
from icarus_memory.mail_ingestion import remember

corpus = load_frozen_sources()
native = {row['id']: row for row in corpus.native}
raw = corpus.originals[native['N01']['file']]
pdf = corpus.originals[native['N02']['file']]
before_files = {name: sha256((corpus.root / name).read_bytes()).hexdigest()
                for name in corpus.file_digests}
mailbox = Postfach()
uid = mailbox.ablegen('INBOX', 'N01', raw)
reader = MailConnector(MailConfig(imap_host='imap.replay.example', username=corpus.owner_address,
                                  password='synthetic-unused'))
observations = []
with offline_boundary(), source_only_instance(corpus, directory=ROOT / 'instance') as instance:
    def current(parent_id):
        ids = [parent_id, *instance.episodes.mail_attachment_children(parent_id)]
        assert len(ids) == 2
        snapshots = [instance.episodes.support_snapshot(value) for value in ids]
        assert all(value.current() for value in snapshots)
        return [{'id': value.episode.id, 'source_key': value.source_key,
                 'head_id': value.head_id, 'body_digest': value.episode.digest,
                 'support': value.support_fingerprint(), 'document': value.episode.to_dict()}
                for value in snapshots]

    with postfach_installieren(mailbox):
        for attempt in range(2):
            message = reader.message_mit_anhaengen('INBOX', f'1.{uid}')
            assert message.anhang_bericht['vollstaendig'] is True
            qualified = replace(message, account_id=ACCOUNT, uid=f'{ACCOUNT}:{message.uid}')
            result = remember(instance.episodes, qualified, claims=instance.claims,
                              source_identity=message.uid)
            parent = result['episode']['id']
            observations.append({'attempt': attempt + 1, 'new': result['new'],
                                 'changed': result['changed'], 'fetch_count': mailbox.abrufe,
                                 'sources': current(parent)})
    assert observations[0]['new'] is True
    assert observations[1]['new'] is False and observations[1]['changed'] is False
    assert observations[1]['fetch_count'] > observations[0]['fetch_count']
    assert observations[0]['sources'] == observations[1]['sources']
    assert len(list(instance.episodes.each_episode())) == 2
    assert not instance.app.state.tasks.all_tasks()
    # Show that the child was read from the MIME, not imported separately.
    from email import policy
    from email.parser import BytesParser
    parts = BytesParser(policy=policy.default).parsebytes(raw).iter_attachments()
    embedded = [p.get_payload(decode=True) for p in parts]
    assert embedded == [pdf]

assert before_files == {name: sha256((corpus.root / name).read_bytes()).hexdigest()
                        for name in corpus.file_digests}
report = {'code_commit': (ROOT / 'base.txt').read_text().strip(),
          'case': 'S08 original MIME/PDF exact replay only', 'status': 'PASS',
          'wire_sha256': sha256(raw).hexdigest(), 'embedded_pdf_sha256': sha256(pdf).hexdigest(),
          'fetches': [o['fetch_count'] for o in observations],
          'parent_child_documents_and_support_identical': True,
          'episode_count': 2, 'task_count': 0, 'network_calls': 0, 'model_calls': 0,
          'semantic_license_obligation_and_answer': 'NOT EVALUATED',
          'scope_limits': ['synthetic IMAP transport; no provider authentication or TLS',
                           'same account, folder and UIDVALIDITY/UID only',
                           'no MIME cursor shortcut; both calls fetched and parsed original bytes'],
          'observations': observations}
(ROOT / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:v for k,v in report.items() if k != 'observations'}, ensure_ascii=False, indent=2))
