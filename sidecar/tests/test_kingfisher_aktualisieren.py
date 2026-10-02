"""`make aktualisieren` (scripts/kingfisher_aktualisieren.py): erst sichern, dann laden, dann umschalten; bei einem
Fehler läuft wieder die Fassung von vorher, und der Satz nennt `make zurueck-vor-update`. Ohne Docker, ohne Netz:
Befehle und Antworten des Sidecars sind Attrappen."""
from __future__ import annotations

import importlib.util
import stat
import subprocess
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('kingfisher_aktualisieren', WURZEL / 'scripts' / 'kingfisher_aktualisieren.py')
skript = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(skript)

BILD = 'ghcr.io/icarus-health/kingfisher-app:1.2.0'
MANIFEST = {'fassung': '1.2.0', 'image': BILD, 'datum': '2026-10-02', 'hinweise': [], 'app_mindestens': '1.0.0',
            'dmg': 'https://github.com/Icarus-health/kingfisher-app/releases/download/v1.2.0/Kingfisher.dmg'}


class Rechner:
    """Docker, make und der laufende Sidecar in einem: merkt Befehle, `laeuft` wechselt mit `make start`."""

    def __init__(self, env: Path, *, sichern_ok=True, pull_ok=True, neu_startet=True, alt_startet=True,
                 neueste=MANIFEST, erreicht=True, laeuft='1.0.0') -> None:
        self.env, self.befehle, self.anfragen = env, [], []
        self.sichern_ok, self.pull_ok, self.neu_startet, self.alt_startet = sichern_ok, pull_ok, neu_startet, alt_startet
        self.neueste, self.erreicht, self.laeuft = neueste, erreicht, laeuft
        self.bild_beim_start: list[str | None] = []

    def lauf(self, *befehl, timeout=600, ausgabe=False):
        self.befehle.append(befehl)
        code, aus = 0, ''
        if 'exec' in befehl:
            code, aus = (0, 'Hinweis\nvor-update-20261002T080000Z\n') if self.sichern_ok else (1, '')
        elif befehl[:2] == ('docker', 'pull'):
            code = 0 if self.pull_ok else 1
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
    arten = [('sichern' if 'exec' in b else 'pull' if b[:2] == ('docker', 'pull') else b[0]) for b in r.befehle]
    assert arten == ['sichern', 'pull', 'make']
    sichern = next(b for b in r.befehle if 'exec' in b)
    assert sichern[:4] == ('docker', 'compose', '-p', 'kingfisher') and 'UPDATE_SET_PREFIX' in sichern[-1]
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


def test_bild_laedt_nicht_nichts_veraendert(env):
    r = Rechner(env, pull_ok=False)
    fehler, _ = los(env, r)
    assert 'Es wurde nichts verändert' in fehler.satz
    assert not any(b[0] == 'make' for b in r.befehle)
    assert 'KINGFISHER_IMAGE' not in skript.env_lesen(env)


def test_neue_fassung_startet_nicht_dann_zurueck_auf_vorher(env):
    r = Rechner(env, neu_startet=False)
    fehler, _ = los(env, r)
    assert isinstance(fehler, skript.Abbruch)
    assert fehler.satz.startswith('Das Update hat nicht geklappt; Kingfisher läuft wieder mit der Fassung von vorher.')
    assert 'make zurueck-vor-update' in fehler.satz and 'vor-update-20261002T080000Z' in fehler.satz
    assert r.bild_beim_start == [BILD, None]          # zurück auf genau den Stand von vorher (ohne Zeile: bauen)
    assert 'KINGFISHER_IMAGE' not in skript.env_lesen(env)


def test_zurueck_auf_ein_frueheres_fertiges_bild(env):
    skript.env_setzen(env, 'KINGFISHER_IMAGE', 'ghcr.io/icarus-health/kingfisher-app:1.0.0')
    r = Rechner(env, neu_startet=False)
    los(env, r)
    assert r.bild_beim_start == [BILD, 'ghcr.io/icarus-health/kingfisher-app:1.0.0']
    assert skript.env_lesen(env)['KINGFISHER_IMAGE'] == 'ghcr.io/icarus-health/kingfisher-app:1.0.0'


def test_auch_vorher_startet_nicht_sagt_was_zu_tun_ist(env):
    r = Rechner(env, neu_startet=False, alt_startet=False)
    fehler, _ = los(env, r)
    assert 'make start' in fehler.satz and 'make zurueck-vor-update' in fehler.satz


def test_nicht_eingerichtet(tmp_path):
    fehler, _ = los(tmp_path / '.kingfisher.env', Rechner(tmp_path / '.kingfisher.env'))
    assert fehler.satz == skript.SATZ_NICHT_EINGERICHTET


def test_makefile_hat_das_ziel_und_start_baut_nicht_ueber_ein_fertiges_bild():
    makefile = (WURZEL / 'Makefile').read_text(encoding='utf-8')
    assert 'aktualisieren: $(ENVDATEI)' in makefile and 'scripts/kingfisher_aktualisieren.py' in makefile
    start = makefile[makefile.index('\nstart: $(ENVDATEI)'):makefile.index('\nnotizen-importieren:')]
    assert '--build' not in start.replace("bauen='--build'", '')
    assert "sed -n 's/^KINGFISHER_IMAGE=//p'" in start
