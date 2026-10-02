"""Die Aufnahme spielt über die Produktpfade ein und findet die Episoden wieder."""
from __future__ import annotations

from datetime import datetime

from messlatte.daten import Mail, Termin


def test_jede_quelle_hat_eine_episode_auch_die_termine(bestand):
    erwartet = {q.id for q in bestand.welt.quellen}
    assert set(bestand.aufnahme.episoden) == erwartet
    assert bestand.aufnahme.nicht_angekommen == {}
    assert (bestand.aufnahme.aufgenommen, bestand.aufnahme.fehlgeschlagen) == (15, 0)


def test_mails_kommen_ueber_den_mailweg_mit_kopfzeilen_an(bestand):
    mail = next(q for q in bestand.welt.quellen if q.id == 'mainz-001')
    episode = bestand.instanz.episodes.get(bestand.aufnahme.episoden['mainz-001'])
    assert episode.title == mail.betreff
    assert episode.body.strip() == mail.text.strip()
    assert episode.occurred_at == mail.zeit
    # Absender zuerst, dann die Empfänger; die eigene Adresse des Nutzers ist „ich“ und
    # steht als Empfänger nur in contacts, nicht im durchsuchbaren participants.
    assert episode.participants == ['Sabine Becker <s.becker@klinikum-albanus.example>']
    assert [(c['rolle'], c['adresse'], c['ich']) for c in episode.contacts] == [
        ('von', 's.becker@klinikum-albanus.example', False), ('an', 'lea@hartmann-beratung.example', True)]
    assert episode.provenance.source_type.value == 'email'


def test_eigene_mail_kommt_aus_dem_ordner_sent(bestand):
    sent = [q.id for q in bestand.welt.quellen if isinstance(q, Mail) and q.ordner == 'Sent']
    assert sent and all(q in bestand.aufnahme.episoden for q in sent)
    episode = bestand.instanz.episodes.get(bestand.aufnahme.episoden[sent[0]])
    assert 'lea@hartmann-beratung.example' in episode.participants[0]


def test_transkript_und_notiz_behalten_zeit_teilnehmer_und_text(bestand):
    transkript = bestand.instanz.episodes.get(bestand.aufnahme.episoden['mainz-008'])
    assert transkript.title == 'Telefonat mit Frau Becker'
    assert transkript.participants == ['Sabine Becker', 'Lea Hartmann']
    assert transkript.occurred_at == datetime.fromisoformat('2026-09-12T11:30:00+02:00')
    assert 'Anfang November' in transkript.body
    notiz = bestand.instanz.episodes.get(bestand.aufnahme.episoden['rechnung-005'])
    assert notiz.title == 'Drucker Wartung' and 'T-4471' in notiz.body


def test_termine_sind_episoden_der_art_event_und_bleiben_in_der_live_anzeige(bestand):
    assert bestand.aufnahme.termine_im_kalender == 2 and bestand.aufnahme.termine_ausserhalb_fenster == 0
    termin = next(q for q in bestand.welt.quellen if q.id == 'mainz-006')
    episode = bestand.instanz.episodes.get(bestand.aufnahme.episoden['mainz-006'])
    assert episode.kind.value == 'event' and episode.provenance.source_type.value == 'calendar'
    assert episode.title == termin.titel and episode.occurred_at == termin.beginn
    assert termin.titel in episode.body and termin.ort in episode.body
    eintraege = bestand.instanz.agent._calendar_entries()
    kennungen = {e['uid'].split(':')[-1] for e in eintraege or []}
    # Fenster der Live-Anzeige: 30 Tage um den Stichtag; beide Termine liegen darin.
    assert kennungen == {'mainz-006', 'rechnung-006'}


def test_alles_ist_eingeordnet_und_damit_durchsuchbar(bestand):
    assert bestand.aufnahme.einordnung.startswith('15 von 15 eingeordnet')


def test_zaehler_je_art(bestand):
    art = bestand.aufnahme.je_art
    assert art['mail']['aufgenommen'] == 9 and art['transkript']['aufgenommen'] == 2
    assert art['notiz']['aufgenommen'] == 2 and art['termin']['aufgenommen'] == 2 and art['termin']['im_kalender'] == 2
