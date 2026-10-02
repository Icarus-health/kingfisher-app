"""Kreis je Person (M4): Vorschlag mit Begründung, Fakt erst nach Bestätigung, nie automatisch geändert, Wirkung.

Zusicherungen (jede mit Sabotageprobe, docs/49-kreis-und-privat.md):

1. Der Vorschlag folgt den Merkmalen: Familie in den inneren Kreis, Kollegen mit Firmenadresse, sonst Kontakte.
2. Ein Fremder landet nie im inneren Kreis, auch nicht mit „Hallo Mama“ und einer Antwort.
3. Die Begründung nennt die Merkmale in einem Satz.
4. Ein Vorschlag schreibt nichts; erst die Bestätigung legt den Kreis fest.
5. Ein bestätigter Kreis wird nie automatisch geändert; ein neuer Vorschlag steht nur daneben.
6. Wirkung: Fristen aus der Akte eines bestätigten Kontakts erscheinen nicht ungefragt im Briefing.
7. Wirkung: Der Antwortkontext kennzeichnet den Kreis; der Export nennt ihn.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from icarus_memory import fristlage, kreis
from icarus_memory.akten_routes import bausteine, nachfuehren
from icarus_memory.episodes import EpisodeKind
from icarus_memory.kreis import Merkmale, vorschlagen
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_source_answers_http import _api

ICH = 'lea@hartmann-beratung.example'
MAMA = 'gabi.hartmann@gmx.example'
KOLLEGE = 'jan.vogt@klinik-nord.example'
FREMD = 'neue.nummer@web.example'
PRAXIS = 'empfang@zahnarzt-kraemer.example'


@pytest.fixture
def api(core, tmp_path, monkeypatch):
    app, client, _ = _api(core, tmp_path, monkeypatch)
    app.state.settings.mail.user = ICH
    try:
        yield app, client
    finally:
        client.close()


_ZAEHLER = [0]


def mail(app, von: str, an: str, text: str, *, tage: int, titel: str = 'Hallo', name: str = '', arten=None):
    """Eine Mail mit Rollen wie aus der Aufnahme: `von` schreibt an `an`; die eigene Adresse trägt `ich`."""
    _ZAEHLER[0] += 1
    text = f'{text}\n\n(Nachricht {_ZAEHLER[0]})'   # gleicher Wortlaut wäre dieselbe Quelle
    kontakte = [{'name': name if von != ICH else 'Lea Hartmann', 'adresse': von, 'rolle': 'von', 'ich': von == ICH},
                {'name': name if an != ICH else 'Lea Hartmann', 'adresse': an, 'rolle': 'an', 'ich': an == ICH}]
    teilnehmer = [f'{k["name"]} <{k["adresse"]}>' for k in kontakte if not k['ich'] or k['rolle'] == 'von']
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, titel, text,
        Provenance(SourceType.EMAIL, source_ref=f'kreis:<{_ZAEHLER[0]}@example.invalid>'),
        participants=teilnehmer, contacts=kontakte, occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    if arten:
        store = WorkingMemoryStore(app.state.episodes)
        pending = store.pending(episode_ids=[episode.id])[0]
        items, pos = [], 0
        for teil, art in arten:  # noqa: B007
            start = text.index(teil, pos)
            items.append({'start': start, 'end': start + len(teil), 'kind': art})
            pos = start + len(teil)
        assert store.commit(pending, items, model='local-test')
    return episode


def termin(app, titel: str, gast: str, *, tage: int):
    episode, _ = app.state.episodes.record(
        EpisodeKind.EVENT, titel, f'{titel}\nOrt: Wiesbaden',
        Provenance(SourceType.CALENDAR, source_ref=f'kalender:{titel}:{tage}'),
        participants=[f'Gast <{gast}>'], occurred_at=datetime.now(timezone.utc) - timedelta(days=tage))
    return episode


def familie(app):
    """Mama: privater Anbieter, Du, familiäre Anrede, Mails in beide Richtungen über Monate, ein Termin."""
    for tage in (150, 120, 90, 40):
        mail(app, MAMA, ICH, 'Hallo Lea, wie geht es dir? Hab dich lieb, deine Mama', tage=tage, name='Gabi Hartmann')
        mail(app, ICH, MAMA, 'Hallo Mama, mir geht es gut. Bis Sonntag!', tage=tage - 1, name='Gabi Hartmann')
    termin(app, 'Kaffee bei Mama', MAMA, tage=30)


def kollege(app):
    for tage in (60, 30, 10):
        mail(app, KOLLEGE, ICH, 'Sehr geehrte Frau Hartmann, anbei das Protokoll. Mit freundlichen Grüßen, Jan Vogt',
             tage=tage, name='Jan Vogt', titel='Protokoll')
        mail(app, ICH, KOLLEGE, 'Sehr geehrter Herr Vogt, vielen Dank. Mit freundlichen Grüßen', tage=tage - 1,
             name='Jan Vogt', titel='Re: Protokoll')
    termin(app, 'Projekttreffen Ernährungsteam', KOLLEGE, tage=5)


def fremder(app):
    """Der bekannte Betrug: „Hallo Mama, das ist meine neue Nummer“, und eine Antwort darauf."""
    mail(app, FREMD, ICH, 'Hallo Mama, das ist meine neue Nummer. Kannst du mir schnell helfen? Hab dich lieb',
         tage=3, name='Unbekannt')
    mail(app, ICH, FREMD, 'Hallo, wer bist du denn?', tage=2, name='Unbekannt')


def kreise(app):
    nachfuehren(app, warten=True)
    from icarus_memory.kreis_routes import kreise as bauen
    return bauen(app)


# -- 1. bis 3.: Vorschlag und Begründung -------------------------------------------------


def test_familie_wird_innerer_kreis_mit_begruendung_aus_den_merkmalen(api):
    app, _ = api
    familie(app)
    vorschlag = kreise(app).vorschlag(f'person:a:{MAMA}')
    assert vorschlag.kreis == kreis.INNERER_KREIS
    m = vorschlag.merkmale
    assert (m.von_ihr, m.von_dir, m.termine, m.privat, m.familiaer.casefold()) == (4, 4, 1, True, 'mama')
    assert m.monate >= 2 and m.du and m.vorname
    satz = vorschlag.begruendung
    assert satz.startswith('8 Mails in beide Richtungen seit ') and satz.endswith('.')
    for merkmal in ('privater Anbieter', 'ein gemeinsamer Termin', 'Anrede „'):
        assert merkmal in satz, satz


def test_kollege_mit_firmenadresse_und_termin_wird_kollegen(api):
    app, _ = api
    kollege(app)
    vorschlag = kreise(app).vorschlag(f'person:a:{KOLLEGE}')
    assert vorschlag.kreis == kreis.KOLLEGEN
    assert 'Firmenadresse' in vorschlag.begruendung and 'per Sie' in vorschlag.begruendung
    assert 'ein gemeinsamer Termin' in vorschlag.begruendung


def test_ein_fremder_landet_nie_im_inneren_kreis(api):
    app, _ = api
    fremder(app)
    vorschlag = kreise(app).vorschlag(f'person:a:{FREMD}')
    assert vorschlag.kreis == kreis.KONTAKTE
    assert vorschlag.merkmale.familiaer  # die Anrede ist da, sie allein reicht nicht
    assert '2 Mails in beide Richtungen' in vorschlag.begruendung


def test_nur_eine_richtung_und_dienstleister_bleiben_kontakte():
    newsletter = Merkmale('info@laden.example', von_ihr=9, seit='2026-01-02', monate=8)
    assert vorschlagen(newsletter).kreis == kreis.KONTAKTE
    assert vorschlagen(newsletter).begruendung == 'Neun Mails an dich, keine Antwort von dir, Firmenadresse.'
    praxis = Merkmale(PRAXIS, von_ihr=5, von_dir=4, seit='2026-01-02', monate=6, termine=2, du=True, vorname=True,
                      dienst='gesundheit')
    assert vorschlagen(praxis).kreis == kreis.KONTAKTE
    assert 'Absender aus dem Bereich Gesundheit' in vorschlagen(praxis).begruendung


@pytest.mark.parametrize(('aenderung', 'erwartet'), [
    ({}, kreis.INNERER_KREIS),
    ({'monate': 1}, kreis.KONTAKTE),           # ein Monat ist kein Verhältnis
    ({'von_dir': 0}, kreis.KONTAKTE),          # nur eine Richtung
    ({'von_ihr': 1, 'von_dir': 1}, kreis.KONTAKTE),
    ({'familiaer': '', 'termine': 0}, kreis.INNERER_KREIS),   # Du, Vorname, privater Anbieter
    ({'familiaer': '', 'privat': False, 'termine': 0}, kreis.KOLLEGEN),
    ({'familiaer': '', 'privat': False}, kreis.KOLLEGEN),   # Du, Vorname und Termine sind unter Kollegen üblich
    ({'eigene_firma': True, 'privat': False}, kreis.KOLLEGEN),
])
def test_schwellen_des_inneren_kreises(aenderung, erwartet):
    basis = dict(adresse=MAMA, von_ihr=3, von_dir=3, seit='2026-03-01', monate=4, termine=1, privat=True, du=True,
                 vorname=True, familiaer='Mama')
    assert vorschlagen(Merkmale(**{**basis, **aenderung})).kreis == erwartet


def test_anrede_liest_nur_den_eigenen_text_nicht_das_zitat():
    gelesen = kreis.anrede(['Sehr geehrte Frau Hartmann,\nIhre Unterlagen sind da.\n\nAm 3. März schrieb Lea:\n> Hallo Mama'])
    assert gelesen == {'du': False, 'vorname': False, 'sie': True, 'familiaer': ''}
    assert kreis.anrede(['Hi Lea!\nKommst du morgen?'])['vorname'] is True
    assert kreis.anrede(['Liebe Frau Becker,\nkommst du?'])['vorname'] is False


# -- 4. und 5.: Fakt erst nach Bestätigung, nie automatisch geändert -------------------------


def _zeilen(app) -> int:
    return app.state.episodes._conn.execute('SELECT COUNT(*) FROM personen_kreis').fetchone()[0]


def test_vorschlag_schreibt_nichts_erst_die_bestaetigung(api):
    app, client = api
    familie(app)
    sache = f'person:a:{MAMA}'
    stand = client.get('/api/v1/kreis', params={'sache': sache}).json()
    assert (stand['kreis'], stand['bestaetigt'], stand['vorschlag']['kreis']) == ('unbestimmt', False, 'innerer_kreis')
    assert [w['kreis'] for w in stand['wahlen']] == ['innerer_kreis', 'kollegen', 'kontakte']
    uebersicht = client.get('/api/v1/kreis/uebersicht').json()
    assert (uebersicht['bestaetigt'], uebersicht['offen']) == (0, 1)
    assert uebersicht['offen_je_kreis'] == {'innerer_kreis': 1, 'kollegen': 0}
    assert uebersicht['vorschlaege'][0]['sache'] == sache and uebersicht['vorschlaege'][0]['name'] == 'Gabi Hartmann'
    # Der Abgleich ist in der Anfrage fertig: die Zahl ist endgültig, nicht vorläufig.
    assert uebersicht['zaehlt_noch'] is False
    assert _zeilen(app) == 0
    akte = client.get('/api/v1/akten/akte', params={'sache': sache}).json()
    assert akte['kreis'] == 'unbestimmt'
    fest = client.put('/api/v1/kreis', json={'sache': sache, 'kreis': 'innerer_kreis'}).json()
    assert (fest['kreis'], fest['bestaetigt'], fest['neuer_vorschlag']) == ('innerer_kreis', True, False)
    assert _zeilen(app) == 1
    assert client.get('/api/v1/akten/akte', params={'sache': sache}).json()['kreis'] == 'innerer_kreis'
    uebersicht = client.get('/api/v1/kreis/uebersicht').json()
    assert (uebersicht['bestaetigt'], uebersicht['offen'], uebersicht['je_kreis']['innerer_kreis']) == (1, 0, 1)


def test_bestaetigter_kreis_bleibt_auch_wenn_sich_die_lage_aendert(api):
    app, client = api
    kollege(app)
    sache = f'person:a:{KOLLEGE}'
    client.put('/api/v1/kreis', json={'sache': sache, 'kreis': 'kontakte'})
    # Neue Lage: Kingfisher würde weiter „Kollegen“ vorschlagen; bestätigt bleibt „Kontakte“.
    mail(app, KOLLEGE, ICH, 'Sehr geehrte Frau Hartmann, noch ein Nachtrag.', tage=1, name='Jan Vogt')
    stand = client.get('/api/v1/kreis', params={'sache': sache}).json()
    assert (stand['kreis'], stand['vorschlag']['kreis'], stand['neuer_vorschlag']) == ('kontakte', 'kollegen', True)
    assert client.get('/api/v1/kreis/uebersicht').json()['geaendert'] == 1
    zurueck = client.delete('/api/v1/kreis', params={'sache': sache}).json()
    assert (zurueck['kreis'], zurueck['bestaetigt']) == ('unbestimmt', False)
    assert client.delete('/api/v1/kreis', params={'sache': sache}).status_code == 404


def test_routen_pruefen_eingaben_und_token(api):
    _, client = api
    assert client.put('/api/v1/kreis', json={'sache': f'person:a:{MAMA}', 'kreis': 'familie'}).status_code == 422
    assert client.put('/api/v1/kreis', json={'sache': 'organisation:x', 'kreis': 'kontakte'}).status_code == 422
    assert client.get('/api/v1/kreis', params={'sache': 'projekt:x'}).status_code == 422
    assert client.get('/api/v1/kreis/uebersicht', headers={'X-Icarus-Token': 'falsch'}).status_code in (401, 403)
    assert client.put('/api/v1/kreis', json={'sache': f'person:a:{MAMA}', 'kreis': 'kontakte'},
                      headers={'X-Icarus-Token': 'falsch'}).status_code in (401, 403)


# -- 6. Wirkung im Briefing ---------------------------------------------------------------------


def _frist_des_kontakts(app):
    frist = (date.today() + timedelta(days=3)).strftime('%d.%m.%Y')
    satz = f'Bitte schicken Sie mir die Unterlagen bis zum {frist}.'
    return mail(app, 'm.roth@verlag-roth.example', ICH, satz, tage=2, name='Maria Roth', titel='Unterlagen',
                arten=[(satz, 'request')])


def _briefing_fristen(app):
    nachfuehren(app, warten=True)
    bezuege, akten = bausteine(app)
    return fristlage.sammeln(akten, bezuege, jetzt=datetime.now().astimezone(), eigene=[ICH])


def test_fristen_eines_bestaetigten_kontakts_erscheinen_nicht_ungefragt_im_briefing(api):
    app, client = api
    quelle = _frist_des_kontakts(app)
    sache = 'person:a:m.roth@verlag-roth.example'
    # Ohne Bestätigung bleibt alles, wie es war: Die Frist steht im Briefing, mit der Person als Akte.
    vorher = _briefing_fristen(app)
    assert [(f.episode_id, f.sache) for f in vorher] == [(quelle.id, sache)]
    client.put('/api/v1/kreis', json={'sache': sache, 'kreis': 'kontakte'})
    nachher = _briefing_fristen(app)
    # Über die Akte der Organisation (direkter Bezug) bleibt sie, nie über die Akte des Kontakts.
    assert all(f.sache != sache for f in nachher)
    assert [f.sache for f in nachher] == ['organisation:verlagroth']
    # Gefragt bleibt alles erreichbar: Die Akte der Person zeigt die Frist weiter.
    akte = client.get('/api/v1/akten/akte', params={'sache': sache}).json()
    assert akte['fristen']['gesamt']['kommend'] == 1


def test_ohne_andere_akte_faellt_die_frist_eines_kontakts_ganz_weg():
    f = fristlage.Frist(datum=date.today(), text='x', ausdruck='heute', episode_id='e-1', titel='t', quelle_datum=None,
                        quelle_art='Mail', art='Bitte', richtung='an_mich', status='kommend', tage=0,
                        sache='person:a:x@y.example', kreis='kontakte')
    assert fristlage.ohne_kontakte([f]) == []
    innen = fristlage.Frist(**{**f.__dict__, 'kreis': 'innerer_kreis'})
    assert fristlage.ohne_kontakte([innen]) == [innen]
    assert f.to_dict()['kreis'] == 'kontakte'


def test_kollegen_sprechen_sachlich_ueber_das_projekt():
    basis = dict(datum=date.today(), text='x', ausdruck='heute', episode_id='e-1', titel='t', quelle_datum=None,
                 quelle_art='Mail', art='Bitte', richtung='an_mich', status='kommend', tage=0)
    person = fristlage.Frist(**basis, sache='person:a:x@y.example', kreis='kollegen')
    projekt = fristlage.Frist(**basis, sache='projekt:p-1')
    assert fristlage.nach_dringlichkeit([person, projekt])[0].sache == 'projekt:p-1'
    offen = fristlage.Frist(**basis, sache='person:a:x@y.example')
    assert fristlage.nach_dringlichkeit([projekt, offen])[0].sache == 'person:a:x@y.example'   # wie bisher


# -- 7. Wirkung im Antwortkontext und im Export ----------------------------------------------------


def test_antwortkontext_kennzeichnet_den_bestaetigten_kreis(api):
    app, client = api
    familie(app)
    quelle = mail(app, MAMA, ICH, 'Hallo Lea, am Samstag habe ich Geburtstag.', tage=1, name='Gabi Hartmann')
    nachfuehren(app, warten=True)
    from icarus_memory import akten_kontext
    _, akten = bausteine(app)
    ohne = akten_kontext.aufbauen(app.state.episodes, None, [quelle.id], akten=akten)
    assert ohne.kreise == {} and akten_kontext.hinweis_kreis(ohne, quelle.id) == []
    assert 'kreise' not in ohne.als_dict()   # ohne Kreis bleibt der gespeicherte Kontext wie bisher
    client.put('/api/v1/kreis', json={'sache': f'person:a:{MAMA}', 'kreis': 'innerer_kreis'})
    mit = akten_kontext.aufbauen(app.state.episodes, None, [quelle.id], akten=akten)
    assert mit.kreise == {f'person:a:{MAMA}': 'innerer_kreis'}
    assert akten_kontext.kreis_der_quelle(mit, quelle.id) == 'innerer_kreis'
    assert akten_kontext.hinweis_kreis(mit, quelle.id) == [
        'Gabi Hartmann – innerer Kreis: mit Vornamen nennen, Alltägliches (Geburtstag, Termine) darf vorkommen']
    assert mit.signatur != ohne.signatur   # eine alte Antwort gilt danach als veraltet
    wieder = akten_kontext.Kontext.aus_dict(mit.als_dict())
    assert wieder is not None and wieder.kreise == mit.kreise and wieder.personen == mit.personen


def test_export_nennt_den_kreis_im_kopf(api):
    app, client = api
    familie(app)
    sache = f'person:a:{MAMA}'
    client.put('/api/v1/kreis', json={'sache': sache, 'kreis': 'innerer_kreis'})
    from icarus_memory import akten_markdown
    nachfuehren(app, warten=True)
    _, akten = bausteine(app)
    daten = akten.akte(sache, alle=True)
    e = akten_markdown.AkteIn(sache=sache, art='person', name=daten['name'], akte=daten)
    datei = akten_markdown.bauen([e], stand=date(2026, 10, 1), version='9.9.9', info=lambda episode_id: None)
    text = next(inhalt for pfad, inhalt in datei.items() if pfad.startswith('Personen/'))
    assert 'kreis: "innerer_kreis"' in text.split('---')[1]
