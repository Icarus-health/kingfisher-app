"""Neue Postfachkennung beim Anbieter (UIDVALIDITY): Kein Bestand doppelt im Gedächtnis.

Vergibt der Server seine Nachrichtennummern neu, beginnt die Aufnahme die Bestandsaufnahme von vorn. Früher legte
sie dabei jede schon gespeicherte Mail ein zweites Mal an (neue Kennung, neue Quelle), und eine ausgeschlossene Mail
kam wieder. Hier der echte Weg über die API gegen die IMAP-Attrappe; alle Mails sind synthetisch.
"""
from __future__ import annotations

from tests.test_mailaufnahme_ende_zu_ende import client, einlesen_starten, hintergrund_takte, postfach  # noqa: F401


def _mails(client) -> list[dict]:
    return [e for e in client.get('/episodes', params={'limit': 50}).json() if e['kind'] == 'message']


def test_neue_postfachkennung_legt_keine_zweite_quelle_an(client, postfach):
    konto = einlesen_starten(client, postfach)
    hintergrund_takte(client)
    vorher = sorted(e['id'] for e in _mails(client))
    assert len(vorher) >= 4

    postfach.uidvalidity = 8  # Der Anbieter hat das Postfach neu angelegt; dieselben Mails, neue Nummern.
    hintergrund_takte(client, 4)

    assert sorted(e['id'] for e in _mails(client)) == vorher
    stand = next(a for a in client.get('/api/v1/mail/intake').json()['accounts'] if a['account_id'] == konto)
    ordner = stand['folders'][0]
    assert ordner['inventory_complete'] and ordner['failed'] == 0 and ordner['pending'] == 0
    assert ordner['captured'] == 0 and ordner['duplicates'] == len(vorher)
    assert stand['stand']['zustand'] == 'aktuell', stand['stand']
