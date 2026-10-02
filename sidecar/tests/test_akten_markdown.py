"""Akten als Markdown-Ordner: Struktur, Determinismus, Atomarität, sichere Namen, Frontmatter, nichts fließt zurück."""
from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from icarus_memory import akten_markdown as am
from icarus_memory import akten_routes, atomic
from icarus_memory.episodes import EpisodeKind
from icarus_memory.lage_routes import lagen_von
from icarus_memory.model import Provenance, SourceType
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_akten_routes import BITTE, ERLEDIGT, abgleichen, api  # noqa: F401 - Fixture
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_mappe import _projekt, _quelle

STAND = date(2026, 9, 30)
JETZT = datetime(2026, 9, 30, 9, 0, tzinfo=timezone.utc)
GEHEIM = 'Die Kontonummer steht im Anhang und bleibt unter uns.'


def beschaffen(app, *, quellen: bool = False, lage=None):
    """Alle Dateien des Exports für den Bestand der App, mit festem Stichtag."""
    bezuege, akten = akten_routes.bausteine(app)
    liste, letzte, _ = am.sammeln(akten, bezuege, lage, jetzt=JETZT)
    info, text = am.quellen_lieferant(app.state.episodes)
    return am.bauen(liste, stand=STAND, version='9.9.9', info=info, text=text if quellen else None, letzte=letzte)


def bestand(app, client):
    """Zwei Quellen zu einem Projekt: eine Bitte und die Erledigung, dazu ein Rest, der nie in eine Akte gehört."""
    projekt = _projekt(app, 'Mainz')
    bitte = _quelle(app, 'Druckdaten', [(BITTE, 'request')], project=projekt.id, tage=3)
    antwort = _quelle(app, 'Antwort', [(ERLEDIGT, 'status')], 'Ben <ben@druck.example>', projekt.id, tage=1)
    # Eine Quelle mit Text, der in keinem Abschnitt steht: er darf nur mit „Quellen mitschreiben“ erscheinen.
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Nebensache', 'Kurze Bitte zur Sache. ' + GEHEIM,
        Provenance(SourceType.EMAIL, source_ref='work:<nebensache@example.invalid>'),
        participants=['Anna Keller <anna@agentur.example>'], project_id=projekt.id,
        occurred_at=datetime.now(timezone.utc) - timedelta(days=2))
    store = WorkingMemoryStore(app.state.episodes)
    offen = store.pending(episode_ids=[episode.id])[0]
    assert store.commit(offen, [{'start': 0, 'end': len('Kurze Bitte zur Sache.'), 'kind': 'request'}], model='local-test')
    abgleichen(client)
    return projekt, bitte, antwort, episode


def frontmatter_lesen(text: str) -> dict:
    """Ein Frontmatter ohne YAML-Bibliothek: Werte sind JSON oder ein Datum."""
    assert text.startswith('---\n'), text[:40]
    kopf = text.split('\n---\n', 1)[0].splitlines()[1:]
    werte = {}
    for zeile in kopf:
        schluessel, wert = zeile.split(': ', 1)
        werte[schluessel] = wert if re.fullmatch(r'\d{4}-\d{2}-\d{2}', wert) else json.loads(wert)
    return werte


# -- Struktur --

def test_der_ordner_hat_katalog_akten_und_hinweis_und_ohne_schalter_keine_quellen(api):
    app, client = api
    bestand(app, client)
    dateien = beschaffen(app)
    assert {'index.md', '_README.md', am.MARKE, 'Personen/Anna Keller.md', 'Personen/Ben.md',
            'Organisationen/Agentur.md', 'Organisationen/Druck.md', 'Projekte/Mainz.md'} == set(dateien)
    assert not any(p.startswith('Quellen/') for p in dateien)
    index = dateien['index.md']
    assert index.index('## Personen') < index.index('## Organisationen') < index.index('## Projekte')
    assert '30.09.2026' in index and '[[Personen/Anna Keller|Anna Keller]]' in index
    assert '[Anna Keller](Personen/Anna%20Keller.md)' in index
    readme = dateien['_README.md']
    for satz in ('von **Kingfisher** erzeugt', '**überschrieben**', '**fließen nicht zurück**', '**Klartext**'):
        assert satz in readme


