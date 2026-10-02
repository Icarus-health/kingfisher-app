"""Sammelbestätigung der Kreise (M4): viele Kollegen mit einem Klick, nie der innere Kreis, rückgängig machbar.

Zusicherungen (jede mit Sabotageprobe, docs/49-kreis-und-privat.md):

1. Ein Klick bestätigt genau die offenen Vorschläge „Kollegen“, sonst nichts; der innere Kreis bleibt offen.
2. Für den inneren Kreis (und Kontakte) gibt es keine Sammelbestätigung.
3. Stimmt die Zahl aus der Rückfrage nicht mehr, wird nichts gespeichert.
4. „Liste zurücknehmen“ lässt genau diese Personen wieder offen; wer seitdem einzeln geändert wurde, bleibt.
"""
from __future__ import annotations

from icarus_memory.akten_routes import nachfuehren
from icarus_memory.kreis import alle_bestaetigten
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_kreis import ICH, MAMA, api, familie, mail, termin  # noqa: F401 - Fixtures

KOLLEGEN = [f'person{n}@klinik-sued.example' for n in range(1, 4)]


def kollegen(app):
    for nummer, adresse in enumerate(KOLLEGEN, 1):
        name = f'Kollegin Nummer{nummer}'
        for tage in (50, 20):
            mail(app, adresse, ICH, 'Sehr geehrte Frau Hartmann, anbei die Unterlagen. Mit freundlichen Grüßen',
                 tage=tage + nummer, name=name, titel='Unterlagen')
            mail(app, ICH, adresse, 'Vielen Dank. Mit freundlichen Grüßen', tage=tage + nummer - 1, name=name,
                 titel='Re: Unterlagen')
        termin(app, f'Projekttreffen {nummer}', adresse, tage=5 + nummer)
    nachfuehren(app, warten=True)


def test_ein_klick_bestaetigt_alle_offenen_kollegen_und_nie_den_inneren_kreis(api):
    app, client = api
    familie(app)
    kollegen(app)
    uebersicht = client.get('/api/v1/kreis/uebersicht').json()
    assert uebersicht['offen_je_kreis'] == {'innerer_kreis': 1, 'kollegen': 3}
    antwort = client.post('/api/v1/kreis/sammel', json={'kreis': 'kollegen', 'anzahl': 3})
    assert antwort.status_code == 200, antwort.text
    assert antwort.json()['satz'] == '3 Personen als Kollegen festgelegt.'
    fest = alle_bestaetigten(app.state.episodes)
    assert fest == {f'person:a:{a}': 'kollegen' for a in KOLLEGEN}
    nachher = client.get('/api/v1/kreis/uebersicht').json()
    assert nachher['offen_je_kreis'] == {'innerer_kreis': 1, 'kollegen': 0}
    assert nachher['letzte_sammlung']['anzahl'] == 3


def test_kein_sammeln_fuer_den_inneren_kreis(api):
    app, client = api
    familie(app)
    kollegen(app)
    for kreis in ('innerer_kreis', 'kontakte'):
        antwort = client.post('/api/v1/kreis/sammel', json={'kreis': kreis, 'anzahl': 1})
        assert antwort.status_code == 422 and 'je Person' in antwort.json()['detail']
    assert alle_bestaetigten(app.state.episodes) == {}


def test_veraltete_zahl_speichert_nichts(api):
    app, client = api
    kollegen(app)
    antwort = client.post('/api/v1/kreis/sammel', json={'kreis': 'kollegen', 'anzahl': 2})
    assert antwort.status_code == 409 and 'Inzwischen sind es 3 Vorschläge' in antwort.json()['detail']
    assert alle_bestaetigten(app.state.episodes) == {}


def test_liste_zuruecknehmen_laesst_genau_diese_wieder_offen(api):
    app, client = api
    kollegen(app)
    sammlung = client.post('/api/v1/kreis/sammel', json={'kreis': 'kollegen', 'anzahl': 3}).json()['sammlung']
    # Eine Person ändert der Mensch danach einzeln: Sie bleibt bei seiner Wahl.
    assert client.put('/api/v1/kreis', json={'sache': f'person:a:{KOLLEGEN[0]}', 'kreis': 'kontakte'}).status_code == 200
    antwort = client.delete('/api/v1/kreis/sammel', params={'sammlung': sammlung})
    assert antwort.status_code == 200 and antwort.json()['satz'] == 'Zurückgenommen: 2 Personen sind wieder offen.'
    assert alle_bestaetigten(app.state.episodes) == {f'person:a:{KOLLEGEN[0]}': 'kontakte'}
    assert client.get('/api/v1/kreis/uebersicht').json()['letzte_sammlung'] is None
    assert client.delete('/api/v1/kreis/sammel', params={'sammlung': sammlung}).status_code == 404
