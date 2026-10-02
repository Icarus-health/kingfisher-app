"""`Intake.status` liest in kleinen Fenstern und hält die Episodensperre nie über den ganzen Bestand."""
import threading

from icarus_memory import mail_intake
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake

from .test_mail_intake import Reader


def gefuellt(tmp_path, anzahl=9):
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    intake.start('a', ['INBOX'])
    reader = Reader()
    reader.count = anzahl
    for _ in range(4):
        intake.step('a', reader, batch=5)
    return ep, intake


def test_fensterweise_gelesen_ergibt_dieselben_zaehler_wie_in_einem_zug(tmp_path, monkeypatch):
    ep, intake = gefuellt(tmp_path)
    monkeypatch.setattr(mail_intake, 'STATUS_WINDOW', 10_000)
    ganz = intake.status('a')
    monkeypatch.setattr(mail_intake, 'STATUS_WINDOW', 2)
    assert intake.status('a') == ganz
    assert ganz['folders'][0]['captured'] == 9
    ep.close()


def test_sperre_ist_zwischen_den_fenstern_frei(tmp_path, monkeypatch):
    ep, intake = gefuellt(tmp_path)
    monkeypatch.setattr(mail_intake, 'STATUS_WINDOW', 2)
    original = intake._window_counts
    fenster, frei = [], []

    def pruefen(*args):
        # Läuft außerhalb der Sperre: Ein anderer Thread (Schreiber) muss sie jetzt bekommen.
        ergebnis = []
        thread = threading.Thread(target=lambda: ergebnis.append(ep._lock.acquire(timeout=2)) or ep._lock.release())
        thread.start()
        thread.join()
        frei.append(ergebnis == [True])
        fenster.append(args[2:])
        return original(*args)

    monkeypatch.setattr(intake, '_window_counts', pruefen)
    intake.status('a')
    assert len(fenster) == 5 and all(frei)   # 9 Einträge in Fenstern zu 2
    ep.close()
