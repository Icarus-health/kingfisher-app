"""Der Grund einer gescheiterten Mail: Kürzel, Satz für alle, technische Angabe ohne Text vom Server (Fremdprobe 3, Befund 2)."""
import imaplib
import socket
import sqlite3

import pytest

from icarus_memory.connectors.mail import MailboxGenerationChanged, MailError
from icarus_memory.mail_intake_grund import SATZ, einordnen, haeufigster


def mit_ursache(meldung, ursache):
    try:
        raise MailError(meldung) from ursache
    except MailError as fehler:
        return fehler


@pytest.mark.parametrize(('fehler', 'grund'), [
    (MailError('Das Postfach liefert keine stabile Nachrichtenkennung.'), 'kennung'),
    (MailboxGenerationChanged('Die Nachrichtenkennung ist veraltet. Bitte den Posteingang neu laden.'), 'kennung'),
    (MailError('Nachricht 7.3 nicht gefunden.'), 'nicht_gefunden'),
    (MailError('Nachricht 7.3 nicht lesbar.'), 'unlesbar'),
    (mit_ursache('IMAP-Zugriff fehlgeschlagen: Betreff Geheim', socket.timeout('timed out')), 'postfach_schweigt'),
    (mit_ursache('IMAP-Zugriff fehlgeschlagen: Betreff Geheim', imaplib.IMAP4.abort('Betreff Geheim')), 'postfach_schweigt'),
    (mit_ursache('IMAP-Zugriff fehlgeschlagen: Betreff Geheim', imaplib.IMAP4.error('Betreff Geheim')), 'abgelehnt'),
    (RuntimeError('Betreff Geheim'), 'unbekannt'),
])
def test_grund_und_technik_ohne_fremden_text(fehler, grund):
    kuerzel, technik = einordnen(fehler)
    assert kuerzel == grund and kuerzel in SATZ
    assert 'Geheim' not in technik
    assert type(fehler).__name__ in technik


def test_beim_speichern_ist_es_das_gedaechtnis():
    assert einordnen(sqlite3.OperationalError('database is locked'), beim_speichern=True)[0] == 'speichern'
    assert einordnen(RuntimeError('x'), beim_speichern=True)[0] == 'unbekannt'


def test_haeufigster_grund():
    assert haeufigster({}) is None
    assert haeufigster({'unlesbar': 1, 'kennung': 4}) == 'kennung'
    assert haeufigster({'unlesbar': 2, 'postfach_schweigt': 2}) == 'postfach_schweigt'


def test_jeder_satz_ist_ein_satz_ohne_fachwort():
    for satz in SATZ.values():
        assert satz.endswith('.') and satz[0].isupper()
        for wort in ('IMAP', 'UID', 'Exception', 'Error'):
            assert wort not in satz
