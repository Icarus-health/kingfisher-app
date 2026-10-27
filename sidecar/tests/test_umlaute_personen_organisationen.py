"""Persona-Prüfung, Befund A7: „Müller“ findet „Mueller“ und umgekehrt, beim Suchen und beim Zusammenführen; die
Karte „Worauf ich warte“ einer Person sagt dasselbe wie ihre Akte.

Zusicherungen:
1. Namen gelten in Umschrift als gleich (ä/ae, ö/oe, ü/ue, ß/ss): Eine Namensnennung „Thomas Mueller“ gehört zur
   Adresse von „Thomas Müller“. Anders bleibt anders („Müller“ ist nicht „Muller“, nicht „Möller“).
2. Eine im Text erwähnte Organisation „Müller Bau GmbH“ ist dieselbe Akte wie die Domäne `mueller-bau`.
3. Den Namen einer Organisation aus einer Domäne nimmt Kingfisher aus der Signatur, wenn eine Zeile genau passt
   („Universität Gießen“); sonst bleibt es bei der Domäne, Umlaute werden nie geraten.
4. Die Suche in den Akten findet beide Schreibweisen.
5. Die Personenseite liefert „Worauf ich warte“ aus derselben Regel wie „Worauf warte ich noch?“.
"""
import pytest

from icarus_memory.bezuege import org_vergleich, suchformen
from icarus_memory.identitaet import name_schluessel
from tests.test_akten import einordnen  # noqa: F401
from tests.test_bezuege import ICH, modell_lauf, quelle, sachen, stelle, welt  # noqa: F401
from tests.test_context_identity import core  # noqa: F401 - Fixture


@pytest.mark.parametrize('a,b,gleich', [
    ('Thomas Müller', 'Thomas Mueller', True), ('Jörg Weiß', 'Joerg Weiss', True), ('Dr. Jürgen Müller', 'Juergen Mueller', True),
    ('Müller, Thomas', 'Thomas Mueller', True), ('Thomas Müller', 'Thomas Muller', False),
    ('Thomas Müller', 'Thomas Möller', False), ('Anna Keller', 'Anna Kellner', False),
])
def test_namen_gelten_in_umschrift_als_gleich(a, b, gleich):
    assert (name_schluessel(a) == name_schluessel(b)) is gleich


