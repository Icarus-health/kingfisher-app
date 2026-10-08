"""`make aktualisieren` (scripts/kingfisher_aktualisieren.py): erst sichern, dann laden, dann umschalten; bei einem
Fehler läuft wieder die Fassung von vorher, und der Satz nennt `make zurueck-vor-update`. Ohne Docker, ohne Netz:
Befehle und Antworten des Sidecars sind Attrappen."""
from __future__ import annotations

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('kingfisher_aktualisieren', WURZEL / 'scripts' / 'kingfisher_aktualisieren.py')
skript = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skript)
_storage_spec = importlib.util.spec_from_file_location(
    'kingfisher_update_storage', WURZEL / 'scripts' / 'kingfisher_update_storage.py'
)
speicher = importlib.util.module_from_spec(_storage_spec)
_storage_spec.loader.exec_module(speicher)

BILD = 'ghcr.io/icarus-health/kingfisher-app:1.2.0'
OLD_ID = 'sha256:' + '1' * 64
PINNED_IMAGE = 'kingfisher:rollback-' + '1' * 16
GUTER_SPEICHER = {'root_available_bytes': 20 * 1024**3, 'root_available_inodes': 100_000,
                  'data_available_bytes': 20 * 1024**3, 'data_available_inodes': 100_000,
                  'backup_bytes': 1024**2, 'backup_files': 5}
MANIFEST = {'fassung': '1.2.0', 'image': BILD, 'datum': '2026-10-02', 'hinweise': [], 'app_mindestens': '1.0.0',
            'dmg': 'https://github.com/Icarus-health/kingfisher-app/releases/download/v1.2.0/Kingfisher.dmg'}


class Rechner:
    """Docker, make und der laufende Sidecar in einem: merkt Befehle, `laeuft` wechselt mit `make start`."""

    def __init__(self, env: Path, *, sichern_ok=True, pull_ok=True, neu_startet=True, alt_startet=True,
                 stop_ok=True, restore_ok=True,
                 neueste=MANIFEST, erreicht=True, laeuft='1.0.0', speicherstaende=None) -> None:
        self.env, self.befehle, self.anfragen = env, [], []
        self.sichern_ok, self.pull_ok, self.neu_startet, self.alt_startet = sichern_ok, pull_ok, neu_startet, alt_startet
        self.stop_ok, self.restore_ok = stop_ok, restore_ok
        self.restored = False
        self.neueste, self.erreicht, self.laeuft = neueste, erreicht, laeuft
        self.bild_beim_start: list[str | None] = []
        self.speicherstaende = list(speicherstaende or [GUTER_SPEICHER, GUTER_SPEICHER])

    def lauf(self, *befehl, timeout=600, ausgabe=False):
        self.befehle.append(befehl)
        code, aus = 0, ''
        if 'exec' in befehl and befehl[-1] == skript.PROBE_SOURCE:
            stand = self.speicherstaende.pop(0) if self.speicherstaende else GUTER_SPEICHER
            if stand is None:
                code, aus = 1, 'Speicherstatus nicht verfügbar'
            elif isinstance(stand, str):
                code, aus = 0, stand
            else:
                code, aus = 0, json.dumps(stand)
        elif 'exec' in befehl:
            code, aus = (0, 'Hinweis\nvor-update-20261002T080000Z\n') if self.sichern_ok else (1, '')
        elif befehl[:2] == ('docker', 'pull'):
            code = 0 if self.pull_ok else 1
        elif 'stop' in befehl:
            code = 0 if self.stop_ok else 1
            self.laeuft = None
        elif 'run' in befehl:
            code = 0 if self.restore_ok else 1
            self.restored = code == 0
        elif 'ps' in befehl:
            aus = 'old-container\n' if self.laeuft else ''
        elif befehl[:2] == ('docker', 'inspect'):
            aus = OLD_ID + '|' + (skript.env_lesen(self.env).get('KINGFISHER_IMAGE') or skript.VORGABE_BILD) + '\n'
        elif befehl[0] == 'make':
            bild = skript.env_lesen(self.env).get('KINGFISHER_IMAGE')
            self.bild_beim_start.append(bild)
            if bild == BILD:
                self.laeuft = '1.2.0' if self.neu_startet else None
            else:
                self.laeuft = '1.0.0' if self.alt_startet else None
        return subprocess.CompletedProcess(befehl, code, stdout=aus, stderr='')

    def anfrage(self, methode, pfad, token):
        self.anfragen.append((methode, pfad, token))
        if self.laeuft is None:
            return None
        if pfad == '/api/v1/recovery/status':
            return {'mode': 'inspection', 'operational': False} if self.restored else None
        if pfad == '/api/v1/fassung/pruefen':
            verfuegbar = bool(self.neueste) and self.neueste['fassung'] != self.laeuft
            return {'fassung': self.laeuft, 'neueste': self.neueste, 'update_verfuegbar': verfuegbar,
                    'erreicht': self.erreicht}
        return {'fassung': self.laeuft}