def test_akte_zeigt_lage_verlauf_offenes_fristen_und_beziehungen_mit_beiden_linkarten(api):
    app, client = api
    bestand(app, client)
    akte = beschaffen(app)['Projekte/Mainz.md']
    for abschnitt in ('## Lage', '## Stand', '## Offene Punkte', '### Vermutlich erledigt', '## Fristen', '### Kommend',
                      '## Verlauf', '## Beziehungen'):
        assert abschnitt in akte, abschnitt
    # Beziehungen: Wiki-Link (Obsidian) und gewöhnlicher Link, mit Leerzeichen kodiert und relativ zur Datei.
    assert '[[Personen/Anna Keller|Anna Keller]] ([Anna Keller](../Personen/Anna%20Keller.md))' in akte
    assert '[zum Katalog](../index.md)' in akte
    assert 'Vermutlich offen' in akte                  # nie „offen“ als Tatsache


def test_frontmatter_traegt_art_sache_stand_und_version(api):
    app, client = api
    projekt, *_ = bestand(app, client)
    dateien = beschaffen(app)
    kopf = frontmatter_lesen(dateien['Projekte/Mainz.md'])
    assert kopf['art'] == 'projekt' and kopf['sache_id'] == f'projekt:{projekt.id}'
    assert kopf['stand'] == '2026-09-30' and kopf['kingfisher_version'] == '9.9.9' and kopf['quellen'] == 3
    person = frontmatter_lesen(dateien['Personen/Anna Keller.md'])
    assert person['art'] == 'person' and person['sache_id'] == 'person:a:anna@agentur.example'
    assert frontmatter_lesen(dateien['index.md'])['art'] == 'katalog'


def test_jeder_zitierte_satz_traegt_einen_belegverweis(api):
    app, client = api
    bestand(app, client)
    dateien = beschaffen(app, quellen=True)
    geprueft = 0
    for pfad, text in dateien.items():
        if not pfad.startswith(('Personen/', 'Organisationen/', 'Projekte/')):
            continue
        zeilen = text.splitlines()
        for i, zeile in enumerate(zeilen):
            if re.match(r'\s*- .*„.+“', zeile) and 'Quelle:' not in zeile and 'danach' not in zeile and 'vorher' not in zeile:
                naechste = zeilen[i + 1] if i + 1 < len(zeilen) else ''
                assert 'kingfisher://quelle/' in zeile or ('Quelle:' in naechste and 'kingfisher://quelle/' in naechste), \
                    f'{pfad}: {zeile}'
                geprueft += 1
    assert geprueft >= 8


def test_die_lage_zeigt_nur_geprueftes_mit_belegnummer_titel_und_datum(api):
    app, client = api
    _, bitte, *_ = bestand(app, client)
    lage = {'saetze': [{'text': 'Die Druckdaten sind angefragt.',
                        'belege': [{'nummer': 1, 'episode_id': bitte.id, 'titel': 'Druckdaten'}]}],
            'erstellt_am': '2026-09-29T08:00:00+00:00', 'veraltet': True, 'stand_vom': '2026-09-29T08:00:00+00:00'}
    bezuege, akten = akten_routes.bausteine(app)
    liste, letzte, _ = am.sammeln(akten, bezuege, None, jetzt=JETZT)
    liste = [am.AkteIn(e.sache, e.art, e.name, e.akte, lage if e.sache.startswith('projekt:') else None) for e in liste]
    info, _ = am.quellen_lieferant(app.state.episodes)
    akte = am.bauen(liste, stand=STAND, version='9.9.9', info=info)['Projekte/Mainz.md']
    assert 'Nur geprüfte Sätze' in akte and 'Stand der Lage: 29.09.2026' in akte and 'wird aktualisiert' in akte
    # Die Bitte liegt drei Tage zurück (Fixture `bestand`); das Datum darf nicht fest stehen, sonst kippt der Test täglich.
    vor_drei_tagen = (datetime.now(timezone.utc) - timedelta(days=3)).strftime('%d.%m.%Y')
    assert f'- Die Druckdaten sind angefragt.\n  - [1] Quelle: Druckdaten, {vor_drei_tagen} · [kingfisher://quelle/{bitte.id}]' in akte


# -- Quellen mitschreiben --

def test_quellen_nur_mit_schalter_und_dann_mit_beiden_pfaden_im_verweis(api):
    app, client = api
    _, bitte, _, nebensache = bestand(app, client)
    aus = beschaffen(app)
    assert GEHEIM not in ''.join(aus.values())                  # ohne Schalter kein Rohtext irgendwo
    assert 'Quellen/' not in ''.join(aus.values())              # und keine Verweise auf Dateien, die es nicht gibt
    an = beschaffen(app, quellen=True)
    quelle = an[f'Quellen/{nebensache.id}.md']
    assert GEHEIM in quelle
    assert frontmatter_lesen(quelle)['quelle_id'] == nebensache.id and frontmatter_lesen(quelle)['art'] == 'quelle'
    assert 'Genannt in:' in quelle and '[[Projekte/Mainz|Mainz]]' in quelle
    akte = an['Projekte/Mainz.md']
    assert f'[[Quellen/{bitte.id}|Druckdaten]] ([Quellen/{bitte.id}.md](../Quellen/{bitte.id}.md))' in akte
    assert f'kingfisher://quelle/{bitte.id}' in akte


