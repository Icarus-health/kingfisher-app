"""Die Vorgaben für Nachrichtenquellen (M3): nur Form und https, nichts wird abgerufen.

Die Adressen stammen nicht aus einem Abruf (`welt_vorgaben.ABGERUFEN` ist `None`); der Test sagt deshalb nichts über
ihre Erreichbarkeit, nur darüber, dass keine die Regeln von `welt_feeds` schon in der Form verletzt.
"""
import ipaddress
import re
from datetime import date
from urllib.parse import urlparse

import pytest

from icarus_memory import welt_vorgaben
from icarus_memory.welt_vorgaben import ABGERUFEN, STAND, VORGABEN, mit_zustand
from tests.test_context_identity import core  # noqa: F401 - Fixture
from tests.test_wetter_welt_routes import api, welt  # noqa: F401 - Fixtures


def test_jede_vorgabe_ist_eine_oeffentliche_https_adresse_in_guter_form():
    for v in VORGABEN:
        adresse = urlparse(v['url'])
        assert adresse.scheme == 'https', v
        assert adresse.hostname and '.' in adresse.hostname, v
        with pytest.raises(ValueError):
            ipaddress.ip_address(adresse.hostname)  # kein Zahlenname
        assert adresse.username is None and adresse.password is None and adresse.port is None, v
        assert not adresse.fragment, v
        assert adresse.hostname != 'localhost' and not adresse.hostname.endswith(('.local', '.internal')), v
        assert len(v['url']) <= 2000 and ' ' not in v['url'], v


def test_vorgaben_sind_eindeutig_und_beschriftet():
    assert len({v['url'] for v in VORGABEN}) == len(VORGABEN) and len({v['id'] for v in VORGABEN}) == len(VORGABEN)
    assert len({v['label'] for v in VORGABEN}) == len(VORGABEN)
    for v in VORGABEN:
        assert re.fullmatch(r'[a-z]+', v['id']), v
        assert 1 <= len(v['label']) <= 80 and v['beschreibung'].strip(), v
    assert len(VORGABEN) >= 4
    # Der Feed-Speicher nimmt höchstens zwölf; die Vorgaben dürfen ihn nicht allein füllen.
    from icarus_memory.welt_meldungen import MAX_FEEDS
    assert len(VORGABEN) <= MAX_FEEDS // 2


def test_der_stand_ist_ein_datum_und_der_abruf_ist_ehrlich_nicht_behauptet():
    assert date.fromisoformat(STAND) <= date(2026, 12, 31)
    assert ABGERUFEN is None, 'Erst nach einem echten Abruf darf ein Datum stehen; bis dahin gilt „nicht abgerufen“.'
    assert 'dpa' not in ' '.join(v['url'] for v in VORGABEN).lower()


def test_alle_vorgaben_nennen_ihren_zustand_anhand_der_hinzugefuegten_feeds():
    feeds = [{'id': 'f1', 'url': VORGABEN[1]['url'], 'label': 'x', 'enabled': True},
             {'id': 'f2', 'url': 'https://eigene.example/feed.xml', 'label': 'eigene', 'enabled': True}]
    zustand = mit_zustand(feeds)
    assert [z['id'] for z in zustand] == [v['id'] for v in VORGABEN]
    assert [z['gewaehlt'] for z in zustand] == [i == 1 for i in range(len(VORGABEN))]
    assert zustand[1]['feed_id'] == 'f1' and zustand[0]['feed_id'] is None


def test_ein_klick_fuegt_hinzu_ein_zweiter_entfernt(welt):
    app, client, tmp_path, d, org = welt
    vorgabe = VORGABEN[0]
    vorher = client.get('/api/v1/welt/briefing').json()
    assert vorher['vorschlaege_stand'] == {'stand': STAND, 'abgerufen': ABGERUFEN}
    angelegt = client.post('/api/v1/welt/feeds', json={'url': vorgabe['url'], 'label': vorgabe['label']})
    assert angelegt.status_code == 201
    nachher = next(v for v in angelegt.json()['vorschlaege'] if v['id'] == vorgabe['id'])
    assert nachher['gewaehlt'] is True and nachher['feed_id']
    entfernt = client.delete(f'/api/v1/welt/feeds/{nachher["feed_id"]}')
    assert entfernt.status_code == 200
    danach = next(v for v in entfernt.json()['vorschlaege'] if v['id'] == vorgabe['id'])
    assert danach['gewaehlt'] is False and danach['feed_id'] is None and entfernt.json()['feeds'] == []


def test_das_modul_ruft_nichts_ab():
    quelltext = open(welt_vorgaben.__file__, encoding='utf-8').read()
    assert 'httpx' not in quelltext and 'urlopen' not in quelltext and 'requests' not in quelltext