@pytest.fixture
def env(tmp_path):
    datei = tmp_path / '.kingfisher.env'
    datei.write_text('# Kopf\nICARUS_SIDECAR_TOKEN=abc\nICARUS_SECRETS_PASSPHRASE=geheim\n', encoding='utf-8')
    datei.chmod(0o600)
    return datei


def los(env, rechner, fassung=''):
    gesagt = []
    try:
        ergebnis = skript.aktualisieren(fassung, wurzel=env.parent, lauf=rechner.lauf, anfrage=rechner.anfrage,
                                        sagen=gesagt.append, warten=lambda s: None)
    except skript.Abbruch as fehler:
        return fehler, gesagt
    return ergebnis, gesagt


def test_der_ganze_weg_in_der_richtigen_reihenfolge(env):
    r = Rechner(env)
    ergebnis, gesagt = los(env, r)
    assert ergebnis == '1.2.0'
    arten = [('probe' if 'exec' in b and b[-1] == skript.PROBE_SOURCE else
              'sichern' if 'exec' in b else 'pull' if b[:2] == ('docker', 'pull') else b[0]) for b in r.befehle]
    assert arten == ['docker', 'docker', 'probe', 'docker', 'sichern', 'pull', 'probe', 'make', 'docker', 'docker']
    sichern = next(b for b in r.befehle if 'exec' in b and b[-1] == skript.SICHERN)
    assert sichern[:4] == ('docker', 'compose', '-p', 'kingfisher') and 'UPDATE_SET_PREFIX' in sichern[-1]
    probes = [b for b in r.befehle if 'exec' in b and b[-1] == skript.PROBE_SOURCE]
    assert len(probes) == 2 and all(b[-5:] == ('-T', 'kingfisher', 'python', '-c', skript.PROBE_SOURCE)
                                    for b in probes)
    assert ('docker', 'pull', BILD) in r.befehle
    werte = skript.env_lesen(env)
    assert werte['KINGFISHER_IMAGE'] == BILD
    assert werte['ICARUS_SIDECAR_TOKEN'] == 'abc' and werte['ICARUS_SECRETS_PASSPHRASE'] == 'geheim'
    assert '# Kopf' in env.read_text()
    assert stat.S_IMODE(env.stat().st_mode) == 0o600
    assert gesagt[-1] == 'Kingfisher ist jetzt auf Fassung 1.2.0. Die Sicherung von vorher heißt vor-update-20261002T080000Z.'
    assert all(a[2] == 'abc' for a in r.anfragen)


def test_schon_aktuell_aendert_nichts(env):
    r = Rechner(env, laeuft='1.2.0')
    ergebnis, gesagt = los(env, r)
    assert ergebnis is None and r.befehle == []
    assert gesagt == ['Kingfisher ist auf dem neuesten Stand (Fassung 1.2.0). Es wurde nichts verändert.']
    assert 'KINGFISHER_IMAGE' not in skript.env_lesen(env)


def test_ohne_manifest_ein_satz(env):
    r = Rechner(env, neueste=None, erreicht=False)
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch) and 'FASSUNG=1.2.0' in fehler.satz and r.befehle == []


@pytest.mark.parametrize('falsch', [{**MANIFEST, 'image': 'ghcr.io/fremd/kingfisher:1.2.0'},
                                    {**MANIFEST, 'image': 'ghcr.io/icarus-health/kingfisher-app:1.1.0'}])
def test_fremdes_bild_wird_nicht_geladen(env, falsch):
    r = Rechner(env, neueste=falsch)
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch) and r.befehle == []


def test_fassung_von_hand(env):
    r = Rechner(env)
    assert los(env, r, '1.2.0')[0] == '1.2.0'
    assert ('POST', '/api/v1/fassung/pruefen', 'abc') not in r.anfragen
    fehler, _ = los(env, Rechner(env), 'v1.3')
    assert isinstance(fehler, skript.Abbruch) and '„v1.3“ ist keine Fassungsnummer' in fehler.satz


