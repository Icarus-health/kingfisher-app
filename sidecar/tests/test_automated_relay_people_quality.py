"""Technical updates and opaque relay IDs never establish a natural person."""
from contextlib import closing

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.bezuege import Bezuege
from icarus_memory.graph import GraphNode
from icarus_memory.identitaet import Verzeichnis
from icarus_memory.people_quality import annotate_people


ADDRESSES = [
    'update+synthetic-token@facebookmail.com',
    'anbieter-ab1cd2ef3gh45@mail.ebay-kleinanzeigen.de',
]


@pytest.mark.parametrize('address', ADDRESSES)
def test_update_and_opaque_relay_addresses_are_reviewable_without_person_aliases(address):
    label = f'Alex Beispiel <{address}>'
    [person] = annotate_people([GraphNode('synthetic', 'person', label)])

    assert person.attributes['quality_category'] == 'review'
    assert person.attributes['duplicate_ids'] == []
    assert Verzeichnis.aus([{'participants': [label]}]).adressen_zum_namen('Alex Beispiel') == []


@pytest.mark.parametrize('address', [
    'alex@facebookmail.com', 'lea@mail.ebay-kleinanzeigen.de',
    'anna.update@example.org', 'update.anna@example.org',
    'anbieter-anna@example.org', 'anbieter-anna.meier@example.org',
    'anbieter-1234567890123@example.org',
])
def test_personal_mailboxes_and_platform_employees_are_not_swept_up(address):
    [person] = annotate_people([GraphNode('synthetic', 'person', f'Alex Beispiel <{address}>')])

    assert person.attributes['quality_category'] == 'person'


@pytest.mark.parametrize('address', ADDRESSES)
@pytest.mark.parametrize('resolution', ['explicit_registry', 'confirmed_group'])
def test_confirmed_human_identity_at_technical_address_is_preserved(address, resolution):
    [person] = annotate_people([
        GraphNode('confirmed', 'person', f'Alex Beispiel <{address}>', {'identity_resolution': resolution}),
    ])

    assert person.id == 'confirmed'
    assert person.attributes['quality_category'] == 'person'
    assert person.attributes['quality_reason'] == ''


@pytest.mark.parametrize('address', ADDRESSES)
def test_old_rule_version_recalculates_technical_person_anchor_without_losing_user_decisions(
        tmp_path, monkeypatch, address):
    import icarus_memory.bezuege as module

    path = tmp_path / 'episodes.sqlite3'
    with closing(EpisodeStore(path)) as episodes:
        source, _ = episodes.record(
            EpisodeKind.MESSAGE, 'Synthetic technical sender', 'Synthetic relay message.',
            Provenance(SourceType.EMAIL), participants=[address],
        )
        links = Bezuege(episodes)
        with monkeypatch.context() as previous:
            previous.setattr(module, 'maschinell', lambda value: False)
            links.aktualisieren()
        links.nutzer_setzen(source.id, 'thema:work', 'zu')
        with episodes.transaction():
            # Historical cache format before technical update/relay recognition.
            episodes._conn.execute(
                "UPDATE sach_quellen SET eingabe=substr(eingabe,1,instr(eingabe,'|regeln:')-1)||'|regeln:1'"
                " WHERE episode_id=?", (source.id,),
            )
        original = tuple(episodes._conn.execute('SELECT * FROM episodes WHERE id=?', (source.id,)).fetchone())
        decisions = [tuple(row) for row in episodes._conn.execute('SELECT * FROM sach_nutzer')]

    with closing(EpisodeStore(path)) as episodes:
        links = Bezuege(episodes)

        assert links.aktualisieren()['berechnet'] == 1

        projected = links.bezuege_der_quelle(source.id)['bezuege']
        assert not [row for row in projected if row['art'] == 'person']
        assert any(row['art'] == 'organisation' for row in projected)
        assert any(row['sache'] == 'thema:work' and row['grundlagen'] == ['nutzer'] for row in projected)
        assert links.aktualisieren()['berechnet'] == 0
        assert tuple(episodes._conn.execute('SELECT * FROM episodes WHERE id=?', (source.id,)).fetchone()) == original
        assert [tuple(row) for row in episodes._conn.execute('SELECT * FROM sach_nutzer')] == decisions
