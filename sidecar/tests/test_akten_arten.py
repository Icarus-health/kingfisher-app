"""Private Akten-Arten (M4): Vorschlag aus dem Absender, Bestätigung, Fristen mit Beleg und nie geraten.

Zusicherungen (jede mit Sabotageprobe, docs/49-kreis-und-privat.md):

1. Die Art schlägt allein der Absender vor (Praxis, Versicherung, Stadtwerke, Kita); ein Betreff stützt nur.
2. Erst die Bestätigung legt die Art fest; „Keine davon“ ist eine Antwort und stellt die Fristensuche ab.
3. Fristen nur mit ausgeschriebenem Kalenderdatum, das noch kommt; Erledigtes („eingegangen“) ist keine Frist.
4. Jede Zahl im Vorschlag steht wörtlich in der Quelle; der Beleg ist die Textstelle.
5. Fristen werden Aufgabenvorschläge, nie Aufgaben; was einmal vorgeschlagen war, kommt nicht wieder.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from icarus_memory import akten_arten
from icarus_memory.akten_arten import fristen_finden, vorschlagen, zahlen_belegt
from icarus_memory.akten_routes import bausteine, nachfuehren
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_kreis import ICH, api, mail  # noqa: F401 - Fixture und Hilfen

PRAXIS = 'empfang@zahnarzt-kraemer.example'
VERSICHERUNG = 'service@rheinland-versicherung.example'
BEZUG = datetime(2026, 9, 10, 9, 0, tzinfo=timezone.utc)


def kuenftig(tage: int) -> date:
    return date.today() + timedelta(days=tage)


# -- 1. Vorschlag aus dem Absender -------------------------------------------------------


@pytest.mark.parametrize(('absender', 'betreffe', 'art'), [
    (['Zahnarztpraxis Dr. Krämer', 'zahnarzt-kraemer'], ['Ihre Rechnung'], 'gesundheit'),
    (['rheinland-versicherung'], ['Beitragsanpassung 2027'], 'vertraege'),
    (['Stadtwerke Wiesbaden'], ['Abschlag Strom'], 'haushalt'),
    (['Hausverwaltung Uferzeile'], ['Nebenkostenabrechnung'], 'haushalt'),
    (['kita-sonnenblume'], ['Elternabend'], 'familie'),
    (['Grundschule am Park'], [], 'familie'),
])
def test_absender_traegt_den_vorschlag(absender, betreffe, art):
    vorschlag = vorschlagen(absender, betreffe)
    assert vorschlag.art == art
    assert vorschlag.begruendung.startswith(f'Absender „{absender[0]}“')


@pytest.mark.parametrize(('absender', 'betreffe'), [
    (['klinikum-albanus', 'Sabine Becker'], ['Rahmenvertrag', 'Rechnung März']),   # Beruf: Betreff allein trägt nicht
    (['klinikum-albanus'], ['Vertrag Folgeprojekt', 'Kündigung der Rahmenvereinbarung']),
    (['hochschule-rheinmain-med'], ['Lehrauftrag']),
    (['physioplaner'], ['Ihre Lizenz']),
])
def test_ohne_privaten_absender_kein_vorschlag(absender, betreffe):
    assert vorschlagen(absender, betreffe).art == ''


def test_betreff_entscheidet_nur_zwischen_zwei_absendern():
    # „Versicherung“ und „Praxis“ im Absender: Der Betreff „Rezept“ stützt Gesundheit.
    assert vorschlagen(['Praxis und Versicherung'], ['Ihr Rezept']).art == 'gesundheit'
    assert vorschlagen(['Praxis und Versicherung'], ['Ihre Police']).art == 'vertraege'


# -- 3. und 4. Fristen ---------------------------------------------------------------------


def test_zahlungsfrist_mit_betrag_im_satz():
    text = ('Sehr geehrte Frau Hartmann,\nanbei die Rechnung Nr. 4711 für die Zahnreinigung. Bitte überweisen Sie '
            f'86,40 € bis zum {kuenftig(20):%d.%m.%Y} auf unser Konto.\nMit freundlichen Grüßen')
    [frist] = fristen_finden(text, BEZUG)
    assert (frist.art, frist.datum, frist.betrag) == ('zahlung', kuenftig(20), '86,40 €')
    assert frist.satz in text and frist.ausdruck in frist.satz
    assert frist.aussage('Zahnarztpraxis Dr. Krämer') == (
        f'Zahlung bis {kuenftig(20):%d.%m.%Y}: 86,40 € (Zahnarztpraxis Dr. Krämer)')
    assert zahlen_belegt(frist.aussage(''), text) == []


def test_betrag_aus_der_betragszeile_und_kuendigung_mit_monatsname():
    monat = ('Januar', 'Februar', 'März', 'April', 'Mai', 'Juni', 'Juli', 'August', 'September', 'Oktober',
             'November', 'Dezember')[kuenftig(40).month - 1]
    ausdruck = f'{kuenftig(40).day}. {monat} {kuenftig(40).year}'
    text = (f'Rechnungsbetrag: 1.234,50 EUR\nDer Betrag ist fällig am {kuenftig(10):%d.%m.%Y}.\n'
            f'Ihr Vertrag verlängert sich um ein Jahr, wenn Sie nicht bis zum {ausdruck} kündigen.')
    zahlung, kuendigung = fristen_finden(text, BEZUG)
    assert (zahlung.art, zahlung.betrag, zahlung.datum) == ('zahlung', '1.234,50 EUR', kuenftig(10))
    assert (kuendigung.art, kuendigung.ausdruck, kuendigung.betrag) == ('kuendigung', ausdruck, '')
    assert kuendigung.aussage('Rheinland') == f'Kündigung möglich bis {ausdruck} (Rheinland)'


@pytest.mark.parametrize('satz', [
    'Bitte überweisen Sie den Betrag innerhalb von zwei Wochen.',          # nicht ausgeschrieben: nie gerechnet
    'Bitte überweisen Sie den Betrag bis Freitag.',
    'Die Kündigung ist zum Ende Oktober möglich.',
    'Ihre Zahlung vom {heute} ist eingegangen, vielen Dank.',             # erledigt
    'Ihr Vertrag wurde zum {kuenftig} gekündigt.',                         # Bestätigung, keine Frist
    'Bitte überweisen Sie 20,00 € bis zum {vergangen}.',                  # verstrichen
    'Wir sehen uns am {kuenftig} zur Kontrolle.',                          # kein Zahlungs- oder Kündigungswort
])
def test_keine_frist_ohne_beleg_oder_wenn_erledigt(satz):
    text = satz.format(heute=f'{date.today():%d.%m.%Y}', kuenftig=f'{kuenftig(30):%d.%m.%Y}',
                       vergangen=f'{date.today() - timedelta(days=3):%d.%m.%Y}')
    assert fristen_finden(text, BEZUG) == []


def test_zahlen_belegt_findet_erfundene_zahlen():
    assert zahlen_belegt('Zahlung bis 15.10.2026: 86,40 €', 'Bitte 86,40 € bis 15.10.2026.') == []
    assert zahlen_belegt('Zahlung bis 15.10.2026: 86,50 €', 'Bitte 86,40 € bis 15.10.2026.') == ['86,50']


# -- 2. und 5. Ablage, Routen, Aufgabenvorschläge ---------------------------------------------------


def _rechnung(app, tage_bis: int = 20, *, von: str = PRAXIS, betrag: str = '86,40 €', titel: str = 'Ihre Rechnung',
              name: str = 'Zahnarztpraxis Dr. Krämer'):
    satz = f'Bitte überweisen Sie {betrag} bis zum {kuenftig(tage_bis):%d.%m.%Y}.'
    return mail(app, von, ICH, f'Sehr geehrte Frau Hartmann,\nanbei Ihre Rechnung. {satz}\nMit freundlichen Grüßen',
                tage=2, name=name, titel=titel), satz


def test_art_wird_vorgeschlagen_und_erst_mit_klick_fest(api):
    app, client = api
    _rechnung(app)
    sache = 'organisation:zahnarztkraemer'
    stand = client.get('/api/v1/akten/art', params={'sache': sache}).json()
    assert (stand['art'], stand['bestaetigt'], stand['vorschlag']['art']) == (None, False, 'gesundheit')
    assert stand['vorschlag']['begruendung'].startswith('Absender „Zahnarztpraxis Dr. Krämer“')
    assert app.state.episodes._conn.execute('SELECT COUNT(*) FROM akten_arten').fetchone()[0] == 0
    fest = client.put('/api/v1/akten/art', json={'sache': sache, 'art': 'gesundheit'}).json()
    assert (fest['art'], fest['bestaetigt'], fest['neuer_vorschlag']) == ('gesundheit', True, False)
    assert client.get('/api/v1/akten/akte', params={'sache': sache}).json()['akten_art'] == 'gesundheit'
    assert client.put('/api/v1/akten/art', json={'sache': 'person:a:x@y.example', 'art': 'familie'}).status_code == 422
    assert client.put('/api/v1/akten/art', json={'sache': sache, 'art': 'beruf'}).status_code == 422
    assert client.delete('/api/v1/akten/art', params={'sache': sache}).json()['bestaetigt'] is False


def test_fristen_werden_aufgabenvorschlaege_mit_beleg_nie_aufgaben(api):
    app, client = api
    quelle, satz = _rechnung(app)
    aufgaben_vorher = len(app.state.tasks.all_tasks())
    lauf = client.post('/api/v1/akten/arten/fristen').json()
    assert (lauf['laeuft'], lauf['vorgeschlagen']) == (False, 1)
    [vorschlag] = [v for v in client.get('/api/v1/task-candidates').json()
                   if v['proposed_by'].startswith(akten_arten.VORGESCHLAGEN_VON)]
    assert vorschlag['statement'] == f'Zahlung bis {kuenftig(20):%d.%m.%Y}: 86,40 € (Zahnarztpraxis Dr. Krämer)'
    assert vorschlag['evidence'][0] == {'episode_id': quelle.id, 'quote': satz, 'digest': quelle.digest}
    assert vorschlag['valid_until'][:10] == kuenftig(20).isoformat()
    assert zahlen_belegt(vorschlag['statement'], quelle.body) == []
    assert len(app.state.tasks.all_tasks()) == aufgaben_vorher   # Vorschlag, keine Aufgabe
    # Ein zweiter Lauf legt nichts doppelt an; ein abgelehnter Vorschlag kommt nicht wieder.
    assert client.post('/api/v1/akten/arten/fristen').json()['vorgeschlagen'] == 0
    client.post(f'/api/v1/task-candidates/{vorschlag["id"]}/reject')
    assert client.post('/api/v1/akten/arten/fristen').json()['vorgeschlagen'] == 0
    assert not [v for v in client.get('/api/v1/task-candidates').json()
                if v['proposed_by'].startswith(akten_arten.VORGESCHLAGEN_VON)]


def test_annahme_macht_eine_aufgabe_mit_faelligkeit(api):
    app, client = api
    _rechnung(app, 12)
    client.post('/api/v1/akten/arten/fristen')
    [vorschlag] = client.get('/api/v1/task-candidates').json()
    aufgabe = client.post(f'/api/v1/task-candidates/{vorschlag["id"]}/accept',
                          json={'title': vorschlag['statement'], 'due': vorschlag['valid_until']}).json()
    assert aufgabe['title'] == vorschlag['statement'] and aufgabe['due'][:10] == kuenftig(12).isoformat()


def test_keine_davon_stellt_die_fristensuche_fuer_die_akte_ab(api):
    app, client = api
    _rechnung(app)
    client.put('/api/v1/akten/art', json={'sache': 'organisation:zahnarztkraemer', 'art': 'keine'})
    assert client.post('/api/v1/akten/arten/fristen').json()['vorgeschlagen'] == 0


def test_berufliche_rechnung_wird_keine_private_frist(api):
    app, client = api
    _rechnung(app, von='buchhaltung@klinikum-albanus.example', titel='Rechnung Workshop', name='Buchhaltung Albanus')
    assert client.post('/api/v1/akten/arten/fristen').json()['vorgeschlagen'] == 0


def test_private_akten_werden_auch_unter_vielen_beruflichen_gefunden(api):
    """Mit vielen Organisationen zählt nicht die Reihenfolge: Die Fristensuche liest die Akten mit privatem Absender,
    nicht die jüngsten paar hundert (mit 10.000 Quellen fiel sonst die Akte der Stadtwerke heraus)."""
    app, _ = api
    quelle, _ = _rechnung(app)
    for nummer in range(4):
        mail(app, f'kontakt@beratung-nord{nummer}.example', ICH, 'Anbei das Protokoll.', tage=1,
             name=f'Beratung Nord {nummer}', titel='Protokoll')
    nachfuehren(app, warten=True)
    bezuege, _ = bausteine(app)
    assert akten_arten.private_kandidaten(bezuege) == ['organisation:zahnarztkraemer']
    lauf = akten_arten.fristen_vorlegen(bezuege, app.state.proposals, max_akten=2)
    assert (lauf.akten, lauf.vorgeschlagen) == (1, 1)