def test_ohne_sicherung_wird_nichts_veraendert(env):
    r = Rechner(env, sichern_ok=False)
    fehler, _ = los(env, r)
    assert fehler.satz == skript.SATZ_SICHERUNG
    assert not any(b[:2] == ('docker', 'pull') or b[0] == 'make' for b in r.befehle)
    assert 'KINGFISHER_IMAGE' not in skript.env_lesen(env)


def test_zu_wenig_speicher_vor_sicherung_laesst_update_unberuehrt(env):
    knapp = {**GUTER_SPEICHER, 'root_available_bytes': 1}
    r = Rechner(env, speicherstaende=[knapp])
    original = env.read_text()
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch) and fehler.satz == skript.SATZ_SPEICHER.format(grund='low_space')
    assert env.read_text() == original
    assert not any('exec' in b and b[-1] == skript.SICHERN for b in r.befehle)
    assert not any(b[:2] == ('docker', 'pull') or b[0] == 'make' for b in r.befehle)


def test_unbekannter_speicherstatus_stoppt_vor_der_sicherung(env):
    r = Rechner(env, speicherstaende=[None])
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch) and fehler.satz == skript.SATZ_SPEICHER.format(grund='unavailable')
    assert not any('exec' in b and b[-1] == skript.SICHERN for b in r.befehle)
    assert not any(b[:2] == ('docker', 'pull') or b[0] == 'make' for b in r.befehle)


@pytest.mark.parametrize('speicherstaende, erwartete_pulls', [([None], False), ([GUTER_SPEICHER, None], True),
                                                              (['{'], False), ([GUTER_SPEICHER, '{'], True)])
def test_unbekannter_oder_unlesbarer_probe_status_aendert_config_nicht(env, speicherstaende, erwartete_pulls):
    r = Rechner(env, speicherstaende=speicherstaende)
    original = env.read_text()
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch) and fehler.satz == skript.SATZ_SPEICHER.format(grund='unavailable')
    assert env.read_text() == original and r.laeuft == '1.0.0'
    assert (('docker', 'pull', BILD) in r.befehle) is erwartete_pulls
    assert not any(b[0] == 'make' or 'stop' in b or 'run' in b for b in r.befehle)


def test_zu_wenig_speicher_nach_pull_laesst_altes_bild_und_config_unberuehrt(env):
    knapp = {**GUTER_SPEICHER, 'data_available_inodes': 1}
    r = Rechner(env, speicherstaende=[GUTER_SPEICHER, knapp])
    original = env.read_text()
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch) and fehler.satz == skript.SATZ_SPEICHER.format(grund='low_inodes')
    assert r.laeuft == '1.0.0'
    assert env.read_text() == original
    assert ('docker', 'pull', BILD) in r.befehle
    assert not any(b[0] == 'make' or 'stop' in b or 'run' in b for b in r.befehle)
    assert env.stat().st_mode & 0o777 == 0o600


def test_bild_laedt_nicht_nichts_veraendert(env):
    r = Rechner(env, pull_ok=False)
    fehler, _ = los(env, r)
    assert 'Es wurde nichts verändert' in fehler.satz
    assert not any(b[0] == 'make' for b in r.befehle)
    assert 'KINGFISHER_IMAGE' not in skript.env_lesen(env)


def test_neue_fassung_startet_nicht_dann_snapshot_vor_altem_bild_wiederherstellen(env):
    r = Rechner(env, neu_startet=False)
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch)
    assert 'Prüfmodus' in fehler.satz and 'vor-update-20261002T080000Z' in fehler.satz
    assert r.bild_beim_start == [BILD, PINNED_IMAGE]
    assert skript.env_lesen(env)['KINGFISHER_IMAGE'] == PINNED_IMAGE
    kinds = ['stop' if 'stop' in b else 'restore' if 'run' in b else 'make' if b[0] == 'make' else '' for b in r.befehle]
    assert kinds.index('stop') < kinds.index('restore') < kinds.index('make', kinds.index('restore'))


def test_zurueck_auf_ein_frueheres_fertiges_bild(env):
    skript.env_setzen(env, 'KINGFISHER_IMAGE', 'ghcr.io/icarus-health/kingfisher-app:1.0.0')
    r = Rechner(env, neu_startet=False)
    los(env, r)
    assert r.bild_beim_start == [BILD, PINNED_IMAGE]
    assert skript.env_lesen(env)['KINGFISHER_IMAGE'] == PINNED_IMAGE


def test_auch_vorher_startet_nicht_sagt_was_zu_tun_ist(env):
    r = Rechner(env, neu_startet=False, alt_startet=False)
    fehler, _ = los(env, r)
    assert 'startet nicht geprüft' in fehler.satz


