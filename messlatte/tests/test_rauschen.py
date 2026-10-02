"""Das Rauschen ist deterministisch, gleichmäßig verteilt, ähnlich im Wortschatz und nie antwortend."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest

from messlatte import rauschen
from messlatte.bewertung import normalisiere
from messlatte.daten import Mail, Notiz, Termin
from messlatte.welt import lade_welt

MINI = Path(__file__).parent / 'mini_welt'


@pytest.fixture(scope='module')
def welt():
    return lade_welt(MINI)


def texte(quelle) -> str:
    return ' '.join(str(getattr(quelle, f, '') or '') for f in ('betreff', 'text', 'titel', 'ort'))


def test_gleicher_seed_gleiche_quellen_anderer_seed_andere(welt):
    a, b, c = rauschen.erzeuge(200, [welt], 7), rauschen.erzeuge(200, [welt], 7), rauschen.erzeuge(200, [welt], 8)
    assert a == b and a != c


def test_anzahl_ids_und_ein_zeitraum_von_drei_jahren(welt):
    quellen = rauschen.erzeuge(300, [welt], 1)
    assert len(quellen) == 300 == len({q.id for q in quellen})
    assert all(q.id.startswith('rauschen-') and q.szenario == 'rauschen' for q in quellen)
    assert all(q.zeit < welt.stichtag for q in quellen)
    frueh, spaet = min(q.zeit for q in quellen), max(q.zeit for q in quellen)
    assert welt.stichtag - frueh > timedelta(days=3 * 365 - 20) and welt.stichtag - spaet < timedelta(days=20)


def test_gleichmaessig_ueber_die_jahre(welt):
    quellen = rauschen.erzeuge(600, [welt], 2)
    je_halbjahr = Counter((welt.stichtag - q.zeit).days // 183 for q in quellen)
    assert len(je_halbjahr) == 6 and min(je_halbjahr.values()) >= 80


def test_mischung_aus_mail_termin_und_notiz_nur_example_domains(welt):
    quellen = rauschen.erzeuge(400, [welt], 3)
    arten = Counter(type(q) for q in quellen)
    assert arten[Mail] > 250 and arten[Termin] > 10 and arten[Notiz] >= 1
    for q in quellen:
        if isinstance(q, Mail):
            assert q.von.adresse.endswith('.example') and all(a.adresse.endswith('.example') for a in q.an)
            if q.ordner == 'Sent':
                assert q.von.adresse in welt.nutzer.adressen


def test_sent_mails_stammen_vom_nutzer_und_nur_die(welt):
    for q in rauschen.erzeuge(400, [welt], 4):
        if isinstance(q, Mail):
            assert (q.ordner == 'Sent') == (q.von.adresse in welt.nutzer.adressen)


def test_nie_ein_pflichtsatz_eine_verbotene_aussage_oder_ein_voller_name(welt):
    verboten = set()
    for frage in welt.fragen:
        verboten |= {normalisiere(a) for g in frage.erwartet.aussagen for a in g if len(a) >= 4}
        verboten |= {normalisiere(v) for v in frage.verboten.aussagen}
    verboten |= {normalisiere(n) for p in welt.personen for n in p.namen}
    assert verboten
    for q in rauschen.erzeuge(1500, [welt], 5):
        text = normalisiere(texte(q) + ' ' + (q.von.name if isinstance(q, Mail) else ''))
        assert not [v for v in verboten if v in text], (q.id, text)


def test_teilt_woerter_mit_den_szenarien(welt):
    quellen = rauschen.erzeuge(800, [welt], 6)
    gesamt = ' '.join(texte(q) for q in quellen)
    assert 'Mainz' in gesamt and 'Sabine' in gesamt and 'Becker' in gesamt


def test_grenzen_des_produkts_werden_eingehalten(welt):
    quellen = rauschen.erzeuge(60000, [welt], 9)
    assert sum(isinstance(q, Termin) for q in quellen) <= rauschen.MAX_TERMINE
    assert sum(isinstance(q, Notiz) for q in quellen) <= rauschen.MAX_NOTIZEN


def test_null_ergibt_nichts(welt):
    assert rauschen.erzeuge(0, [welt]) == ()
