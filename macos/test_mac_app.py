"""Statische Sicherungen der Mac-App (Kingfisher.dmg), prüfbar ohne Mac.

Was nur auf dem Mac geht (Fenster, Docker Desktop, Gatekeeper), steht als Checkliste in macos/README.md.
Hier wird gesichert, dass die App zur Schnittstelle und zum Bestand passt: Bündelwerte, Compose-Datei im
Bündel, Brückenname und Aktion, Bildprüfung, Variablennamen, Docker-Orte, Projekt, Volume, Sicherungsroute.
Ist `swiftc` vorhanden, läuft zusätzlich das Prüfprogramm der reinen Logik (macos/tests/main.swift).

    .venv/bin/python -m pytest macos/test_mac_app.py -q
"""
from __future__ import annotations

import importlib.util
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MACOS = REPO / 'macos'
APP = MACOS / 'App'
LOGIC = APP / 'Logic'
BUILD = MACOS / 'build_dmg.sh'


def swift(*teile: str) -> str:
    return (MACOS.joinpath(*teile)).read_text(encoding='utf-8')


def swift_konstante(text: str, name: str) -> str:
    treffer = re.search(rf'static let {name} = "([^"]*)"', text)
    assert treffer, f'Konstante {name} fehlt'
    return treffer.group(1)