@pytest.mark.parametrize('failure', ['stop', 'restore'])
def test_kein_altes_bild_auf_migrierten_daten_wenn_offline_restore_scheitert(env, failure):
    r = Rechner(env, neu_startet=False, stop_ok=failure != 'stop', restore_ok=failure != 'restore')
    fehler, _ = los(env, r)
    assert 'nicht gestartet' in fehler.satz
    assert r.bild_beim_start == [BILD]
    assert skript.env_lesen(env)['KINGFISHER_IMAGE'] == BILD


def test_rollback_uses_pinned_image_if_old_tag_changes_during_pull(env):
    r = Rechner(env, neu_startet=False)
    tags = {skript.VORGABE_BILD: OLD_ID}

    original = r.lauf
    # Use the original implementation inside the wrapper, without recursion.
    def changing_tags(*command, **options):
        if command[:3] == ('docker', 'image', 'tag'):
            tags[command[4]] = command[3]
        if command[:2] == ('docker', 'pull'):
            tags[skript.VORGABE_BILD] = 'sha256:' + '2' * 64
        result = original(*command, **options)
        if command[:2] == ('docker', 'inspect'):
            name = skript.env_lesen(env).get('KINGFISHER_IMAGE') or skript.VORGABE_BILD
            return subprocess.CompletedProcess(command, 0, stdout=tags.get(name, OLD_ID) + '|' + name + '\n')
        return result
    r.lauf = changing_tags
    error, _ = los(env, r)
    assert 'läuft mit dem vorherigen Bild im Prüfmodus' in error.satz
    assert r.bild_beim_start == [BILD, PINNED_IMAGE]


def test_nicht_eingerichtet(tmp_path):
    fehler, _ = los(tmp_path / '.kingfisher.env', Rechner(tmp_path / '.kingfisher.env'))
    assert fehler.satz == skript.SATZ_NICHT_EINGERICHTET


def test_makefile_hat_das_ziel_und_start_baut_nicht_ueber_ein_fertiges_bild():
    makefile = (WURZEL / 'Makefile').read_text(encoding='utf-8')
    assert 'aktualisieren: $(ENVDATEI)' in makefile and 'scripts/kingfisher_aktualisieren.py' in makefile
    start = makefile[makefile.index('\nstart: $(ENVDATEI)'):makefile.index('\nnotizen-importieren:')]
    assert '--build' not in start.replace("bauen='--build'", '')
    assert "sed -n 's/^KINGFISHER_IMAGE=//p'" in start


def test_speicherpolitik_prueft_reserven_und_ungueltige_werte():
    assert speicher.evaluate_status(GUTER_SPEICHER, before_backup=True) is None
    assert speicher.evaluate_status({**GUTER_SPEICHER, 'root_available_bytes': 1}, True) == 'low_space'
    assert speicher.evaluate_status({**GUTER_SPEICHER, 'data_available_bytes': 1}, False) == 'low_space'
    assert speicher.evaluate_status({**GUTER_SPEICHER, 'root_available_inodes': 1}, True) == 'low_inodes'
    assert speicher.evaluate_status({**GUTER_SPEICHER, 'backup_files': 2**64 - 1}, True) == 'unavailable'
    assert speicher.evaluate_status({**GUTER_SPEICHER, 'backup_bytes': True}, True) == 'unavailable'
    assert speicher.evaluate_status({**GUTER_SPEICHER, 'data_available_inodes': -1}, False) == 'unavailable'
    assert speicher.evaluate_status(GUTER_SPEICHER, 1) == 'unavailable'
    vor_grenze = {**GUTER_SPEICHER, 'root_available_bytes': 512 * 1024**2, 'root_available_inodes': 64,
                  'data_available_bytes': 512 * 1024**2 + 3 * GUTER_SPEICHER['backup_bytes'],
                  'data_available_inodes': 64 + 3 * GUTER_SPEICHER['backup_files']}
    nach_grenze = {**vor_grenze, 'data_available_bytes': 512 * 1024**2 + 2 * GUTER_SPEICHER['backup_bytes'],
                   'data_available_inodes': 64 + 2 * GUTER_SPEICHER['backup_files']}
    assert speicher.evaluate_status(vor_grenze, True) is None
    assert speicher.evaluate_status(nach_grenze, False) is None