def test_rohtext_mit_codezaeunen_bricht_die_datei_nicht(api):
    app, client = api
    _, _, _, nebensache = bestand(app, client)
    roh = lambda _id: 'Vorher\n```\nCode\n```\nNachher ````'  # noqa: E731
    bezuege, akten = akten_routes.bausteine(app)
    liste, letzte, _ = am.sammeln(akten, bezuege, None, jetzt=JETZT)
    info, _ = am.quellen_lieferant(app.state.episodes)
    dateien = am.bauen(liste, stand=STAND, version='9.9.9', info=info, text=roh)
    quelle = dateien[f'Quellen/{nebensache.id}.md']
    assert '`````text\nVorher' in quelle and quelle.rstrip().endswith('`````')


# -- Determinismus --

def test_gleicher_bestand_ergibt_gleiche_dateien_unabhaengig_von_der_reihenfolge(api):
    app, client = api
    bestand(app, client)
    erste = beschaffen(app, quellen=True)
    zweite = beschaffen(app, quellen=True)
    assert erste == zweite and list(erste) == list(zweite)
    bezuege, akten = akten_routes.bausteine(app)
    liste, letzte, _ = am.sammeln(akten, bezuege, None, jetzt=JETZT)
    info, text = am.quellen_lieferant(app.state.episodes)
    umgekehrt = am.bauen(list(reversed(liste)), stand=STAND, version='9.9.9', info=info, text=text, letzte=letzte)
    assert umgekehrt == erste


def test_geschriebene_ordner_sind_byte_gleich(api, tmp_path):
    app, client = api
    bestand(app, client)
    dateien = beschaffen(app, quellen=True)
    am.schreiben(tmp_path / 'eins', dateien)
    am.schreiben(tmp_path / 'zwei', dateien)
    def lesen(wurzel):
        return {str(p.relative_to(wurzel)): p.read_bytes() for p in sorted(wurzel.rglob('*')) if p.is_file()}
    assert lesen(tmp_path / 'eins') == lesen(tmp_path / 'zwei') and len(lesen(tmp_path / 'eins')) == len(dateien)


# -- Atomarität --

def test_schreiben_ersetzt_den_alten_stand_vollstaendig(tmp_path):
    ziel = tmp_path / 'Akten'
    am.schreiben(ziel, {'index.md': 'alt', 'Personen/Alt.md': 'x'})
    am.schreiben(ziel, {'index.md': 'neu', 'Orte/Neu.md': 'y'})
    assert sorted(str(p.relative_to(ziel)) for p in ziel.rglob('*') if p.is_file()) == ['Orte/Neu.md', 'index.md']
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'neu'
    assert [p.name for p in tmp_path.iterdir()] == ['Akten']         # keine Reste daneben


def test_ein_fehler_mitten_im_schreiben_laesst_den_alten_ordner_unversehrt(tmp_path, monkeypatch):
    ziel = tmp_path / 'Akten'
    am.schreiben(ziel, {'index.md': 'alt', 'Personen/A.md': 'a'})
    echte = Path.write_text
    zaehler = {'n': 0}

    def bricht(self, *args, **kwargs):
        zaehler['n'] += 1
        if zaehler['n'] == 2:
            raise OSError('Platte voll')
        return echte(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'write_text', bricht)
    with pytest.raises(OSError):
        am.schreiben(ziel, {'index.md': 'neu', 'Personen/A.md': 'neu', 'Personen/B.md': 'neu'})
    monkeypatch.setattr(Path, 'write_text', echte)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'alt' and (ziel / 'Personen/A.md').read_text(encoding='utf-8') == 'a'
    assert not (ziel / 'Personen/B.md').exists()
    assert [p.name for p in tmp_path.iterdir()] == ['Akten']         # der halbe Nachbarordner ist weg


def test_bricht_das_einsetzen_ab_kommt_die_alte_fassung_zurueck(tmp_path, monkeypatch):
    ziel = tmp_path / 'Akten'
    am.schreiben(ziel, {'index.md': 'alt'})
    neu = tmp_path / 'neu'
    neu.mkdir()
    (neu / 'index.md').write_text('neu', encoding='utf-8')
    echt = os.replace
    aufrufe = []

    def replace(von, nach):
        aufrufe.append((Path(von).name, Path(nach).name))
        if Path(von) == neu:
            raise OSError('gestört')
        return echt(von, nach)

    monkeypatch.setattr(os, 'replace', replace)
    with pytest.raises(OSError):
        atomic.ordner_tauschen(neu, ziel)
    monkeypatch.setattr(os, 'replace', echt)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'alt'


