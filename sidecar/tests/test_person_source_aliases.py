"""Kurznamen brauchen Belege dieser Mail, keine globalen Teilnamens-Aliasse."""
from contextlib import closing
from copy import deepcopy

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.bezuege import Bezuege, Register, berechnen
from icarus_memory.memory_categories import Categories
from tests.test_bezuege import JETZT, Modell, stelle

ICH = 'lars@example.test'
ABSENDER = 'person:a:nora@example.test'
KONTAKTE = [
    {'name': 'Dr. Nora Becker', 'adresse': 'nora@example.test', 'rolle': 'von'},
    {'name': 'Lars Winter', 'adresse': ICH, 'rolle': 'an'},
]


def mail(episodes, body, *, contacts=None, source_ref='test:brief'):
    return episodes.record(
        EpisodeKind.MESSAGE, 'Synthetischer Brief', body,
        Provenance(SourceType.EMAIL, source_ref=source_ref),
        contacts=deepcopy(KONTAKTE if contacts is None else contacts), occurred_at=JETZT,
    )[0]


def auszug(body, *names):
    return {'categories': [], 'entities': [stelle(body, name) for name in names]}


@pytest.mark.parametrize('greeting,name', [
    ('Sehr geehrter Herr Winter,', 'Herr Winter'),
    ('Hallo Lars,', 'Lars'),
])
def test_own_short_name_in_direct_greeting_does_not_create_an_extra_person(tmp_path, greeting, name):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = greeting + '\n\nBitte prüfen Sie den Entwurf.'
        source = mail(episodes, body)
        before = deepcopy(source.to_dict())
        register = Register.bauen([source], eigene=[ICH])

        result = berechnen(source, auszug(body, name), register, [ICH])

        assert [b.sache for b in result if b.art == 'person'] == [ABSENDER]
        assert episodes.get(source.id).to_dict() == before


