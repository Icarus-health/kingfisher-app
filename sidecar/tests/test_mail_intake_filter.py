"""Die Aufnahme übernimmt die Filterregeln, verwirft nichts still und nutzt eine Sitzung je Durchgang."""
from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace

import pytest

from icarus_memory import mail_filter
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake

from .test_mail_intake import Reader


class FilterReader(Reader):
    """UID 2 trägt den Spam-Kopf, UID 3 gehört zu einer Liste, UID 4 kommt von einer gesperrten Adresse."""
    sitzungen = 0
    offen = 0

    def message_in_folder(self, folder, uid):
        nummer = int(uid.split('.')[1])
        nachricht = super().message_in_folder(folder, uid)
        if nummer == 2:
            return replace(nachricht, spam_flag=True)
        if nummer == 3:
            return replace(nachricht, list_mail=True)
        if nummer == 4:
            return replace(nachricht, sender='Werbung <nachricht@werbung.example>')
        return nachricht

    @contextmanager
    def session(self):
        type(self).sitzungen += 1
        type(self).offen += 1
        try:
            yield self
        finally:
            type(self).offen -= 1


def einstellungen(**regeln):
    return SimpleNamespace(mail_filter=dict(regeln))


def aufnehmen(tmp_path, regeln, batch=6):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    reader = FilterReader()
    screen = mail_filter.intake_screen(einstellungen(**regeln))
    for _ in range(3):
        intake.step('a', reader, batch=batch, screen=screen)
    return ep, intake, reader


def test_filter_greift_wird_gezaehlt_und_nichts_wird_aufgenommen(tmp_path):
    ep, intake, _ = aufnehmen(tmp_path, {'blocked': ['@werbung.example']})
    ordner = intake.status('a')['folders'][0]
    assert ordner['filtered'] == 3
    assert ordner['filtered_by'] == {'spam': 1, 'newsletter': 1, 'blocked': 1}
    assert ordner['captured'] == 3 and ordner['pending'] == 0
    assert ordner['total'] == 6            # gefilterte Nachrichten zählen zum Bestand des Ordners
    assert sum(ep.counts().values()) == 3  # und liegen nicht im Gedächtnis
    ep.close()


def test_newsletter_nach_einstellung(tmp_path):
    ep, intake, _ = aufnehmen(tmp_path, {'block_newsletters': False})
    ordner = intake.status('a')['folders'][0]
    assert ordner['filtered_by'] == {'spam': 1}
    assert ordner['captured'] == 5
    ep.close()


def test_ohne_screen_wird_alles_aufgenommen(tmp_path):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    for _ in range(3):
        intake.step('a', FilterReader(), batch=6)
    assert intake.status('a')['folders'][0]['filtered'] == 0
    assert sum(ep.counts().values()) == 6
    ep.close()


def test_erneut_versuchen_prueft_nach_geaenderten_regeln_neu(tmp_path):
    ep, intake, reader = aufnehmen(tmp_path, {'blocked': ['@werbung.example']})
    freier = mail_filter.intake_screen(einstellungen(block_newsletters=False, allowed=['@werbung.example', '@example.org']))
    intake.retry('a')
    for _ in range(3):
        intake.step('a', reader, batch=6, screen=freier)
    ordner = intake.status('a')['folders'][0]
    assert ordner['filtered_by'] == {'spam': 1}  # der Spam-Kopf gilt auch für erlaubte Absender
    assert ordner['captured'] == 5
    ep.close()


def test_modell_wird_in_der_aufnahme_nie_gefragt(tmp_path):
    """`ai_enabled` ohne Anbieter würde in `classify` alles zurückhalten; die Aufnahme lässt Unklares durch."""
    ep, intake, _ = aufnehmen(tmp_path, {'ai_enabled': True})
    assert intake.status('a')['folders'][0]['captured'] == 4  # nur Spam-Kopf und Newsletter fallen heraus
    ep.close()


def test_eine_sitzung_je_durchgang_und_am_ende_geschlossen(tmp_path):
    FilterReader.sitzungen = FilterReader.offen = 0
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    intake.step('a', FilterReader(), batch=6)
    assert (FilterReader.sitzungen, FilterReader.offen) == (1, 0)
    ep.close()


@pytest.mark.parametrize('name', ['[Gmail]/Spam', '[Gmail]/Trash', '[Gmail]/Papierkorb', 'INBOX.Junk', 'Trash', '[Gmail]/Bin'])
def test_papierkorb_und_spam_ordner_werden_nie_aufgenommen(tmp_path, name):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    with pytest.raises(ValueError):
        Intake(ep).start('a', ['INBOX', name])
    ep.close()


def test_hintergrundtakt_holt_25_und_wendet_die_einstellungen_an(tmp_path):
    from icarus_memory import mail_intake
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    reader = FilterReader()
    reader.count = 26
    ids = intake.background_step('a', reader, einstellungen(), permitted=lambda: True,
                                 permission_lock=None, claims=None)
    ordner = intake.status('a')['folders'][0]
    assert mail_intake.BACKGROUND_BATCH == 25
    assert ordner['captured'] + ordner['filtered'] == 25 and len(ids) == ordner['captured']
    # Der Verlauf geht von neu nach alt: UID 26 bis 2 im ersten Takt, darunter 2 und 3.
    assert ordner['filtered_by'] == {'spam': 1, 'newsletter': 1}
    assert ordner['pending'] == 1  # UID 1, die älteste, kommt zuletzt
    ep.close()


def test_normale_ordner_bleiben_erlaubt(tmp_path):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    Intake(ep).start('a', ['[Gmail]/Alle Nachrichten'])
    Intake(ep).start('a', ['INBOX'])
    ep.close()
