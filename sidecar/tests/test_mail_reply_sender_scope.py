"""Antwortvorschläge suchen nur in Mails des Absenders; ein großes Postfach stört nicht."""
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType
from tests.test_mail_conversation_flow import index_prior_mail, memory_reply_app, suggest_memory_reply


def _validate(client, token):
    return client.post('/api/v1/messages/work:1/reply-suggestion/validate', json={'context_token': token})


def test_large_mailbox_with_same_subject_words_still_yields_the_sender_quote(tmp_path, monkeypatch):
    app, _, second, episode, client = memory_reply_app(tmp_path, monkeypatch)
    for n in range(40):
        index_prior_mail(app, f'Projekt Atlas Rechnung Nummer {n}: Die Rechnung liegt der Buchhaltung vor.',
                         sender=f'kollege{n}@example.invalid')
    suggestion = suggest_memory_reply(client)
    assert suggestion['sources'][0]['episode_id'] == episode.id
    assert second.sent == []


def test_other_senders_do_not_invalidate_but_the_sender_does(tmp_path, monkeypatch):
    app, _, _, _, client = memory_reply_app(tmp_path, monkeypatch)
    token = suggest_memory_reply(client)['context_token']
    index_prior_mail(app, 'Projekt Atlas Rechnung: Der Versand ist nicht zugesagt.', sender='kollege@example.invalid')
    assert _validate(client, token).json() == {'valid': True}
    index_prior_mail(app, 'Projekt Atlas Rechnung: Neue Freigabe nötig, erst danach Versand.')
    assert _validate(client, token).status_code == 409


def test_sender_lookup_checks_account_single_sender_and_wildcards(tmp_path):
    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    def mail(ref, participants, kind=EpisodeKind.MESSAGE, source=SourceType.EMAIL):
        episode, _ = episodes.record(kind, 'T', f'Text {ref} {participants}', Provenance(source, source_ref=ref),
                                     participants=participants)
        return episode.id
    own = mail('work:<1>', ['Alex <alex@example.invalid>'])
    mail('home:<2>', ['Alex <alex@example.invalid>'])
    mail('work:<3>', ['Alex <alex@example.invalid>', 'Bea <bea@example.invalid>'])
    mail('work:<4>', ['Alex <alex2@example.invalid>'])
    mail('work:<5>', ['Alex <alex@example.invalid>'], source=SourceType.CHAT)
    assert episodes.sender_episode_ids('work', 'ALEX@example.invalid') == ([own], False)
    assert episodes.sender_episode_ids('work', '%@example.invalid') == ([], False)
    assert episodes.sender_episode_ids('', 'alex@example.invalid') == ([], False)
    more = [mail(f'work:<m{n}>', ['alex@example.invalid']) for n in range(3)]
    ids, truncated = episodes.sender_episode_ids('work', 'alex@example.invalid', limit=2)
    assert len(ids) == 2 and truncated and set(ids) <= set(more + [own])
    episodes.close()