def test_nach_abbruch_zwischen_den_umbenennungen_stellt_der_naechste_lauf_wieder_her(tmp_path):
    ziel = tmp_path / 'Akten'
    alt = tmp_path / '.Akten.alt'
    alt.mkdir()
    (alt / 'index.md').write_text('gerettet', encoding='utf-8')          # Zustand nach einem Absturz: Ziel fehlt
    neu = tmp_path / 'neu'
    neu.mkdir()
    (neu / 'index.md').write_text('neu', encoding='utf-8')
    atomic.ordner_tauschen(neu, ziel)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'neu' and not alt.exists()
    # Fehlt nach einem Absturz auch das Neue, bleibt wenigstens der alte Stand erhalten.
    alt.mkdir()
    (alt / 'index.md').write_text('alt', encoding='utf-8')
    import shutil
    shutil.rmtree(ziel)
    with pytest.raises(FileNotFoundError):
        atomic.ordner_tauschen(tmp_path / 'gibtesnicht', ziel)
    assert (ziel / 'index.md').read_text(encoding='utf-8') == 'alt'


def test_unsichere_pfade_im_export_werden_abgelehnt(tmp_path):
    for schlecht in ('../x.md', '/etc/x.md', 'a/../../x.md', 'a\\b.md', '', 'a//b.md'):
        with pytest.raises(ValueError):
            am.schreiben(tmp_path / 'Akten', {schlecht: 'x'})
    assert not (tmp_path / 'Akten').exists() and not list(tmp_path.iterdir())


def test_reste_eines_abgebrochenen_schreibens_werden_aufgeraeumt(tmp_path):
    ziel = tmp_path / 'Akten'
    (tmp_path / '.Akten.neu-abc').mkdir()
    (tmp_path / 'fremd').mkdir()
    am.aufraeumen(ziel)
    assert [p.name for p in tmp_path.iterdir()] == ['fremd']


# -- Sichere Namen --

@pytest.mark.parametrize('roh,erwartet', [
    ('Anna Keller', 'Anna Keller'),
    ('../../etc/passwd', 'etc passwd'),
    ('Müller/Schmidt: GmbH', 'Müller Schmidt GmbH'),
    ('Projekt #1 [neu] ^x |y', 'Projekt 1 neu x y'),
    ('  ...versteckt.  ', 'versteckt'),
    ('', 'Ohne Name'),
    ('///', 'Ohne Name'),
    ('CON', 'CON_'),
    ('nul', 'nul_'),
    ('Zeile\neins\tzwei', 'Zeile eins zwei'),
    ('Ärger mit Ü', 'Ärger mit Ü'),
])
def test_dateinamen_sind_sicher(roh, erwartet):
    assert am.dateiname(roh) == erwartet


def test_dateinamen_sind_begrenzt_und_schneiden_keine_zeichen_durch():
    name = am.dateiname('ä' * 500)
    assert len(name.encode('utf-8')) <= am.MAX_NAME_BYTES and set(name) == {'ä'}
    name = am.dateiname('Ab ' + 'x' * 500)
    assert len(name) <= am.MAX_NAME_BYTES and not name.endswith(' ')
    # Zusammengesetzte und zerlegte Umlaute ergeben denselben Namen.
    assert am.dateiname('Müller') == am.dateiname('Müller')


def _akte(sache, art, name):
    leer = {'art_text': art, 'quellen': {'gesamt': 1, 'beruecksichtigt': 1, 'begrenzt': False},
            'stand_der_dinge': {'aktuell': None, 'vorher': [], 'vorher_gesamt': 0, 'weitere': [], 'weitere_gesamt': 0},
            'offen': {'eintraege': [], 'gesamt': 0, 'erledigt': {'eintraege': [], 'gesamt': 0}},
            'fristen': {'kommend': [], 'verstrichen': [], 'ersetzt': [], 'gesamt': {}, 'ohne_datum': {'eintraege': [], 'gesamt': 0}},
            'termine': {'kommend': [], 'vergangen': [], 'gesamt': {}}, 'aufgaben': {'eintraege': [], 'gesamt': 0},
            'verlauf': {'eintraege': [], 'gesamt': 0}, 'beteiligte': {'eintraege': [], 'gesamt': 0}}
    return am.AkteIn(sache, art, name, leer)


