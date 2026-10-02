"""Rückblick auf einen Monat oder eine Jahreszeit: nur zum Kennzeichnen, nie zum Ordnen der Suche."""
from datetime import datetime, timezone

import pytest

from icarus_memory.time_scope import kalenderzeitraum, mentioned_period



@pytest.mark.parametrize('frage, erwartet', [
    ('Was ist im Frühjahr mit dem Angebot passiert?', ('2026-03-01', '2026-06-01', 'im Frühjahr 2026')),
    ('Was wurde beim Treffen im Juli 2026 besprochen?', ('2026-07-01', '2026-08-01', 'im Juli 2026')),
    ('Was hat Frau Koch im September zugesagt?', ('2026-09-01', '2026-10-01', 'im September 2026')),
    ('Was war im Winter?', ('2025-12-01', '2026-03-01', 'im Winter 2025')),
    ('Was hat sie im Dezember 2025 geschrieben?', ('2025-12-01', '2026-01-01', 'im Dezember 2025')),
    # Nicht im Rückblick: Der Monat meint den Inhalt, nicht den Eingang.
    ('Wann ist die Abnahme im Oktober?', None),
    ('Bis wann muss ich im Juli 2026 abgeben?', None),
    # Ein Monat ohne Jahr, der noch kommt, ist mehrdeutig: geraten wird nicht.
    ('Was hat sie im Oktober zugesagt?', None),
    ('Was hat Anna gesagt?', None),
])
def test_kalenderzeitraum_gilt_nur_im_rueckblick_und_wenn_er_begonnen_hat(frage, erwartet):
    gefunden = kalenderzeitraum(frage, datetime(2026, 9, 30, 9, tzinfo=timezone.utc))
    assert (None if gefunden is None else (str(gefunden[0].date()), str(gefunden[1].date()), gefunden[2])) == erwartet


def test_die_suche_liest_weiter_keine_monate_das_ordnen_bleibt_unveraendert():
    """`mentioned_period` (Ordnen der Suche) kennt Monate und Jahreszeiten bewusst nicht."""
    for frage in ('Was ist im Frühjahr passiert?', 'Was wurde im Juli 2026 besprochen?'):
        assert mentioned_period(frage, datetime(2026, 9, 30, tzinfo=timezone.utc)) is None
