"""Modellwahl und die IMAP-Attrappe (Rohmail bis Produktparser)."""
from __future__ import annotations

import imaplib
from datetime import datetime, timezone

import pytest

from messlatte.daten import Adresse, Mail
from messlatte.modell import ModellFehler, baue_anbieter, lese_modell
from messlatte.postfach import Postfach, postfach_installieren, quelle_aus_message_id, rohmail


# -- Modellwahl ------------------------------------------------------------------------------


def test_keins_und_vorgabe():
    assert lese_modell('keins').art == 'keins' and lese_modell('').art == 'keins'
    assert baue_anbieter(lese_modell('keins')) is None


def test_ollama_mit_doppelpunkt_im_modellnamen():
    wahl = lese_modell('ollama:qwen2.5:14b')
    assert (wahl.art, wahl.name) == ('ollama', 'qwen2.5:14b') and wahl.bezeichnung == 'ollama:qwen2.5:14b'


def test_kompatibel_zerlegt_url_und_modellnamen():
    wahl = lese_modell('kompatibel:http://127.0.0.1:1234/v1:qwen2.5:14b', {'OPENAI_API_KEY': 'k'})
    assert (wahl.url, wahl.name, wahl.schluessel) == ('http://127.0.0.1:1234/v1', 'qwen2.5:14b', 'k')


def test_kompatibel_ohne_pfad_wird_erklaert():
    with pytest.raises(ModellFehler, match='Pfad in der URL'):
        lese_modell('kompatibel:http://127.0.0.1:1234:qwen')


def test_anthropic_braucht_den_schluessel_aus_der_umgebung():
    with pytest.raises(ModellFehler, match='ANTHROPIC_API_KEY'):
        lese_modell('anthropic:claude-x', {})
    assert lese_modell('anthropic:claude-x', {'ANTHROPIC_API_KEY': 'geheim'}).art == 'anthropic'


def test_bezeichnung_im_bericht_enthaelt_nie_einen_schluessel():
    wahl = lese_modell('anthropic:claude-x', {'ANTHROPIC_API_KEY': 'geheim'})
    assert 'geheim' not in wahl.bezeichnung and 'geheim' not in repr(lese_modell('kompatibel:http://h/v1:m', {'OPENAI_API_KEY': 'geheim'}).bezeichnung)


def test_unbekanntes_modell():
    with pytest.raises(ModellFehler, match='Unbekanntes Modell'):
        lese_modell('zauberei:x')


def test_lokaler_anbieter_bekommt_die_vertrauenswuerdige_lokale_verbindung():
    anbieter = baue_anbieter(lese_modell('ollama:m'))
    assert anbieter.is_local and anbieter._verified_local_transport is True
    fern = baue_anbieter(lese_modell('kompatibel:https://api.example.org/v1:m'))
    assert not fern.is_local and not getattr(fern, '_verified_local_transport', False)


# -- Postfach-Attrappe ---------------------------------------------------------------------------


def mail(**felder):
    grund = dict(id='t-001', zeit=datetime(2026, 5, 4, 8, 30, tzinfo=timezone.utc), szenario='t',
                 von=Adresse('Jürgen Müller', 'j.mueller@firma.example'), an=(Adresse('Lea Hartmann', 'lea@hartmann-beratung.example'),),
                 betreff='Überweisung für Käse & Brot', text='Grüße aus Köln.\n\nBis zum 5. Mai.')
    return Mail(**{**grund, **felder})


def test_rohmail_ueberlebt_den_produktparser_mit_umlauten():
    from icarus_memory.connectors.mail import MailConfig, MailConnector
    postfach = Postfach()
    postfach.ablegen_mail(mail())
    with postfach_installieren(postfach):
        leser = MailConnector(MailConfig(imap_host='h', username='u', password='p'))
        seite = leser.inventory_page('INBOX', 0, None, 10)
        assert seite['uids'] == [1] and seite['uidvalidity'] == '1'
        nachricht = leser.message_in_folder('INBOX', f"{seite['uidvalidity']}.1")
    assert nachricht.subject == 'Überweisung für Käse & Brot'
    assert nachricht.sender == 'Jürgen Müller <j.mueller@firma.example>'
    assert nachricht.body.strip() == 'Grüße aus Köln.\n\nBis zum 5. Mai.'
    assert nachricht.date == datetime(2026, 5, 4, 8, 30, tzinfo=timezone.utc)
    assert quelle_aus_message_id(nachricht.message_id) == 't-001'


def test_mehrere_mails_ueber_eine_sitzung_eine_verbindung():
    from icarus_memory.connectors.mail import MailConfig, MailConnector
    postfach = Postfach()
    for nummer in range(3):
        postfach.ablegen_mail(mail(id=f't-{nummer}'))
    with postfach_installieren(postfach):
        leser = MailConnector(MailConfig(imap_host='h', username='u', password='p'))
        with leser.session():
            betreffs = [leser.message_in_folder('INBOX', f'1.{uid}').subject for uid in (1, 2, 3)]
        assert len(betreffs) == 3 and postfach.abrufe == 3 and postfach.verbindungen == 1
        leser.message_in_folder('INBOX', '1.1')
        assert postfach.verbindungen == 2   # ohne Sitzung wie bisher eine Verbindung je Abruf


def test_antwort_kopf_und_ordner_sent():
    roh = rohmail(mail(antwort_auf='t-000', ordner='Sent')).decode('utf-8')
    assert 'In-Reply-To: <t-000@messlatte.example>' in roh


def test_attrappe_wird_wiederhergestellt():
    import ssl
    original, kontext = imaplib.IMAP4_SSL, ssl.create_default_context
    with postfach_installieren(Postfach()):
        assert imaplib.IMAP4_SSL is not original and ssl.create_default_context is not kontext
    assert imaplib.IMAP4_SSL is original and ssl.create_default_context is kontext


def test_message_id_umkehrung_mit_kontopraefix():
    assert quelle_aus_message_id('messlatte:<mainz-003@messlatte.example>') == 'mainz-003'
    assert quelle_aus_message_id('<irgendwas@echt.example>') is None
