"""Unterlagen aus synchronisierten Cloud-Ordnern (M4): OneDrive, Google Drive, iCloud Drive als Vorschläge zum Anklicken.

Zusicherungen (jede mit Sabotageprobe, docs/49-kreis-und-privat.md):

1. Vorgeschlagen wird nur, was es auf dem Rechner gibt, mit lesbarem Namen; im Container keiner, dafür ein ehrlicher Satz.
2. Ein vorgeschlagener Cloud-Ordner ist keine Freigabe: gelesen wird erst nach dem Klick.
3. Gelesen werden PDF, Text, Markdown und Word, die Dateien bleiben, wo sie sind; was nur in der Cloud liegt, wird
   nicht heruntergeladen.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

from icarus_memory import ordner_lokal
from tests.test_ordner_lokal import alt, client, zuhause  # noqa: F401 - Fixtures

D = '/api/v1/folder-sync'


def cloud(home: Path) -> dict[str, Path]:
    pfade = {'onedrive': home / 'Library/CloudStorage/OneDrive-Hochschule',
             'google': home / 'Library/CloudStorage/GoogleDrive-lea@beispiel.example/Meine Ablage',
             'icloud': home / 'Library/Mobile Documents/com~apple~CloudDocs'}
    for pfad in pfade.values():
        pfad.mkdir(parents=True)
    (home / 'Library/CloudStorage/Dropbox').mkdir()   # kein unterstützter Dienst: kein Vorschlag
    return pfade


def test_cloud_ordner_mit_lesbarem_namen_nur_wenn_es_sie_gibt(zuhause):
    assert ordner_lokal.cloud_orte(zuhause) == []
    pfade = cloud(zuhause)
    (pfade['onedrive'] / 'Rechnung.pdf').write_bytes(b'%PDF')
    orte = ordner_lokal.bekannte_orte('Dokumente', {'.pdf', '.md'}, home=zuhause, umgebung={}, container=False)
    wolken = [(o['cloud'], o['name'], o['pfad'], o['dateien']) for o in orte if o.get('cloud')]
    assert wolken == [('google_drive', 'Google Drive (lea@beispiel.example)', str(pfade['google']), 0),
                      ('onedrive', 'OneDrive (Hochschule)', str(pfade['onedrive']), 1),
                      ('icloud', 'iCloud Drive', str(pfade['icloud']), 0)]
    assert ordner_lokal.cloud_hinweis(orte, False) == ''


def test_im_container_keine_cloud_ordner_und_ein_ehrlicher_satz(zuhause, tmp_path):
    cloud(zuhause)
    orte = ordner_lokal.bekannte_orte('Dokumente', {'.pdf'}, home=zuhause, umgebung={}, container=True)
    assert orte == []
    assert 'Ein Techniker kann einen dieser Ordner einbinden' in ordner_lokal.cloud_hinweis(orte, True)
    # Eingebunden trägt er denselben lesbaren Namen.
    eingebunden = tmp_path / 'ordner' / 'OneDrive-Firma'
    eingebunden.mkdir(parents=True)
    orte = ordner_lokal.bekannte_orte('Dokumente', {'.pdf'}, home=zuhause,
                                      umgebung={'KINGFISHER_ORDNER': str(eingebunden)}, container=True)
    assert [(o['cloud'], o['name']) for o in orte] == [('onedrive', 'OneDrive (Firma)')]
    assert ordner_lokal.cloud_hinweis(orte, True) == ''


def test_vorschlag_ist_keine_freigabe_erst_der_klick_liest(client, zuhause):
    app, http = client
    pfade = cloud(zuhause)
    (pfade['icloud'] / 'Vertrag.md').write_text('# Mietvertrag\n\nKündigung bis zum 30.11.2026 möglich.\n')
    alt(pfade['icloud'] / 'Vertrag.md')
    orte = http.get(f'{D}/orte').json()
    assert 'iCloud Drive' in [o['name'] for o in orte['orte']] and orte['cloud_hinweis'] == ''
    assert http.get(D).json()['enabled'] is False
    assert not [e for e in app.state.episodes.each_episode() if e.title.startswith('Mietvertrag')]
    antwort = http.post(f'{D}/lokal', json={'pfad': str(pfade['icloud'])})
    assert antwort.status_code == 200 and '1 Datei gelesen' in antwort.json()['satz']
    assert (pfade['icloud'] / 'Vertrag.md').exists()   # die Datei bleibt, wo sie ist


def test_ohne_cloud_ordner_ein_satz(client):
    _, http = client
    assert http.get(f'{D}/orte').json()['cloud_hinweis'] == (
        'Auf diesem Rechner hat Kingfisher keinen Ordner von OneDrive, Google Drive oder iCloud Drive gefunden.')


def test_nur_in_der_cloud_wird_nicht_heruntergeladen(tmp_path, monkeypatch):
    ordner = tmp_path / 'OneDrive-Hochschule'
    ordner.mkdir()
    (ordner / 'lokal.md').write_text('da')
    (ordner / 'wolke.md').write_text('nur ein Platzhalter')
    alt(ordner / 'lokal.md'), alt(ordner / 'wolke.md')
    echt = os.lstat

    class Info:
        def __init__(self, info, flags):
            self._info, self.st_flags = info, flags

        def __getattr__(self, name):
            return getattr(self._info, name)

    def lstat(pfad, *args, **kwargs):
        info = echt(pfad, *args, **kwargs)
        return Info(info, ordner_lokal.NUR_IN_DER_CLOUD if str(pfad).endswith('wolke.md') else 0) \
            if stat.S_ISREG(info.st_mode) else info
    monkeypatch.setattr(ordner_lokal.os, 'lstat', lstat)
    gelesen = ordner_lokal.lesen(ordner, {'.md'})
    assert [d[0] for d in gelesen['dateien']] == ['lokal.md']
    assert gelesen['fehler'] == ['wolke.md: liegt nur in der Cloud; Kingfisher lädt nichts herunter']