def starter():
    spec = importlib.util.spec_from_file_location('kingfisher_starten', REPO / 'scripts/kingfisher_starten.py')
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def bau(tmp_path: Path, *argumente: str, compose: bool, version: str | None = None,
        umgebung: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    """Das Bauskript in einer leeren Kopie des Repos ausführen (ohne Mac bricht es vor dem Übersetzen ab)."""
    (tmp_path / 'macos').mkdir()
    shutil.copy(BUILD, tmp_path / 'macos/build_dmg.sh')
    if compose:
        (tmp_path / 'deploy').mkdir()
        (tmp_path / 'deploy/compose.app.yaml').write_text('services: {}\n')
    if version is not None:
        (tmp_path / 'VERSION').write_text(version)
    env = {k: v for k, v in os.environ.items() if k != 'KINGFISHER_FASSUNG'}
    env.update(umgebung or {})
    return subprocess.run(['bash', str(tmp_path / 'macos/build_dmg.sh'), *argumente], capture_output=True,
                          text=True, env=env, cwd=tmp_path)


# -- Bündel ------------------------------------------------------------------

def test_info_plist_wie_im_bestand():
    vorlage = (APP / 'Info.plist').read_text(encoding='utf-8')
    assert '__FASSUNG__' in vorlage and '__BUNDLE_VERSION__' in vorlage
    info = plistlib.loads(vorlage.replace('__FASSUNG__', '1.0.0-rc.1').replace('__BUNDLE_VERSION__', '1.0.0').encode())
    fenster = (REPO / 'scripts/build_mac_window.py').read_text(encoding='utf-8')
    bestand_id = re.search(r"CFBundleIdentifier='([^']+)'", fenster).group(1)
    bestand_macos = re.search(r"LSMinimumSystemVersion='([^']+)'", fenster).group(1)
    assert info['CFBundleIdentifier'] == bestand_id == 'local.kingfisher.window'
    assert info['LSMinimumSystemVersion'] == bestand_macos
    assert f'MINDEST_MACOS="{bestand_macos}"' in BUILD.read_text(encoding='utf-8')
    assert info['CFBundleExecutable'] == 'Kingfisher'
    assert info['CFBundlePackageType'] == 'APPL'
    assert info['CFBundleShortVersionString'] == '1.0.0-rc.1'
    assert info['CFBundleVersion'] == '1.0.0'
    assert info['NSAppTransportSecurity']['NSAllowsLocalNetworking'] is True


def test_bauskript_legt_compose_app_ins_buendel():
    skript = BUILD.read_text(encoding='utf-8')
    assert 'COMPOSE_APP="deploy/compose.app.yaml"' in skript
    assert 'cp "$COMPOSE_APP" "$APP/Contents/Resources/compose.yaml"' in skript
    # Die App sucht genau diese Ressource.
    assert 'forResource: "compose", withExtension: "yaml"' in swift('App', 'Paths.swift')


def test_bauskript_bricht_ohne_compose_app_klar_ab(tmp_path):
    ergebnis = bau(tmp_path, compose=False)
    assert ergebnis.returncode != 0
    assert 'deploy/compose.app.yaml' in ergebnis.stderr
    assert not (tmp_path / 'deploy').exists(), 'das Skript darf die Datei nicht selbst anlegen'
    assert not (tmp_path / 'dist').exists()


@pytest.mark.skipif(sys.platform == 'darwin', reason='prüft den Abbruch außerhalb von macOS')
def test_bauskript_nur_auf_dem_mac(tmp_path):
    ergebnis = bau(tmp_path, compose=True)
    assert ergebnis.returncode != 0
    assert 'nur auf macOS' in ergebnis.stderr


@pytest.mark.parametrize('version, umgebung, erwartet', [
    (None, {}, '0.0.0'),
    ('1.2.3\n', {}, '1.2.3'),
    ('1.2.3', {'KINGFISHER_FASSUNG': '1.2.4-rc.1'}, '1.2.4-rc.1'),
])
def test_fassung_aus_version(tmp_path, version, umgebung, erwartet):
    ergebnis = bau(tmp_path, '--nur-fassung', compose=False, version=version, umgebung=umgebung)
    assert ergebnis.returncode == 0, ergebnis.stderr
    assert ergebnis.stdout.strip() == erwartet


@pytest.mark.parametrize('fassung', ['1.0', 'v1.0.0', '1.0.0+build', '01.0.0', '1.0.0; rm -rf /'])
def test_ungueltige_fassung_wird_abgewiesen(tmp_path, fassung):
    ergebnis = bau(tmp_path, '--nur-fassung', compose=False, umgebung={'KINGFISHER_FASSUNG': fassung})
    assert ergebnis.returncode != 0
    assert 'SemVer' in ergebnis.stderr


def test_unbekannte_paketarchitektur_bricht_vor_dateiaenderungen_ab(tmp_path):
    result = bau(tmp_path, '--nur-fassung', compose=False,
                 umgebung={'KINGFISHER_ARCHITEKTUR': 'arm64; external-command'})
    assert result.returncode != 0
    assert 'Architektur' in result.stderr
    assert not (tmp_path / 'build').exists()
    assert not (tmp_path / 'dist').exists()


def test_alle_quellen_werden_uebersetzt():
    skript = BUILD.read_text(encoding='utf-8')
    assert 'QUELLEN=(macos/Shared/*.swift macos/App/Logic/*.swift macos/App/*.swift)' in skript
    ordner = {p.parent for p in (MACOS / 'App').rglob('*.swift')} | {p.parent for p in (MACOS / 'Shared').rglob('*.swift')}
    assert ordner == {APP, LOGIC, MACOS / 'Shared'}, 'neuer Unterordner ohne Eintrag im Bauskript'
    assert 'arm64 x86_64' in skript and 'lipo -create' in skript
    assert 'codesign --force --deep --sign -' in skript
    assert 'ln -s /Applications "$INHALT/Programme"' in skript
    assert 'dist/Kingfisher.dmg' in skript


# -- Schnittstelle zur Oberfläche ------------------------------------------------

def test_bruecke_heisst_kingfisher_mit_aktion_aktualisieren():
    ablauf = swift('App', 'Logic', 'UpdateFlow.swift')
    assert swift_konstante(ablauf, 'bridgeName') == 'kingfisher'
    assert swift_konstante(ablauf, 'action') == 'aktualisieren'
    assert 'fields["aktion"] as? String == UpdateRequest.action' in ablauf
    app = swift('App', 'AppDelegate.swift')
    assert 'userContentController.add(bridge, name: UpdateRequest.bridgeName)' in app
    assert 'message.frameInfo.isMainFrame' in app
    assert 'UpdateRequest(message: message.body)' in app


def test_bildpruefung_verlangt_praefix_und_fassung_als_tag():
    release = swift('App', 'Logic', 'Release.swift')
    assert swift_konstante(release, 'prefix') == 'ghcr.io/icarus-health/kingfisher-app:'
    assert 'image.hasPrefix(prefix)' in release
    assert 'String(image.dropFirst(prefix.count)) == fassung' in release
    assert 'ImageName.isValid(image, fassung: fassung)' in swift('App', 'Logic', 'UpdateFlow.swift')


def test_manifest_adresse():
    assert 'URL(string: "https://icarus-health.github.io/kingfisher-app/latest.json")' in swift('App', 'Logic', 'Release.swift')


def test_update_nur_nach_nachricht_der_seite():
    """Kein Update ohne Klick: Updater.perform hat genau einen Aufrufer, und der kommt aus der Brücke."""
    app = swift('App', 'AppDelegate.swift')
    assert app.count('requestUpdate(') == 2, 'Definition und genau ein Aufruf'
    assert re.search(r'onUpdate: \{ \[weak self\] request in self\?\.requestUpdate\(request\) \}', app)
    alle = '\n'.join(p.read_text(encoding='utf-8') for p in APP.rglob('*.swift'))
    assert alle.count('.perform(request)') == 1
    assert 'Updater' not in swift('App', 'Startup.swift')


# -- Bestand -----------------------------------------------------------------

def test_variablennamen_wie_der_starter(tmp_path):
    datei = starter().schluessel_anlegen(tmp_path)
    namen = {zeile.split('=', 1)[0] for zeile in datei.read_text().splitlines() if '=' in zeile and not zeile.startswith('#')}
    env = swift('App', 'Logic', 'EnvFile.swift')
    assert {swift_konstante(env, 'token'), swift_konstante(env, 'passphrase')} == namen
    compose = (REPO / 'compose.yaml').read_text(encoding='utf-8')
    for name in namen:
        assert f'{name}=${{{name}:?' in compose


def test_docker_orte_wie_der_starter():
    docker = swift('App', 'Docker.swift')
    liste = re.search(r'static let places = \[(.*?)\]', docker, re.S).group(1)
    assert tuple(re.findall(r'"([^"]+)"', liste)) == starter().DOCKER_ORTE
    assert starter().DOCKER_DOWNLOAD in swift('App', 'Logic', 'Texts.swift')
    assert starter().OLLAMA_DOWNLOAD in swift('App', 'Logic', 'Texts.swift')


def test_projekt_volume_und_adresse_wie_make_start():
    installation = swift('App', 'Logic', 'Installation.swift')
    makefile = (REPO / 'Makefile').read_text(encoding='utf-8')
    compose = (REPO / 'compose.yaml').read_text(encoding='utf-8')
    projekt = re.search(r'docker compose -p (\S+)', makefile).group(1)
    assert swift_konstante(installation, 'project') == projekt
    volume = re.search(r'^volumes:\n  ([\w-]+):', compose, re.M).group(1)
    assert swift_konstante(installation, 'dataVolume') == f'{projekt}_{volume}'
    assert re.search(r'ENVDATEI := (\S+)', makefile).group(1) == swift_konstante(installation, 'starterEnvName')
    assert '"127.0.0.1:8890:8890"' in compose
    assert 'URL(string: "http://127.0.0.1:8890")!' in swift('App', 'Paths.swift')


def test_sicherung_ueber_die_vorhandene_route():
    server = (REPO / 'sidecar/icarus_memory/server.py').read_text(encoding='utf-8')
    assert '@app.post("/backups", dependencies=guard, status_code=201)' in server
    assert 'x_icarus_token: Annotated[str | None, Header()]' in server  # FastAPI: Kopf x-icarus-token
    loopback = swift('App', 'Loopback.swift')
    assert 'URL(string: "backups?vor_update=true", relativeTo: AppPaths.origin)' in loopback
    assert 'request.httpMethod = "POST"' in loopback
    assert 'forHTTPHeaderField: "x-icarus-token"' in loopback
    assert 'response.status == 201' in loopback
    assert 'UpdateSnapshotName.isValid(name)' in loopback
    assert 'return name' in loopback


def test_update_checks_target_version_and_restores_snapshot_before_old_image():
    updater = swift('App', 'Updater.swift')
    loopback = swift('App', 'Loopback.swift')
    assert 'Loopback.waitForVersion(request.fassung, token: token)' in updater
    assert 'authenticatedVersion(token: token) == expected' in loopback
    assert 'docker.compose(["stop", "kingfisher"]' in updater
    assert '"-m", "icarus_memory.update_restore", snapshotName' in updater
    assert updater.index('"-m", "icarus_memory.update_restore"') < updater.index('restored.set(EnvKey.image, pinnedTag)')
    assert 'docker.runningImage(paths: paths)?.id == previous.id' in updater
    assert 'Loopback.inspectionMode(token: token)' in updater


def test_first_launch_does_not_convert_existing_local_installation():
    startup = swift('App', 'Startup.swift')
    assert 'docker.projectContainer() != nil || docker.volumeExists(Installation.dataVolume)' in startup
    assert 'return .failed(Satz.bestehendeInstallation)' in startup
    assert startup.index('return .failed(Satz.bestehendeInstallation)') < startup.index('let image = firstImage(')
    assert 'docker.installedImage(paths: paths)' in startup
    assert 'Loopback.authenticatedVersion(token: token) == expectedVersion' in startup


def test_name_und_zeitzone_des_macs_gehen_an_den_container():
    """V3: Was der Mac weiß, fragt der Assistent nicht. Jeder Compose-Aufruf gibt den vollen Namen (nur als Vorschlag)
    und die Zeitzone des Macs mit, die Zeitzone nur, wenn die Env-Datei keine eigene setzt; beide Compose-Dateien
    reichen den Namen in den Container."""
    env = swift('App', 'Logic', 'EnvFile.swift')
    assert swift_konstante(env, 'vollerName') == 'KINGFISHER_VOLLER_NAME'
    assert swift_konstante(env, 'zeitzone') == 'KINGFISHER_TIMEZONE'
    compose = re.search(r'func compose\(.*?\n    \}', swift('App', 'Docker.swift'), re.S).group(0)
    assert 'environment[EnvKey.vollerName] = NSFullUserName()' in compose
    zeitzone = compose.index('environment[EnvKey.zeitzone] = TimeZone.current.identifier')
    pruefung = compose.index('$0.hasPrefix(EnvKey.zeitzone + "=")')
    assert pruefung < zeitzone < compose.index('return run(')
    assert 'environment: environment' in compose
    for datei in ('compose.yaml', 'deploy/compose.app.yaml'):
        text = (REPO / datei).read_text(encoding='utf-8')
        assert '- KINGFISHER_VOLLER_NAME=${KINGFISHER_VOLLER_NAME:-}' in text, datei
        assert '- KINGFISHER_TIMEZONE=${KINGFISHER_TIMEZONE:-Europe/Berlin}' in text, datei
    # Der Sidecar liest genau diesen Namen, und nur als Vorschlag.
    assert "'KINGFISHER_VOLLER_NAME'" in (REPO / 'sidecar/icarus_memory/name_vorschlag.py').read_text(encoding='utf-8')


def test_logik_braucht_nur_foundation():
    """Die reine Logik muss ohne AppKit übersetzen, sonst lässt sie sich nicht außerhalb des Macs prüfen."""
    for datei in LOGIC.glob('*.swift'):
        importe = set(re.findall(r'^import (\w+)', datei.read_text(encoding='utf-8'), re.M))
        assert 'Foundation' in importe and importe <= {'Foundation', 'CoreFoundation'}, f'{datei.name}: {importe}'


def test_deutsche_anfuehrungszeichen_in_swift():
    dateien = [str(p) for p in MACOS.rglob('*.swift')]
    ergebnis = subprocess.run([sys.executable, str(REPO / 'scripts/pruefe_anfuehrungszeichen.py'), *dateien],
                              capture_output=True, text=True)
    assert ergebnis.returncode == 0, ergebnis.stdout


# -- Workflow ----------------------------------------------------------------

def test_workflow_baut_auf_unterstuetztem_macos_15():
    text = (REPO / '.github/workflows/mac-app.yml').read_text(encoding='utf-8')
    assert re.search(r'^  workflow_call:\n    inputs:\n      fassung:', text, re.M)
    assert re.search(r'^  pull_request:\n    paths:', text, re.M)
    assert '"macos/**"' in text and '".github/workflows/mac-app.yml"' in text
    assert 'runs-on: macos-15' in text
    assert 'bash macos/build_dmg.sh' in text
    assert 'name: Kingfisher.dmg' in text and 'path: dist/Kingfisher.dmg' in text
    # Die Fassung geht als Umgebung ins Skript, nie als Text in den Befehl.
    assert 'KINGFISHER_FASSUNG: ${{ inputs.fassung }}' in text
    assert not re.search(r'run:.*\$\{\{\s*inputs\.', text)


# -- Reine Logik, wenn swiftc da ist -----------------------------------------------

@pytest.mark.skipif(shutil.which('swiftc') is None and not (sys.platform == 'darwin' and shutil.which('xcrun')),
                    reason='swiftc fehlt; läuft im Workflow mac-app.yml')
def test_logik_pruefprogramm(tmp_path):
    befehl = ['swiftc'] if shutil.which('swiftc') else ['xcrun', 'swiftc']
    programm = tmp_path / 'logik'
    quellen = [str(p) for p in sorted(LOGIC.glob('*.swift'))] + [str(MACOS / 'Shared/PowerReporter.swift'),
                                                                  str(MACOS / 'Shared/Mitteilungen.swift'),
                                                                  str(MACOS / 'tests/main.swift')]
    uebersetzt = subprocess.run([*befehl, *quellen, '-o', str(programm)], capture_output=True, text=True)
    assert uebersetzt.returncode == 0, uebersetzt.stderr
    lauf = subprocess.run([str(programm)], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert 'alle Prüfungen bestanden' in lauf.stdout


# -- Mitteilungen (Etappe 5) -------------------------------------------------------

def test_mitteilungen_reporter_vorhanden_mit_kategorie_und_zwei_aktionen():
    """Der Reporter zeigt jede Mitteilung mit „Öffnen“ und „War überflüssig“; die Kennungen stehen in der reinen Logik."""
    logik_importe = set(re.findall(r'^import (\w+)', swift('Shared', 'Mitteilungen.swift'), re.M))
    # Foundation, unter Linux dazu FoundationNetworking (URLRequest); nichts vom Mac (AppKit, UserNotifications).
    assert logik_importe <= {'Foundation', 'FoundationNetworking'} and 'Foundation' in logik_importe, \
        'die reine Logik muss im Prüfprogramm ohne Mac übersetzen'
    logik = swift('Shared', 'Mitteilungen.swift')
    reporter = swift('Shared', 'NotificationReporter.swift')
    assert swift_konstante(logik, 'kategorie') == 'KINGFISHER_MITTEILUNG'
    assert swift_konstante(logik, 'aktionOeffnen') == 'oeffnen'
    assert swift_konstante(logik, 'aktionUeberfluessig') == 'ueberfluessig'
    assert 'UNNotificationCategory(identifier: MitteilungenPfad.kategorie' in reporter
    assert 'UNNotificationAction(identifier: MitteilungenPfad.aktionOeffnen, title: "Öffnen"' in reporter
    assert 'UNNotificationAction(identifier: MitteilungenPfad.aktionUeberfluessig, title: "War überflüssig"' in reporter
    assert 'import UserNotifications' in reporter
    assert 'static let interval: TimeInterval = 300' in logik, 'alle fünf Minuten'
    assert 'maximumResponseBytes = 4096' in reporter, 'Antwort höchstens 4 KB'


def test_mitteilungen_reporter_spricht_nur_die_mitteilungsrouten_am_loopback():
    logik = swift('Shared', 'Mitteilungen.swift')
    server = (REPO / 'sidecar/icarus_memory/mitteilungen_routes.py').read_text(encoding='utf-8')
    for pfad in ('/api/v1/mitteilungen/faellig', '/api/v1/mitteilungen/einstellung', '/api/v1/mitteilungen/erlaubnis'):
        assert f'"{pfad}"' in logik and f"'{pfad}'" in server, pfad
    assert "'/api/v1/mitteilungen/{kennung}/zugestellt'" in server and "'/api/v1/mitteilungen/{kennung}/rueckmeldung'" in server
    assert '"/api/v1/mitteilungen/" + kennung + "/zugestellt"' in logik
    assert '"/api/v1/mitteilungen/" + kennung + "/rueckmeldung"' in logik
    # Dieselbe Adressprüfung wie der Energiebericht: nur 127.0.0.1, Token im Kopf, keine Weiterleitungen.
    assert 'PowerReportRequest.make(origin: origin, source: .unknown, token: token)' in logik
    reporter = swift('Shared', 'NotificationReporter.swift')
    assert 'willPerformHTTPRedirection' in reporter and 'completionHandler(nil)' in reporter
    assert 'connectionProxyDictionary = [:]' in reporter


def test_mitteilungen_erlaubnis_nur_bei_eingeschaltetem_schalter_und_nie_inhalt_im_protokoll():
    reporter = swift('Shared', 'NotificationReporter.swift')
    assert 'requestAuthorization' in reporter
    assert reporter.index('einstellung.an') < reporter.index('requestAuthorization'), 'erst der Schalter, dann die Systemfrage'
    assert 'print(' not in reporter and 'NSLog(' not in reporter and 'os_log' not in reporter, 'kein Protokoll mit Inhalt'
    logik = swift('Shared', 'Mitteilungen.swift')
    assert 'print(' not in logik and 'NSLog(' not in logik


def test_bauskript_bindet_user_notifications_ein_und_delegate_ist_verdrahtet():
    skript = BUILD.read_text(encoding='utf-8')
    assert '-framework UserNotifications' in skript
    app = swift('App', 'AppDelegate.swift')
    assert 'private var notificationReporter: NotificationReporter?' in app
    assert 'NotificationReporter(origin: AppPaths.origin, tokenFile: paths.envFile' in app
    assert 'notificationReporter?.stop()' in app
    assert 'surface.load(path:' in swift('Shared', 'NotificationReporter.swift') or 'onOpen' in app, 'Öffnen führt zur Seite'
    assert 'self?.surface.load(path: pfad)' in app or 'self?.openPage(pfad)' in app


def test_mitteilung_aus_der_antwort_wird_streng_geprueft():
    """Die reine Logik nimmt nur kleine, bekannte Felder und Pfade innerhalb der eigenen Seite."""
    logik = swift('Shared', 'Mitteilungen.swift')
    assert 'maxTitel = 60' in logik and 'maxSatz = 140' in logik and 'maxJeAbruf = 3' in logik
    assert 'pfad.hasPrefix("/")' in logik and '"//"' in logik and '":"' in logik or 'pfad.contains(":")' in logik
    main = (MACOS / 'tests/main.swift').read_text(encoding='utf-8')
    assert 'Mitteilung.parse(' in main or 'Mitteilungen.parse(' in main, 'die Logik hat Prüfungen im Swift-Prüfprogramm'
