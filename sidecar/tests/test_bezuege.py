"""Bezüge (D1): Quelle -> Sache mit Grundlage, abgeleitet und mit Fingerabdruck."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, EpisodeStore, Provenance, SourceType
from icarus_memory.bezuege import Bezuege, orte_im_termin, org_aus_adresse
from icarus_memory.memory_categories import Categories
from icarus_memory.providers import Reply
from icarus_memory.workspace import WorkspaceStore

ICH = 'lea@hartmann-beratung.example'
JETZT = datetime(2026, 9, 29, 8, 0, tzinfo=timezone.utc)


class Modell:
    """Lokales Skriptmodell für die Themen- und Erwähnungsauswertung."""

    is_local = True
    name = 'lokal'
    model = 'skript'

    def __init__(self, antwort):
        self.antwort = antwort

    def complete_json(self, messages, *, max_tokens, schema):
        nutzer = json.loads(messages[-1]['content'])
        ergebnis = self.antwort(nutzer) if callable(self.antwort) else self.antwort
        return Reply(text=json.dumps(ergebnis))


def stelle(text, name, art='person', rolle='mentioned', nach=0):
    start = text.index(name, nach)
    return {'kind': art, 'name': name, 'start': start, 'end': start + len(name), 'role': rolle}


@pytest.fixture
def welt(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    bezuege = Bezuege(episodes, workspace=workspace, eigene=lambda: [ICH])
    yield episodes, workspace, bezuege
    episodes.close()
    workspace.close()


def quelle(episodes, titel, text, teilnehmer=(), *, art=EpisodeKind.MESSAGE, tage=1, projekt=None, ref=None):
    episode, _ = episodes.record(
        art, titel, text, Provenance(SourceType.EMAIL if art is EpisodeKind.MESSAGE else SourceType.CALENDAR,
                                     source_ref=ref or f'test:{titel}'),
        participants=list(teilnehmer), project_id=projekt, occurred_at=JETZT - timedelta(days=tage))
    return episode


def sachen(bezuege):
    return {s['sache']: s['quellen'] for s in bezuege.sachen(limit=500)['sachen']}


def modell_lauf(episodes, antwort):
    Categories(episodes).run(Modell(antwort), limit=20)


# -- Anker ------------------------------------------------------------------


def test_adresse_als_absender_ist_ein_ankerbezug_zur_person_und_organisation(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Angebot', 'Hier das Angebot.', ['Sabine Becker <s.becker@klinikum-albanus.example>'])
    assert bezuege.aktualisieren()['offen'] == 0
    daten = bezuege.bezuege_der_quelle(e.id)
    belegt = {b['sache']: b['grundlagen'] for b in daten['bezuege']}
    assert belegt == {'person:a:s.becker@klinikum-albanus.example': ['anker'],
                      'organisation:klinikumalbanus': ['anker']}
    assert bezuege.beschriftung('person:a:s.becker@klinikum-albanus.example') == 'Sabine Becker'
    assert bezuege.beschriftung('organisation:klinikumalbanus') == 'Klinikum Albanus'


def test_eigene_adresse_und_private_anbieter_sind_keine_sachen(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Privat', 'Hallo', ['Tom <tom@gmail.com>', f'Lea <{ICH}>'])
    bezuege.aktualisieren()
    assert set(sachen(bezuege)) == {'person:a:tom@gmail.com'}
    assert org_aus_adresse('x@gmail.com') == '' and org_aus_adresse('x@mail.klinik.example') == 'klinik'
    assert org_aus_adresse('x@firma.co.uk') == 'firma'


def test_automatisches_postfach_ist_eine_organisation_kein_mensch(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Rechnung', 'Ihre Rechnung', ['Shop <no-reply@meinshop.example>'])
    bezuege.aktualisieren()
    assert set(sachen(bezuege)) == {'organisation:meinshop'}


@pytest.mark.parametrize('adresse', [
    'auftragsplanung@firma.example', 'auftragsabwicklung@firma.example',
    'auftrag-abwicklung+vorgang@firma.example',
])
def test_auftragsfunktionspostfach_ohne_absendernamen_ist_keine_person(welt, adresse):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Auftragsstand', 'Der Auftrag ist eingeplant.', [adresse])
    original = episodes.get(e.id).to_dict()

    bezuege.aktualisieren()

    daten = bezuege.bezuege_der_quelle(e.id)
    assert {b['sache']: b['grundlagen'] for b in daten['bezuege']} == {
        'organisation:firma': ['anker'],
    }
    assert daten['offen'] == []
    assert episodes.get(e.id).to_dict() == original


def test_personenname_im_text_vom_auftragsfunktionspostfach_bleibt_belegt(welt):
    episodes, _, bezuege = welt
    text = 'Anna Beispiel übernimmt den Termin.'
    e = quelle(episodes, 'Auftragsstand', text, ['Anna Beispiel <auftragsplanung@firma.example>'])
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Anna Beispiel')]})

    bezuege.aktualisieren()

    daten = bezuege.bezuege_der_quelle(e.id)
    assert {b['sache']: b['grundlagen'] for b in daten['bezuege']} == {
        'organisation:firma': ['anker'], 'person:n:anna beispiel': ['modell'],
    }
    person = next(b for b in daten['bezuege'] if b['art'] == 'person')
    beleg = person['stellen'][0]
    assert bezuege.zitat(e.id, beleg['start'], beleg['ende']) == 'Anna Beispiel'


def test_nutzer_bestaetigte_person_am_auftragsfunktionspostfach_bleibt_zugeordnet(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Auftragsstand', 'Der Auftrag ist eingeplant.', ['auftragsplanung@firma.example'])
    bezuege.aktualisieren()

    bezuege.nutzer_setzen(e.id, 'person:a:auftragsplanung@firma.example', 'zu')
    bezuege.aktualisieren()

    daten = bezuege.bezuege_der_quelle(e.id)
    assert {b['sache']: b['grundlagen'] for b in daten['bezuege']} == {
        'organisation:firma': ['anker'], 'person:a:auftragsplanung@firma.example': ['nutzer'],
    }


@pytest.mark.parametrize('person_bestaetigt', [False, True])
def test_alter_postfach_personenanker_wird_nach_neustart_einmalig_neuberechnet(
        tmp_path, monkeypatch, person_bestaetigt):
    from icarus_memory import bezuege as bezuege_modul

    path = tmp_path / 'episodes.sqlite3'
    episodes = EpisodeStore(path)
    e = quelle(episodes, 'Alter Auftragsstand', 'Der Auftrag ist eingeplant.', ['auftragsplanung@firma.example'])
    person = 'person:a:auftragsplanung@firma.example'
    alt = Bezuege(episodes)
    # Reproduce the prior rule and its persisted, unversioned address-only
    # cache. No category output or name-dependent register was involved.
    with monkeypatch.context() as vorher:
        vorher.setattr(bezuege_modul, 'maschinell', lambda adresse: False)
        alt.aktualisieren()
        alt.nutzer_setzen(e.id, 'thema:work', 'zu')
        if person_bestaetigt:
            alt.nutzer_setzen(e.id, person, 'zu')
    row = episodes._conn.execute('SELECT * FROM episodes WHERE id=?', (e.id,)).fetchone()
    alter_eingabewert = (
        f"{row['digest']}:{row['metadata_digest']}:{row['support_generation']}:{len(row['document'])}|::|:|"
    )
    with episodes.transaction():
        episodes._conn.execute('UPDATE sach_quellen SET eingabe=?, register=\'\' WHERE episode_id=?',
                               (alter_eingabewert, e.id))
    original = tuple(episodes._conn.execute('SELECT * FROM episodes WHERE id=?', (e.id,)).fetchone())
    entscheidungen = [tuple(row) for row in episodes._conn.execute('SELECT * FROM sach_nutzer ORDER BY sache')]
    episodes.close()

    episodes = EpisodeStore(path)
    try:
        aktuell = Bezuege(episodes)
        assert aktuell.aktualisieren()['berechnet'] == 1
        erwartet = {'organisation:firma': ['anker'], 'thema:work': ['nutzer']}
        if person_bestaetigt:
            erwartet[person] = ['nutzer']
        assert {b['sache']: b['grundlagen'] for b in aktuell.bezuege_der_quelle(e.id)['bezuege']} == erwartet
        assert aktuell.aktualisieren()['berechnet'] == 0
        assert tuple(episodes._conn.execute('SELECT * FROM episodes WHERE id=?', (e.id,)).fetchone()) == original
        assert [tuple(row) for row in episodes._conn.execute('SELECT * FROM sach_nutzer ORDER BY sache')] == entscheidungen
    finally:
        episodes.close()


def test_projektzuordnung_der_quelle_ist_ein_ankerbezug(welt):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Atlas', Provenance(SourceType.USER_STATED))
    e = quelle(episodes, 'Stand', 'Kurzer Stand.', projekt=projekt.id)
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(e.id)
    assert [(b['sache'], b['grundlagen']) for b in daten['bezuege']] == [(f'projekt:{projekt.id}', ['anker'])]
    assert bezuege.beschriftung(f'projekt:{projekt.id}') == 'Atlas'


def test_terminort_ist_ein_ortsbezug_ohne_modell(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Workshop', 'Termin: Workshop\nWann: Dienstag\nOrt: Akademie Taunus, Seminarraum 3, Bad Homburg\n'
               'Teilnehmer: Silke <s.vogt@akademie-taunus.example>', art=EpisodeKind.EVENT,
               teilnehmer=['Silke Vogt <s.vogt@akademie-taunus.example>'])
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(e.id)
    orte = {b['sache'] for b in daten['bezuege'] if b['art'] == 'ort'}
    # „Akademie Taunus“ ist die Organisation der Teilnehmerin: kein zweiter, gleichnamiger Ort.
    assert orte == {'ort:badhomburg'}
    akademie = next(b for b in daten['bezuege'] if b['sache'] == 'organisation:akademietaunus')
    assert akademie['grundlagen'] == ['anker'] and 'terminort' in akademie['rollen']
    assert bezuege.zitat(e.id, akademie['stellen'][0]['start'], akademie['stellen'][0]['ende']) == 'Akademie Taunus'
    assert all(b['grundlagen'] == ['anker'] for b in daten['bezuege'] if b['art'] == 'ort')
    stelle_ = next(b for b in daten['bezuege'] if b['sache'] == 'ort:badhomburg')['stellen'][0]
    assert bezuege.zitat(e.id, stelle_['start'], stelle_['ende']) == 'Bad Homburg'
    assert bezuege.beschriftung('ort:badhomburg') == 'Bad Homburg'


def test_terminort_ohne_gleichnamige_organisation_bleibt_ein_ort(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Forum', 'Termin: Forum\nOrt: Haus der Verbände, Frankfurt',
               art=EpisodeKind.EVENT, teilnehmer=['Miriam <miriam@kessler-diaet.example>'])
    bezuege.aktualisieren()
    sachen_ = {b['sache'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert {'ort:hausderverbände', 'ort:frankfurt', 'organisation:kesslerdiaet'} <= sachen_


@pytest.mark.parametrize('ort,gast,erwartet,nicht', [
    # Der Träger vorn, mit Rechtsform: dieselbe Organisation wie die Adresse.
    ('Akademie Taunus GmbH, Raum 2, Bad Homburg', 's.vogt@akademie-taunus.example',
     {'organisation:akademietaunus', 'ort:badhomburg'}, {'ort:akademietaunusgmbh'}),
    # Ein Ortsname bleibt Ort, auch wenn die Domäne so heißt; ebenso der Ort hinter der Postleitzahl.
    ('Mainz', 'presse@mainz.de', {'ort:mainz', 'organisation:mainz'}, set()),
    ('Rathaus, 55116 Mainz', 'buero@stadt.mainz.de', {'ort:rathaus', 'ort:mainz', 'organisation:mainz'}, set()),
])
def test_terminort_nur_der_traeger_wird_zur_organisation(welt, ort, gast, erwartet, nicht):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Termin', f'Termin: Treffen\nOrt: {ort}', art=EpisodeKind.EVENT, teilnehmer=[f'Gast <{gast}>'])
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(e.id)
    sachen_ = {b['sache'] for b in daten['bezuege']}
    assert erwartet <= sachen_ and not nicht & sachen_
    if 'ort:mainz' in erwartet:
        mainz = next(b for b in daten['bezuege'] if b['sache'] == 'ort:mainz')
        assert 'terminort' in mainz['rollen']
        assert 'terminort' not in next(b for b in daten['bezuege'] if b['sache'] == 'organisation:mainz')['rollen']


def test_terminort_neben_nur_erwaehnter_organisation_bleibt_ein_ort(welt):
    episodes, _, bezuege = welt
    text = 'Termin: Forum\nOrt: Haus der Verbände, Frankfurt\nDas Haus der Verbände lädt ein.'
    e = quelle(episodes, 'Forum', text, art=EpisodeKind.EVENT)
    modell_lauf(episodes, {'categories': [], 'entities': [
        stelle(text, 'Haus der Verbände', 'organization', nach=text.index('Das'))]})
    bezuege.aktualisieren()
    belegt = {b['sache']: b['grundlagen'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    # Die Erwähnung durch das Modell ist kein Anker: Der Terminort bleibt Ort, die Erwähnung bleibt, was sie ist.
    assert belegt['ort:hausderverbände'] == ['anker'] and belegt['organisation:hausderverbände'] == ['modell']


def test_neue_terminregel_rechnet_nur_termine_neu(welt):
    episodes, _, bezuege = welt
    mail = quelle(episodes, 'Mail', 'Hallo', ['Ben <ben@druck.example>'])
    termin = quelle(episodes, 'Termin', 'Termin: Treffen\nOrt: Frankfurt', art=EpisodeKind.EVENT)
    bezuege.aktualisieren()
    with episodes._lock:
        eingabe = dict(episodes._conn.execute('SELECT episode_id, eingabe FROM sach_quellen').fetchall())
    # Die Regelfassung der Mails bleibt die bisherige: Ein Update rechnet nicht den ganzen Bestand neu.
    assert eingabe[mail.id].endswith('|regeln:3') and eingabe[termin.id].endswith('|regeln:4')


def test_orte_im_termin_regeln():
    assert [k for k, *_ in orte_im_termin('online')] == []
    assert [k for k, *_ in orte_im_termin('Zoom')] == []
    assert [k for k, *_ in orte_im_termin('Rathaus, Platz 1, 55116 Mainz')] == ['rathaus', 'mainz']
    assert [k for k, *_ in orte_im_termin('Klinik am Mühlberg, Konferenzraum')] == ['klinikammühlberg']
    assert [k for k, *_ in orte_im_termin('Café Central')] == ['cafécentral']


# -- Modell -----------------------------------------------------------------


def test_erwaehnung_wird_nur_bei_eindeutigkeit_einer_person_zugeordnet(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Erstes', 'Hallo', ['Sabine Becker <s.becker@klinikum-albanus.example>'])
    text = 'Ich habe mit Sabine Becker gesprochen.'
    e = quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, lambda n: {'categories': [], 'entities': [stelle(text, 'Sabine Becker')]}
                if 'Sabine' in n['blocks'][0]['text'] else {'categories': [], 'entities': []})
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(e.id)
    assert [(b['sache'], b['grundlagen']) for b in daten['bezuege']] == [
        ('person:a:s.becker@klinikum-albanus.example', ['modell'])]
    assert daten['offen'] == []
    zitat = daten['bezuege'][0]['stellen'][0]
    assert bezuege.zitat(e.id, zitat['start'], zitat['ende']) == 'Sabine Becker'


def test_zwei_gleichnamige_bleiben_offen_mit_kandidaten_und_nutzer_entscheidet(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'A', 'Hallo aus dem Catering.', ['Alex Winter <alex@winter-catering.example>'])
    quelle(episodes, 'B', 'Hallo aus dem Institut.', ['Alex Winter <alex@winter-institut.example>'])
    text = 'Alex Winter meldet sich morgen.'
    e = quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, lambda n: {'categories': [], 'entities': [stelle(text, 'Alex Winter')]}
                if 'meldet' in n['blocks'][0]['text'] else {'categories': [], 'entities': []})
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(e.id)
    assert daten['bezuege'] == [] and len(daten['offen']) == 1
    assert daten['offen'][0]['kandidaten'] == ['person:a:alex@winter-catering.example',
                                              'person:a:alex@winter-institut.example']
    assert 'person:a:alex@winter-catering.example' not in sachen(bezuege) or sachen(bezuege)[
        'person:a:alex@winter-catering.example'] == 1
    # Ein Klick entscheidet für diese Quelle; die Erwähnung ist damit nicht mehr offen.
    bezuege.nutzer_setzen(e.id, 'person:a:alex@winter-catering.example', 'zu')
    daten = bezuege.bezuege_der_quelle(e.id)
    assert daten['offen'] == []
    assert [(b['sache'], b['grundlagen']) for b in daten['bezuege']] == [
        ('person:a:alex@winter-catering.example', ['nutzer'])]


def test_neue_gleichnamige_adresse_macht_eine_eindeutige_zuordnung_wieder_offen(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'A', 'Hallo aus dem Catering.', ['Alex Winter <alex@winter-catering.example>'])
    text = 'Alex Winter kommt.'
    e = quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, lambda n: {'categories': [], 'entities': [stelle(text, 'Alex Winter')]}
                if 'kommt' in n['blocks'][0]['text'] else {'categories': [], 'entities': []})
    bezuege.aktualisieren()
    assert [b['sache'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']] == ['person:a:alex@winter-catering.example']
    quelle(episodes, 'B', 'Hallo aus dem Institut.', ['Alex Winter <alex@winter-institut.example>'])
    bezuege.aktualisieren()
    daten = bezuege.bezuege_der_quelle(e.id)
    assert daten['bezuege'] == [] and len(daten['offen']) == 1


def test_ort_organisation_und_projekt_aus_erwaehnungen(welt):
    episodes, workspace, bezuege = welt
    projekt = workspace.add_project('Atlas', Provenance(SourceType.USER_STATED))
    text = 'Treffen in Mainz mit der Winter Catering GmbH zu Projekt Atlas und Projekt Zeus.'
    e = quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, {'categories': [{'category_id': 'work', 'block_id': 'B1'}], 'entities': [
        stelle(text, 'Mainz', 'place'), stelle(text, 'Winter Catering GmbH', 'organization'),
        stelle(text, 'Projekt Atlas', 'project'), stelle(text, 'Projekt Zeus', 'project')]})
    bezuege.aktualisieren()
    belegt = {b['sache']: b['grundlagen'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert belegt == {'ort:mainz': ['modell'], 'organisation:wintercatering': ['modell'],
                      f'projekt:{projekt.id}': ['modell'], 'projekt:n:zeus': ['modell'], 'thema:work': ['modell']}
    assert bezuege.beschriftung('ort:mainz') == 'Mainz'
    assert bezuege.beschriftung('organisation:wintercatering') == 'Winter Catering GmbH'


def test_domaene_und_erwaehnung_derselben_organisation_sind_eine_sache(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Mail', 'Hallo', ['Alex <alex@winter-catering.example>'])
    text = 'Angebot der Winter Catering GmbH liegt vor.'
    quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, lambda n: {'categories': [], 'entities': [stelle(text, 'Winter Catering GmbH', 'organization')]}
                if 'Angebot' in n['blocks'][0]['text'] else {'categories': [], 'entities': []})
    bezuege.aktualisieren()
    assert sachen(bezuege)['organisation:wintercatering'] == 2


def test_themen_ohne_aussage_werden_keine_sache(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'X', 'Etwas Unklares.')
    modell_lauf(episodes, {'categories': [{'category_id': 'unclear', 'block_id': 'B1'}], 'entities': []})
    bezuege.aktualisieren()
    assert not [s for s in sachen(bezuege) if s.startswith('thema:')]


def test_die_eigene_person_und_der_absender_als_erwaehnung_sind_keine_zusatzsache(welt):
    episodes, _, bezuege = welt
    quelle(episodes, 'Selbst', 'Hallo', [f'Lea Hartmann <{ICH}>'])
    text = 'Lea Hartmann schreibt: Sabine Becker meldet sich.'
    quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, lambda n: {'categories': [], 'entities': [stelle(text, 'Lea Hartmann')]}
                if 'schreibt' in n['blocks'][0]['text'] else {'categories': [], 'entities': []})
    bezuege.aktualisieren()
    assert not [s for s in sachen(bezuege) if s.startswith('person:')]


# -- Nutzer -----------------------------------------------------------------


def test_nutzer_ueberschreibt_modell_zuordnung_und_ablehnung(welt):
    episodes, _, bezuege = welt
    text = 'Treffen in Mainz.'
    e = quelle(episodes, 'Notiz', text)
    modell_lauf(episodes, {'categories': [], 'entities': [stelle(text, 'Mainz', 'place')]})
    bezuege.aktualisieren()
    assert sachen(bezuege) == {'ort:mainz': 1}
    # Ablehnen überstimmt das Modell ...
    daten = bezuege.nutzer_setzen(e.id, 'ort:mainz', 'nicht')
    assert daten['bezuege'] == [] and daten['abgelehnt'] == [{'sache': 'ort:mainz', 'art': 'ort'}]
    assert sachen(bezuege) == {}
    # ... und Entfernen der Entscheidung stellt den Fund des Programms wieder her.
    assert bezuege.nutzer_entfernen(e.id, 'ort:mainz') is True
    assert sachen(bezuege) == {'ort:mainz': 1}
    # Zuordnen fügt hinzu, was das Programm nicht fand.
    daten = bezuege.nutzer_setzen(e.id, 'thema:finance', 'zu')
    assert {b['sache']: b['grundlagen'] for b in daten['bezuege']} == {'ort:mainz': ['modell'], 'thema:finance': ['nutzer']}
    assert bezuege.nutzer_entfernen(e.id, 'thema:finance') is True
    assert bezuege.nutzer_entfernen(e.id, 'thema:finance') is False


def test_nutzer_mit_ungueltiger_sache_oder_entzogener_quelle_wird_abgewiesen(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Notiz', 'Text')
    with pytest.raises(ValueError):
        bezuege.nutzer_setzen(e.id, 'tier:hund', 'zu')
    with pytest.raises(ValueError):
        bezuege.nutzer_setzen(e.id, 'ort:mainz', 'vielleicht')
    episodes.ignore(e.id)
    with pytest.raises(LookupError):
        bezuege.nutzer_setzen(e.id, 'ort:mainz', 'zu')


def test_zuordnung_des_nutzers_gilt_fuer_den_text_der_quelle(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Notiz', 'Text', ['Ben <ben@druck.example>'])
    bezuege.aktualisieren()
    bezuege.nutzer_setzen(e.id, 'thema:finance', 'zu')
    assert 'thema:finance' in sachen(bezuege)
    # Nachgetragene Kontakte ändern die Quellenangaben, nicht den Text: Die Zuordnung bleibt, der neue Kontakt kommt
    # beim nächsten Abgleich dazu.
    episodes.add_contacts(e.id, [{'name': 'Ben', 'adresse': 'ben@druck.example', 'rolle': 'von', 'ich': False},
                                 {'name': 'Cem', 'adresse': 'cem@druck.example', 'rolle': 'an', 'ich': False}],
                          ['Ben <ben@druck.example>', 'Cem <cem@druck.example>'])
    assert 'thema:finance' in sachen(bezuege)
    stand = bezuege.aktualisieren()
    assert stand['berechnet'] == 1 and stand['offen'] == 0
    assert 'person:a:cem@druck.example' in sachen(bezuege) and 'thema:finance' in sachen(bezuege)
    assert bezuege.bezuege_der_quelle(e.id)['veraltet'] == []
    # Eine Entscheidung über einen anderen Text (gespeichert mit dessen Digest) gilt nicht: veraltet, ohne Wirkung.
    with episodes._lock:
        episodes._conn.execute("UPDATE sach_nutzer SET fingerprint = 'anderer-text:' || fingerprint WHERE episode_id = ?",
                               (e.id,))
    assert 'thema:finance' not in sachen(bezuege)
    daten = bezuege.bezuege_der_quelle(e.id)
    assert daten['veraltet'] == [{'sache': 'thema:finance', 'art': 'thema', 'aktion': 'zu'}]
    assert daten['berechnet'] is True


@pytest.mark.parametrize('mit_quellenschluessel', [True, False])
def test_entscheidung_des_nutzers_ueberlebt_ablage_und_nachtraege(welt, mit_quellenschluessel):
    episodes, workspace, bezuege = welt
    if mit_quellenschluessel:
        # Wie eine aufgenommene Mail: mit Quellenschlüssel und damit mit Quellenangaben-Digest.
        e, _ = episodes.record(EpisodeKind.MESSAGE, 'Notiz', 'Text zum Thema',
                               Provenance(SourceType.EMAIL, source_ref='m:1'), participants=['Ben <ben@druck.example>'],
                               occurred_at=JETZT, source_key='mail:test:1')
        episodes.advance_source_head('mail:test:1', None, e.id)
    else:
        e = quelle(episodes, 'Notiz', 'Text zum Thema', ['Ben <ben@druck.example>'], tage=0)
    ben, thema = 'person:a:ben@druck.example', 'thema:finance'
    bezuege.aktualisieren()
    bezuege.nutzer_setzen(e.id, ben, 'nicht')
    bezuege.nutzer_setzen(e.id, thema, 'zu')

    def gilt_noch():
        # Beide Lesewege: die Abfrage über alle Sachen (SQL) und die Ansicht einer Quelle (Python).
        assert ben not in sachen(bezuege) and thema in sachen(bezuege)
        assert bezuege.quellen_von(ben) == []
        assert [(q['episode_id'], q['grundlagen']) for q in bezuege.quellen_von(thema)] == [(e.id, ['nutzer'])]
        daten = bezuege.bezuege_der_quelle(e.id)
        assert daten['veraltet'] == [] and daten['abgelehnt'] == [{'sache': ben, 'art': 'person'}]

    gilt_noch()
    # Eine Projektzuordnung ist Ablage, keine neue Fassung: Beide Entscheidungen bleiben.
    projekt = workspace.add_project('Atlas', Provenance(SourceType.USER_STATED))
    episodes.link_project(e.id, projekt.id)
    bezuege.aktualisieren()
    gilt_noch()
    # Nachgetragene Kontakte, Kopfzeilen und Anhangberichte ändern die Quellenangaben, nicht den Text.
    episodes.add_contacts(e.id, [{'name': 'Ben', 'adresse': 'ben@druck.example', 'rolle': 'von', 'ich': False},
                                 {'name': 'Cem', 'adresse': 'cem@druck.example', 'rolle': 'an', 'ich': False}],
                          ['Ben <ben@druck.example>', 'Cem <cem@druck.example>'])
    episodes.add_mail_headers(e.id, ['mail-test:kopfzeile'])
    episodes.set_mail_attachment_report(e.id, {'abruf_vollstaendig': False})
    bezuege.aktualisieren()
    gilt_noch()
    assert 'person:a:cem@druck.example' in sachen(bezuege)
    # Verdichten und Archivieren sind ebenso Ablage.
    episodes.mark_consolidated(e.id)
    assert episodes.archive_before(JETZT + timedelta(days=1)) == 1
    bezuege.aktualisieren()
    gilt_noch()


def test_themenkorrektur_des_nutzers_hat_die_grundlage_nutzer(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Notiz', 'Rechnung für den Drucker.')
    modell_lauf(episodes, {'categories': [{'category_id': 'work', 'block_id': 'B1'}], 'entities': []})
    Categories(episodes).correct(e.id, ['finance'])
    bezuege.aktualisieren()
    belegt = {b['sache']: b['grundlagen'] for b in bezuege.bezuege_der_quelle(e.id)['bezuege']}
    assert belegt == {'thema:finance': ['nutzer']}
    assert bezuege.beschriftung('thema:finance') == 'Finanzen / Verträge'


# -- Entzug, Änderung, Neuberechnung ------------------------------------------


def test_entzug_entfernt_den_bezug_sofort_und_der_abgleich_die_zeilen(welt):
    episodes, _, bezuege = welt
    e = quelle(episodes, 'Notiz', 'Text', ['Ben <ben@druck.example>'])
    bezuege.aktualisieren()
    assert 'person:a:ben@druck.example' in sachen(bezuege)
    episodes.ignore(e.id)
    assert sachen(bezuege) == {}
    assert bezuege.bezuege_der_quelle(e.id) is None
    assert bezuege.quellen_von('person:a:ben@druck.example') == []
    assert episodes._conn.execute('SELECT COUNT(*) FROM sach_bezuege').fetchone()[0] > 0
    assert bezuege.aktualisieren()['entfernt'] == 1
    assert episodes._conn.execute('SELECT COUNT(*) FROM sach_bezuege').fetchone()[0] == 0


def test_neue_fassung_ersetzt_die_alte_und_nur_die_neue_traegt_bezuege(welt):
    episodes, _, bezuege = welt
    alt = quelle(episodes, 'Termin', 'Termin: X\nOrt: Mainz', art=EpisodeKind.EVENT, ref='cal:1')
    with episodes.transaction():
        episodes._conn.execute("UPDATE episodes SET source_key='cal:x' WHERE id=?", (alt.id,))
    episodes.advance_source_head('cal:x', None, alt.id)
    bezuege.aktualisieren()
    assert 'ort:mainz' in sachen(bezuege)
    neu, _ = episodes.record(EpisodeKind.EVENT, 'Termin', 'Termin: X\nOrt: Wiesbaden',
                             Provenance(SourceType.CALENDAR, source_ref='cal:1b'), source_key='cal:x',
                             occurred_at=JETZT)
    episodes.advance_source_head('cal:x', alt.id, neu.id)
    assert set(sachen(bezuege)) == set()  # Kopf ist neu, aber noch nicht berechnet
    bezuege.aktualisieren()
    assert set(sachen(bezuege)) == {'ort:wiesbaden'}


def test_abgleich_rechnet_nur_neues_und_geaendertes(welt):
    episodes, _, bezuege = welt
    for n in range(3):
        quelle(episodes, f'Q{n}', f'Text {n}', [f'Person {n} <p{n}@firma{n}.example>'])
    assert bezuege.aktualisieren()['berechnet'] == 3
    assert bezuege.aktualisieren() == {'berechnet': 0, 'entfernt': 0, 'offen': 0}
    quelle(episodes, 'Q3', 'Text 3', ['Person 3 <p3@firma3.example>'])
    assert bezuege.aktualisieren()['berechnet'] == 1


def test_stand_und_begrenzter_abgleich_nennen_was_noch_offen_ist(welt):
    episodes, _, bezuege = welt
    for n in range(5):
        quelle(episodes, f'Q{n}', f'Text {n}', [f'P{n} <p{n}@f{n}.example>'])
    assert bezuege.stand() == {'quellen': 5, 'offen': 5}
    assert bezuege.aktualisieren(max_quellen=2) == {'berechnet': 2, 'entfernt': 0, 'offen': 3}
    assert bezuege.stand() == {'quellen': 5, 'offen': 3}
    assert bezuege.aktualisieren()['offen'] == 0


def test_sachenliste_nennt_gesamtzahl_und_blaettert(welt):
    episodes, _, bezuege = welt
    for n in range(4):
        quelle(episodes, f'Q{n}', f'Text {n}', [f'P{n} <p{n}@f{n}.example>'], tage=n + 1)
    bezuege.aktualisieren()
    seite = bezuege.sachen(art='person', limit=3)
    assert seite['gesamt'] == 4 and len(seite['sachen']) == 3
    assert seite['sachen'][0]['sache'] == 'person:a:p0@f0.example'  # jüngste zuerst
    assert bezuege.sachen(art='person', limit=3, offset=3)['sachen'][0]['sache'] == 'person:a:p3@f3.example'
    assert bezuege.sachen(suche='f2')['gesamt'] == 2  # Person und Organisation


def test_migration_baut_orte_ein_und_hebt_die_taxonomie_nur_bei_vorhandenem_bestand(tmp_path):
    from tests.working_memory_legacy import downgrade_terms  # noqa: F401 - gleiche Hilfe wie die Nachbartests
    pfad = tmp_path / 'e.sqlite3'
    episodes = EpisodeStore(pfad)
    # Frische Installation: Gesundheit ergänzt die Taxonomie, nicht den Bestand.
    assert episodes._conn.execute('SELECT taxonomy_version, corpus_version FROM memory_category_scan').fetchone()[:] == (2, 1)
    assert episodes._conn.execute('PRAGMA user_version').fetchone()[0] == 22
    # Orte sind als Art zulässig, unbekannte nicht.
    episodes._conn.execute("INSERT INTO memory_category_entities VALUES ('e','f','place',0,1,'mentioned')")
    with pytest.raises(Exception):
        episodes._conn.execute("INSERT INTO memory_category_entities VALUES ('e','f','tier',0,1,'mentioned')")
    episodes.close()


def test_migration_mit_vorhandenem_bestand_behaelt_zeilen_und_wertet_neu_aus(tmp_path):
    from icarus_memory import memory_categories
    episodes = EpisodeStore(tmp_path / 'e.sqlite3')
    verbindung = episodes._conn
    versionen_vorher = tuple(verbindung.execute('SELECT taxonomy_version, corpus_version FROM memory_category_scan').fetchone())
    verbindung.execute("INSERT INTO memory_category_sources(episode_id,fingerprint,taxonomy_version,status,model,retry_after,support_generation) VALUES ('e-1','fp',1,'complete','m',NULL,0)")
    verbindung.execute("INSERT INTO memory_category_entities VALUES ('e-1','fp','person',0,5,'mentioned')")
    with episodes.transaction():
        memory_categories.migrate_ort(verbindung)
    # Zeilen bleiben, die Taxonomie wird angehoben, damit Orte auch im Bestand gefunden werden.
    assert verbindung.execute('SELECT kind FROM memory_category_entities').fetchall()[0][0] == 'person'
    assert tuple(verbindung.execute('SELECT taxonomy_version, corpus_version FROM memory_category_scan').fetchone()) == (versionen_vorher[0] + 1, versionen_vorher[0] + 1)
    memory_categories.verify(verbindung)
    episodes.close()