def test_probe_zaehlt_regulaere_datenwurzeldateien_ohne_backupordner_oder_dateiinhalte(tmp_path):
    daten = tmp_path / 'daten'
    (daten / 'sicherungen' / 'nicht-zaehlen').mkdir(parents=True)
    (daten / 'produktordner').mkdir()
    (daten / 'self-model.sqlite3').write_bytes(b'abc')
    (daten / 'einstellungen.json').write_bytes(b'12345')
    (daten / 'sicherungen' / 'nicht-zaehlen' / 'gross.zip').write_bytes(b'x' * 1000)

    def statvfs(pfad):
        assert str(pfad) in {'/', str(daten)}
        return type('StatVFS', (), {'f_frsize': 4096, 'f_bavail': 1000, 'f_favail': 200,
                                    'f_files': 1000})()

    namespace = {'__name__': 'storage_probe_under_test'}
    exec(compile(speicher.PROBE_SOURCE, '<storage-probe>', 'exec'), namespace)
    status = namespace['collect_status'](str(daten), statvfs=statvfs)
    assert status == {'root_available_bytes': 4_096_000, 'root_available_inodes': 200,
                      'data_available_bytes': 4_096_000, 'data_available_inodes': 200,
                      'backup_bytes': 8, 'backup_files': 2}


def test_probe_faile_sicher_bei_symlink_oder_unbekanntem_inode_status(tmp_path):
    daten = tmp_path / 'daten'
    daten.mkdir()
    (daten / 'link.sqlite3').symlink_to(tmp_path / 'ziel.sqlite3')
    namespace = {'__name__': 'storage_probe_under_test'}
    exec(compile(speicher.PROBE_SOURCE, '<storage-probe>', 'exec'), namespace)
    with pytest.raises(namespace['ProbeError']):
        namespace['collect_status'](str(daten), statvfs=lambda _: type(
            'StatVFS', (), {'f_frsize': 1, 'f_bavail': 1, 'f_favail': 1, 'f_files': 1}
        )())

    (daten / 'link.sqlite3').unlink()
    with pytest.raises(namespace['ProbeError']):
        namespace['collect_status'](str(daten), statvfs=lambda _: type(
            'StatVFS', (), {'f_frsize': 1, 'f_bavail': 1, 'f_favail': 1, 'f_files': 0}
        )())


@pytest.mark.parametrize('eintrag', ['fifo', 'unreadable'])
def test_probe_faile_sicher_bei_spezialdatei_oder_unlesbarer_datei(tmp_path, eintrag):
    daten = tmp_path / 'daten'
    daten.mkdir()
    datei = daten / 'unknown'
    if eintrag == 'fifo':
        os.mkfifo(datei)
    else:
        datei.write_bytes(b'no-read')
        datei.chmod(0)
    namespace = {'__name__': 'storage_probe_under_test'}
    exec(compile(speicher.PROBE_SOURCE, '<storage-probe>', 'exec'), namespace)
    statvfs = lambda _: type('StatVFS', (), {'f_frsize': 1, 'f_bavail': 10, 'f_favail': 10, 'f_files': 10})()
    with pytest.raises(namespace['ProbeError']):
        namespace['collect_status'](str(daten), statvfs=statvfs)


def test_probe_faile_sicher_bei_statvfs_overflow(tmp_path):
    daten = tmp_path / 'daten'
    daten.mkdir()
    (daten / 'data.db').write_bytes(b'x')
    namespace = {'__name__': 'storage_probe_under_test'}
    exec(compile(speicher.PROBE_SOURCE, '<storage-probe>', 'exec'), namespace)
    statvfs = lambda _: type('StatVFS', (), {'f_frsize': 2**64 - 1, 'f_bavail': 2, 'f_favail': 1,
                                             'f_files': 1})()
    with pytest.raises(namespace['ProbeError']):
        namespace['collect_status'](str(daten), statvfs=statvfs)


def test_probe_resource_gibt_nur_das_schema_als_json_aus(tmp_path):
    daten = tmp_path / 'daten'
    daten.mkdir()
    (daten / 'self-model.sqlite3').write_bytes(b'abc')
    umgebung = dict(os.environ, ICARUS_DATA_DIR=str(daten))
    quelle = (WURZEL / 'scripts' / 'kingfisher_update_storage.py').read_text(encoding='utf-8')
    ergebnis = subprocess.run([sys.executable, '-c', quelle], capture_output=True, text=True, env=umgebung, check=False)
    assert ergebnis.returncode == 0 and not ergebnis.stderr
    status = json.loads(ergebnis.stdout)
    assert set(status) == speicher.SCHEMA
    assert status['backup_bytes'] == 3 and status['backup_files'] == 1
