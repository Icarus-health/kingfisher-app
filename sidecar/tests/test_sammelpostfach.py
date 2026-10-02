"""Die Regel „Sammelpostfach“ (info@, noreply@ …) steht nur in `people_quality.py`.

Aufnahme, Kategorien, Personenansicht und Bezüge rufen dieselbe Funktion. Eine
zweite Kopie der Regel würde beim nächsten Anbieter-Sonderfall auseinanderlaufen.
"""
import re
from pathlib import Path

import pytest

from icarus_memory import bezuege, people_quality
from icarus_memory.people_quality import ist_sammelpostfach, lokalteil

PAKET = Path(people_quality.__file__).parent


@pytest.mark.parametrize('adresse, lokal', [
    ('Info+Newsletter@Firma.de', 'info'),
    ('anna.keller@firma.de', 'anna.keller'),
    ('noreply@x.example', 'noreply'),
    ('ohne-at', 'ohne-at'),
])
def test_lokalteil(adresse, lokal):
    assert lokalteil(adresse) == lokal


@pytest.mark.parametrize('adresse, erwartet', [
    ('info@firma.de', True),
    ('INFO+abo@firma.de', True),
    ('no-reply@firma.de', True),
    ('comments-noreply@docs.google.com', True),
    ('anna.keller@firma.de', False),
    ('information@firma.de', False),
])
def test_sammelpostfach_regel(adresse, erwartet):
    assert ist_sammelpostfach(lokalteil(adresse)) is erwartet


def test_bezuege_folgt_der_einen_regel(monkeypatch):
    assert bezuege.maschinell('Info@Firma.de') is True
    assert bezuege.maschinell('anna@firma.de') is False
    # Erweitert man die Regel an der einen Stelle, folgen die Bezüge.
    monkeypatch.setattr(people_quality, 'GENERIC', people_quality.GENERIC | {'rechnung'})
    assert bezuege.maschinell('rechnung@firma.de') is True


def test_keine_zweite_kopie_der_regel():
    funde = []
    muster = re.compile(r'\bin\s+GENERIC\b|AUTOMATED\.search|import[^\n]*\b(?:AUTOMATED|GENERIC)\b')
    for datei in sorted(PAKET.rglob('*.py')):
        if datei.name == 'people_quality.py':
            continue
        text = datei.read_text(encoding='utf-8')
        for treffer in muster.finditer(text):
            funde.append(f'{datei.name}:{text.count(chr(10), 0, treffer.start()) + 1}')
    assert not funde, 'Die Regel steht nur in people_quality.ist_sammelpostfach: ' + ', '.join(funde)