def test_kollisionen_bekommen_ein_festes_suffix_auch_bei_anderer_schreibweise():
    akten = [_akte('person:a:a@x.example', 'person', 'Anna Keller'), _akte('person:a:b@x.example', 'person', 'anna keller'),
             _akte('person:n:Anna/Keller', 'person', 'Anna/Keller'), _akte('organisation:annakeller', 'organisation', 'Anna Keller')]
    pfade = am.pfade_vergeben(akten)
    assert len(set(p.casefold() for p in pfade.values())) == 4            # alle verschieden, auch ohne Groß-/Kleinschreibung
    assert pfade['organisation:annakeller'] == 'Organisationen/Anna Keller.md'   # anderer Ordner: kein Suffix
    schlichte = [p for p in pfade.values() if p.startswith('Personen/') and '(' not in p]
    assert len(schlichte) == 1
    # Stabil: dieselbe Menge in anderer Reihenfolge ergibt dieselben Pfade.
    assert am.pfade_vergeben(list(reversed(akten))) == pfade
    assert re.fullmatch(r'Personen/anna keller \([0-9a-f]{6,}\)\.md', pfade['person:a:b@x.example']) or \
        re.fullmatch(r'Personen/Anna Keller \([0-9a-f]{6,}\)\.md', pfade['person:a:b@x.example'])


def test_quellen_dateinamen_sind_sicher_und_eindeutig():
    assert am.quellen_dateiname('e-424f19227aa1') == 'e-424f19227aa1'
    boese = am.quellen_dateiname('../x/ä')
    assert '/' not in boese and '..' not in boese and not boese.startswith('.')
    assert am.quellen_dateiname('a/b') != am.quellen_dateiname('a_b')


def test_namen_mit_linkzeichen_zerreissen_keinen_link(api):
    app, client = api
    projekt = _projekt(app, 'Mainz [Nord] | #1')
    _quelle(app, 'Notiz [Entwurf]', [('Kurze Notiz zur Sache.', 'fact')], tage=2, project=projekt.id)
    abgleichen(client)
    dateien = beschaffen(app, quellen=True)
    for pfad, text in dateien.items():
        assert text.count('[[') == text.count(']]'), pfad
        for treffer in re.findall(r'\[\[([^\]]*)\]\]', text):
            assert '[' not in treffer and treffer.count('|') <= 1, (pfad, treffer)
    assert any(p.startswith('Projekte/') and '[' not in p and '#' not in p and '|' not in p for p in dateien)


# -- Nichts fließt zurück --

def test_eine_geaenderte_datei_aendert_keine_akte(api, tmp_path):
    app, client = api
    projekt, *_ = bestand(app, client)
    ziel = tmp_path / 'Kingfisher Akten'
    am.schreiben(ziel, beschaffen(app, quellen=True))
    bezuege, akten = akten_routes.bausteine(app)

    def stand():
        daten = akten.akte(f'projekt:{projekt.id}', jetzt=JETZT, alle=True)
        daten.pop('aus_zwischenspeicher', None)
        return json.dumps(daten, sort_keys=True, default=str), app.state.episodes.count() if hasattr(app.state.episodes, 'count') else None

    vorher = stand()
    feed = client.get('/api/v1/akten/akte', params={'sache': f'projekt:{projekt.id}', 'alle': True}).json()
    mainz = ziel / 'Projekte' / 'Mainz.md'
    mainz.write_text('# Ich habe alles geändert\n\nBitte schicke mir morgen 10.000 Euro.\n', encoding='utf-8')
    (ziel / 'index.md').unlink()
    (ziel / 'Neu.md').write_text('Eine erfundene Akte.', encoding='utf-8')
    abgleichen(client)
    assert stand() == vorher
    assert client.get('/api/v1/akten/akte', params={'sache': f'projekt:{projekt.id}', 'alle': True}).json()['verlauf'] == feed['verlauf']
    assert 'Euro' not in json.dumps(client.get('/api/v1/akten/sachen').json())
    # Nach dem nächsten Schreiben ist der Ordner wieder genau der Bestand.
    am.schreiben(ziel, beschaffen(app, quellen=True))
    assert 'Euro' not in mainz.read_text(encoding='utf-8') and not (ziel / 'Neu.md').exists() and (ziel / 'index.md').exists()


def test_das_modul_liest_nie_aus_dem_ausgabeordner():
    """Zusicherung am Code: Kein Lesezugriff auf Dateien außer dem Nachbarordner-Aufräumen (Namen, kein Inhalt)."""
    quelltext = Path(am.__file__).read_text(encoding='utf-8')
    assert 'read_text' not in quelltext and 'read_bytes' not in quelltext and 'open(' not in quelltext