def test_namensnennung_in_umschrift_gehoert_zur_adresse(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Angebot', 'Hallo', ['Thomas Müller <thomas.mueller@hessenwasser-ag.example>', f'Lea <{ICH}>'])
    text = 'Thomas Mueller schickt die Zahlen.'
    e = quelle(episodes, 'Notiz', text, [f'Lea <{ICH}>', 'Ute Dritte <ute@dritte.example>'])
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Thomas Mueller')]})
    bezuege.aktualisieren()
    belegt = {b['sache'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert 'person:a:thomas.mueller@hessenwasser-ag.example' in belegt
    assert not any(s.startswith('person:n:') for s in belegt)


def test_erwaehnte_organisation_in_umlauten_ist_die_der_domaene(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Angebot', 'Hier das Angebot.', ['Ralf Bau <ralf@mueller-bau.example>', f'Lea <{ICH}>'])
    text = 'Die Müller Bau GmbH liefert am Montag.'
    e = quelle(episodes, 'Lieferung', text, ['Ute Dritte <ute@dritte.example>', f'Lea <{ICH}>'])
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Müller Bau GmbH', art='organization')]})
    bezuege.aktualisieren()
    belegt = {b['sache']: b['grundlagen'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert belegt.get('organisation:muellerbau') == ['modell'] and 'organisation:müllerbau' not in belegt
    # Mit der Erwähnung kennt die Akte die richtige Schreibweise.
    assert bezuege.beschriftung('organisation:muellerbau') == 'Müller Bau GmbH'


def test_ohne_passende_domaene_bleibt_die_erwaehnte_organisation_fuer_sich(welt):
    episodes, _, bezuege = welt
    text = 'Die Möller Bau GmbH liefert am Montag.'
    quelle(episodes, 'Angebot', 'Hier das Angebot.', ['Ralf Bau <ralf@mueller-bau.example>', f'Lea <{ICH}>'])
    e = quelle(episodes, 'Lieferung', text, ['Ute Dritte <ute@dritte.example>', f'Lea <{ICH}>'])
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Möller Bau GmbH', art='organization')]})
    bezuege.aktualisieren()
    belegt = {b['sache'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert 'organisation:möllerbau' in belegt and 'organisation:muellerbau' not in belegt


def test_name_der_organisation_aus_der_signatur_nie_geraten(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Vortrag', 'Guten Tag,\n\nanbei das Programm.\n\nViele Grüße\nProf. Anna Weber\nUniversität Gießen',
           ['Anna Weber <a.weber@universitaet-giessen.example>', f'Lea <{ICH}>'])
    quelle(episodes, 'Lieferung', 'Hallo,\n\ndie Ware kommt.\n\nGruß\nRalf', ['Ralf Bau <ralf@mueller-bau.example>', f'Lea <{ICH}>'])
    bezuege.aktualisieren()
    assert bezuege.beschriftung('organisation:universitaetgiessen') == 'Universität Gießen'
    # Ohne passende Zeile die Domäne, ohne geratene Umlaute.
    assert bezuege.beschriftung('organisation:muellerbau') == 'Mueller Bau'
    assert org_vergleich('Hessenwasser AG') == org_vergleich('hessenwasser-ag')


def test_suche_in_den_akten_findet_beide_schreibweisen(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'A', 'Hallo', ['Thomas Müller <thomas.mueller@a.example>', f'Lea <{ICH}>'])
    text = 'Die Müller Bau GmbH liefert.'
    quelle(episodes, 'B', text, ['Ute <ute@dritte.example>', f'Lea <{ICH}>'])
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Müller Bau GmbH', art='organization')]})
    bezuege.aktualisieren()
    for suche in ('Müller', 'Mueller', 'mueller'):
        gefunden = {s['sache'] for s in bezuege.sachen(suche=suche)['sachen']}
        assert {'person:a:thomas.mueller@a.example', 'organisation:müllerbau'} <= gefunden, suche
    assert {s['sache'] for s in bezuege.sachen(suche='Möller')['sachen']} == set()
    assert suchformen('Weiß') == ['weiss'] and 'müller' in suchformen('Mueller')


def test_personenseite_sagt_dasselbe_wie_worauf_warte_ich(core, tmp_path, monkeypatch):  # noqa: F811
    from icarus_memory import SourceType, offene_punkte
    from icarus_memory.akten_routes import bausteine
    from icarus_memory.model import Provenance
    from tests.test_terminvorbereitung import _mail
    from tests.test_source_answers_http import _api
    app, client, _ = _api(core, tmp_path, monkeypatch)
    try:
        app.state.settings.mail.user = ICH
        lea, anna = f'Lea Hartmann <{ICH}>', 'Anna Keller <anna@agentur.example>'
        bitte = 'Könnten Sie mir bitte die Druckdaten schicken?'
        _mail(app, 'Druckdaten', [(bitte, 'request')], [lea, anna], tage=3)
        _mail(app, 'Hallo', [('Danke für das Treffen.', 'fact')], [anna, lea], tage=2)
        aufgabe = app.state.tasks.add('Angebot prüfen lassen', Provenance(SourceType.USER_STATED))
        app.state.tasks.warten_auf(aufgabe.id, 'Anna Keller')
        client.post('/api/v1/akten/aktualisieren')
        person = client.get('/api/v1/memory/people/anna@agentur.example').json()['person']
        punkte = person['wartet_auf_punkte']
        assert [p['aufgabe']['title'] if p['aufgabe'] else p['text'] for p in punkte] == ['Angebot prüfen lassen', bitte]
        bezuege, akten = bausteine(app)
        gesamt = offene_punkte.sammeln(akten, bezuege, 'wartet_auf', aufgaben=app.state.tasks.open_tasks(limit=None))
        assert [p['text'] for p in gesamt['punkte']] == [p['text'] for p in punkte]
    finally:
        client.close()


def test_kommt_die_adresse_spaeter_wandert_die_erwaehnung_zu_ihr(welt):
    episodes, _, bezuege = welt
    text = 'Die Müller Bau GmbH liefert am Montag.'
    e = quelle(episodes, 'Lieferung', text, ['Ute Dritte <ute@dritte.example>', f'Lea <{ICH}>'])
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Müller Bau GmbH', art='organization')]})
    bezuege.aktualisieren()
    assert 'organisation:müllerbau' in {b['sache'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    quelle(episodes, 'Angebot', 'Hier das Angebot.', ['Ralf Bau <ralf@mueller-bau.example>', f'Lea <{ICH}>'], tage=0)
    bezuege.aktualisieren()
    belegt = {b['sache'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert 'organisation:muellerbau' in belegt and 'organisation:müllerbau' not in belegt