def test_sender_short_signature_reuses_its_address_and_keeps_the_original_span(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = 'Bitte prüfen Sie den Entwurf.\n\nMit freundlichen Grüßen\nDr. Becker'
        source = mail(episodes, body)
        result = berechnen(source, auszug(body, 'Dr. Becker'), Register.bauen([source], eigene=[ICH]), [ICH])

        people = [b for b in result if b.art == 'person']
        assert {b.sache for b in people} == {ABSENDER}
        mention = next(b for b in people if b.grundlage == 'modell')
        assert body[mention.start:mention.ende] == 'Dr. Becker'
        assert mention.abhaengig


@pytest.mark.parametrize('other_role', ['an', 'cc', 'von'])
def test_short_greeting_with_two_matching_source_people_is_unresolved(tmp_path, other_role):
    contacts = [KONTAKTE[0],
                {'name': 'Lars Winter', 'adresse': 'lars@example.test', 'rolle': 'an'},
                {'name': 'Martin Winter', 'adresse': 'martin@example.test', 'rolle': other_role}]
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = 'Sehr geehrter Herr Winter,\n\nBitte prüfen Sie den Entwurf.'
        source = mail(episodes, body, contacts=contacts)
        result = berechnen(source, auszug(body, 'Herr Winter'), Register.bauen([source]))

        mention = next(b for b in result if b.grundlage == 'modell')
        assert mention.sache == ''
        assert mention.kandidaten == ('person:a:lars@example.test', 'person:a:martin@example.test')


@pytest.mark.parametrize('body,name,contacts', [
    ('Hallo Nora,\n\nBitte prüfen.', 'Nora', [
        {'name': 'Nora Becker', 'adresse': 'nora@a.example', 'rolle': 'an'},
        {'name': 'Nora', 'adresse': 'other@b.example', 'rolle': 'cc'},
    ]),
    ('Bitte prüfen.\n\nMit freundlichen Grüßen\nBecker', 'Becker', [
        {'name': 'Nora Becker', 'adresse': 'nora@a.example', 'rolle': 'von'},
        {'name': 'Becker', 'adresse': 'other@b.example', 'rolle': 'an'},
    ]),
])
@pytest.mark.parametrize('own', [[], ['other@b.example']])
def test_exact_short_source_contact_also_prevents_a_partial_name_assignment(tmp_path, body, name, contacts, own):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        source = mail(episodes, body, contacts=contacts)
        before = deepcopy(source.to_dict())

        result = berechnen(source, auszug(body, name), Register.bauen([source], eigene=own), own)

        mention = next(b for b in result if b.grundlage == 'modell')
        assert mention.sache == ''
        assert mention.kandidaten == ('person:a:nora@a.example', 'person:a:other@b.example')
        assert body[mention.start:mention.ende] == name
        assert episodes.get(source.id).to_dict() == before


@pytest.mark.parametrize('body,name', [
    ('Lars prüft den Entwurf.', 'Lars'),
    ('Ein anderer Herr Winter prüft den Entwurf.', 'Herr Winter'),
    ('Dr. Becker aus einer anderen Redaktion prüft den Entwurf.', 'Dr. Becker'),
    ('Danke.\n\n> Mit freundlichen Grüßen\n> Dr. Becker', 'Dr. Becker'),
    ('Danke.\n\nAm 01.10.2026 schrieb jemand:\nMit freundlichen Grüßen\nDr. Becker', 'Dr. Becker'),
    ('Danke.\n\nVon: Andere Person <andere@example.test>\nGesendet: 01.10.2026\n'
     'An: Gast <gast@example.test>\nBetreff: Zitat\nMit freundlichen Grüßen\nDr. Becker', 'Dr. Becker'),
])
def test_prose_and_quoted_third_parties_do_not_inherit_a_source_contact(tmp_path, body, name):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        source = mail(episodes, body)
        result = berechnen(source, auszug(body, name), Register.bauen([source], eigene=[ICH]), [ICH])

        mention = next(b for b in result if b.grundlage == 'modell')
        assert mention.sache == ''
        expected = ('person:a:lars@example.test',) if name in {'Lars', 'Herr Winter'} else (ABSENDER,)
        assert mention.kandidaten == expected
        assert body[mention.start:mention.ende] == name


def test_short_name_in_another_source_does_not_become_a_global_alias(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        first = mail(episodes, 'Mit freundlichen Grüßen\nDr. Becker')
        body = 'Dr. Becker ist hier nur eine Namensnennung.'
        second = mail(episodes, body, contacts=[], source_ref='test:other')
        register = Register.bauen([first, second], eigene=[ICH])

        result = berechnen(second, auszug(body, 'Dr. Becker'), register, [ICH])

        assert [b.sache for b in result] == ['person:n:dr. becker']


def test_repeated_quoted_greeting_is_open_instead_of_creating_a_second_person(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = 'Sehr geehrter Herr Winter,\n\nBitte prüfen.\n\n> Sehr geehrter Herr Winter,\n> Alte Nachricht.'
        source = mail(episodes, body)
        output = auszug(body, 'Herr Winter')
        output['entities'].append(stelle(body, 'Herr Winter', nach=body.index('>')))
        refs = Bezuege(episodes, eigene=lambda: [ICH])
        assert Categories(episodes).run(Modell(output), source_ids=[source.id], limit=1).ok

        refs.aktualisieren()

        data = refs.bezuege_der_quelle(source.id)
        assert [b['sache'] for b in data['bezuege'] if b['art'] == 'person'] == [ABSENDER]
        assert len(data['offen']) == 1
        unresolved = data['offen'][0]
        assert unresolved['kandidaten'] == ['person:a:lars@example.test']
        assert refs.zitat(source.id, unresolved['stelle']['start'], unresolved['stelle']['ende']) == 'Herr Winter'
        assert refs.sachen(art='person')['gesamt'] == 1


@pytest.mark.parametrize('display,greeting,name', [
    ("'Nora Becker'", 'Sehr geehrte Frau Becker,', 'Frau Becker'),
    ('=?utf-8?q?=27Nora_Becker=27?=', 'Sehr geehrte Frau Becker,', 'Frau Becker'),
    ("'Nora Becker'", 'Hallo Nora,', 'Nora'),
    ("'Nora O\'Connor'", "Sehr geehrte Frau O'Connor,", "Frau O'Connor"),
])
def test_outer_contact_quotes_only_affect_local_name_comparison(tmp_path, display, greeting, name):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = greeting + '\n\nBitte prüfen.\n\n> ' + greeting + '\n> Alte Nachricht.'
        contacts = [
            {'name': 'Mara Feld', 'adresse': 'mara@example.test', 'rolle': 'von'},
            {'name': display, 'adresse': 'nora@example.test', 'rolle': 'an'},
        ]
        source = mail(episodes, body, contacts=contacts)
        before = deepcopy(source.to_dict())
        output = auszug(body, name)
        output['entities'].append(stelle(body, name, nach=body.index('>')))
        refs = Bezuege(episodes, eigene=lambda: ['nora@example.test'])
        assert Categories(episodes).run(Modell(output), source_ids=[source.id], limit=1).ok

        refs.aktualisieren()

        data = refs.bezuege_der_quelle(source.id)
        assert [b['sache'] for b in data['bezuege'] if b['art'] == 'person'] == ['person:a:mara@example.test']
        assert len(data['offen']) == 1
        unresolved = data['offen'][0]
        assert unresolved['kandidaten'] == ['person:a:nora@example.test']
        assert refs.zitat(source.id, unresolved['stelle']['start'], unresolved['stelle']['ende']) == name
        assert episodes.get(source.id).to_dict() == before
        # Die lokale Glättung legt keinen globalen Alias ohne äußere Quotes an.
        if 'Becker' in display:
            assert Register.bauen([source]).person('Nora Becker') == ('person:n:nora becker', ())


def test_internal_apostrophe_keeps_a_different_source_contact_out_of_the_candidates(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = "Bitte prüfen.\n\nMit freundlichen Grüßen\nO'Connor"
        contacts = [
            {'name': "'Nora O'Connor'", 'adresse': 'nora@example.test', 'rolle': 'von'},
            {'name': 'Nina OConnor', 'adresse': 'nina@example.test', 'rolle': 'an'},
        ]
        source = mail(episodes, body, contacts=contacts)

        result = berechnen(source, auszug(body, "O'Connor"), Register.bauen([source]))

        mention = next(b for b in result if b.grundlage == 'modell')
        assert mention.sache == 'person:a:nora@example.test'
        assert mention.kandidaten == ()


def test_withdrawing_the_source_contact_removes_its_derived_short_name_resolution(tmp_path):
    with closing(EpisodeStore(tmp_path / 'episodes.sqlite3')) as episodes:
        body = 'Hallo Lars,\n\nBitte prüfen.'
        source = mail(episodes, body)
        categories = Categories(episodes)
        output = auszug(body, 'Lars')
        assert categories.run(Modell(output), source_ids=[source.id], limit=1).ok
        refs = Bezuege(episodes)
        refs.aktualisieren()
        first = refs.bezuege_der_quelle(source.id)
        target = next(b for b in first['bezuege'] if b['sache'] == 'person:a:lars@example.test')
        assert target['grundlagen'] == ['anker', 'modell']

        episodes.remove_contacts(source.id, [KONTAKTE[1]], [])
        categories.request_recheck([source.id])
        assert categories.run(Modell(output), source_ids=[source.id], limit=1).ok
        refs.aktualisieren()

        data = refs.bezuege_der_quelle(source.id)
        assert not any(b['sache'] == 'person:a:lars@example.test' for b in data['bezuege'])
        assert any(b['sache'] == 'person:n:lars' for b in data['bezuege'])
        assert data['offen'] == []


def test_derived_alias_cache_refreshes_after_restart_and_preserves_user_decisions(tmp_path):
    path = tmp_path / 'episodes.sqlite3'
    with closing(EpisodeStore(path)) as episodes:
        body = 'Bitte prüfen.\n\nMit freundlichen Grüßen\nDr. Becker'
        source = mail(episodes, body)
        categories = Categories(episodes)
        assert categories.run(Modell(auszug(body, 'Dr. Becker')), source_ids=[source.id], limit=1).ok
        refs = Bezuege(episodes, eigene=lambda: [ICH])
        refs.aktualisieren()
        refs.nutzer_setzen(source.id, 'person:n:dr. becker', 'zu')
        refs.nutzer_setzen(source.id, ABSENDER, 'nicht')
        # Die Dublette der alten Regel samt altem Berechnungsstand speichern.
        with episodes.transaction():
            episodes._conn.execute(
                "UPDATE sach_bezuege SET sache='person:n:dr. becker' "
                "WHERE episode_id=? AND grundlage='modell'", (source.id,))
            episodes._conn.execute(
                "UPDATE sach_quellen SET eingabe=substr(eingabe,1,instr(eingabe,'|regeln:')-1)||'|regeln:2' "
                "WHERE episode_id=?", (source.id,))
        original = deepcopy(episodes.get(source.id).to_dict())
        decisions = [tuple(row) for row in episodes._conn.execute('SELECT * FROM sach_nutzer ORDER BY sache')]

    with closing(EpisodeStore(path)) as episodes:
        refs = Bezuege(episodes, eigene=lambda: [ICH])
        assert refs.aktualisieren()['berechnet'] == 1
        data = refs.bezuege_der_quelle(source.id)
        assert [(b['sache'], b['grundlagen']) for b in data['bezuege'] if b['art'] == 'person'] == [
            ('person:n:dr. becker', ['nutzer'])]
        assert {'sache': ABSENDER, 'art': 'person'} in data['abgelehnt']
        assert episodes.get(source.id).to_dict() == original
        assert [tuple(row) for row in episodes._conn.execute('SELECT * FROM sach_nutzer ORDER BY sache')] == decisions
        assert refs.aktualisieren()['berechnet'] == 0
        episodes.ignore(source.id)
        assert refs.bezuege_der_quelle(source.id) is None
        refs.aktualisieren()
        assert refs.sachen(art='person')['sachen'] == []
