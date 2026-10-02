"""Quellenantworten nennen die Herkunft als Satz, nicht als technische Kennung."""
from icarus_memory.episodes import EpisodeKind
from icarus_memory.model import Provenance, SourceType
from tests.test_context_identity import core
from tests.test_conversation_retraction import _close_app
from tests.test_source_answers_http import EXCERPT, QUESTION, TITLE, _api, _ask, _conversation, _upload


def test_uploaded_document_names_its_file(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        _upload(client)
        content = _ask(client, _conversation(client), QUESTION)['content']
        assert f'Herkunft: Hochgeladenes Dokument „{TITLE}“' in content
        assert 'upload:' not in content
    finally:
        client.close()
        _close_app(app)


def test_mail_names_sender_not_message_id(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.episodes.record(
            EpisodeKind.MESSAGE, 'Vorgang', EXCERPT,
            Provenance(SourceType.EMAIL, source_ref='mail-4f2a9c:<a1b2c3@mail.example.invalid>'),
            participants=['Mira Stein <mira@example.invalid>'])
        content = _ask(client, _conversation(client), QUESTION)['content']
        assert 'Herkunft: E-Mail von Mira Stein <mira@example.invalid>' in content
        assert 'a1b2c3@mail.example.invalid' not in content and 'mail-4f2a9c' not in content
    finally:
        client.close()
        _close_app(app)
