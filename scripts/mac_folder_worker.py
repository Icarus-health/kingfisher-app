#!/usr/bin/env python3
"""Small consent-bound host worker for the local folder-sync endpoint.

Drei Rollen, ein Programm: `dokumente` beobachtet den mit `--folder` festgelegten
Ordner; `transkripte` beobachtet den Eingangsordner für Mitschriften aus
Meetings. Dessen Ordner tippt niemand: Die Oberfläche bittet um eine Auswahl, der
Helfer zeigt den Auswahldialog des Mac und meldet nur den gewählten Ordner.

`akten` ist die Gegenrichtung und nur lesend für den Nutzer: Der Helfer holt den
fertigen Ordner „Akten als Ordner“ vom Sidecar ab und legt ihn im gewählten Ordner
als Unterordner `Kingfisher Akten` ab. Er ersetzt nur einen Ordner mit der Marke
`.kingfisher-akten`, nie fremde Dateien, und liest nie etwas aus dem Ordner zurück.
"""
from __future__ import annotations

import argparse
import base64
import fcntl
import hashlib
import json
import os
import stat
import io
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from urllib.parse import urlparse

SUPPORTED = {".md", ".markdown", ".txt", ".org", ".rst", ".csv", ".docx", ".pdf", ".srt", ".vtt"}
TEXT = SUPPORTED - {".docx", ".pdf"}
TRANSKRIPTE = {".txt", ".vtt", ".srt", ".docx", ".md"}
VORGABE_ORDNER = ("Documents", "Kingfisher", "Transkripte")
VORGABE_AKTEN = ("Documents", "Kingfisher", "Akten")
AKTEN_ORDNERNAME = "Kingfisher Akten"
AKTEN_MARKE = ".kingfisher-akten"
AKTEN_MAX_DATEIEN, AKTEN_MAX_DATEI, AKTEN_MAX_GESAMT = 200_000, 50 * 1024 * 1024, 2 * 1024 ** 3
MAX_BYTES, MAX_TEXT, MAX_FILES = 5 * 1024 * 1024, 512 * 1024, 2000


def _error(name: str, message: str) -> str:
    return f"{name}: {message[:180]}"


class StopSync(Exception):
    """Consent changed or service unavailable; stop before another read."""


def scan(root: str | Path, consume, *, permitted=lambda: None, expected_root_id=None,
         supported=SUPPORTED, with_mtime=False) -> dict:
    """Read a stable snapshot and pass valid supported files to ``consume``.

    Mit ``with_mtime`` bekommt ``consume`` als dritten Wert die Änderungszeit der Datei.
    """
    root = Path(root)
    observed, errors = [], []
    root_fd = None
    try:
        root_lstat = os.lstat(root)
        if not stat.S_ISDIR(root_lstat.st_mode) or stat.S_ISLNK(root_lstat.st_mode):
            return {"observed": [], "errors": [_error("root", "kein sicherer Ordner")], "complete": False}
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        root_stat = os.fstat(root_fd)
        if (root_lstat.st_dev, root_lstat.st_ino) != (root_stat.st_dev, root_stat.st_ino):
            return {"observed": [], "errors": [_error("root", "Ordner hat sich geändert")], "complete": False}
        actual_id = hashlib.sha256(f"{root.resolve()}\0{root_stat.st_dev}\0{root_stat.st_ino}".encode()).hexdigest()[:32]
        if expected_root_id is not None and actual_id != expected_root_id:
            return {"observed": [], "errors": ["Ordner wurde ausgetauscht; erneute Freigabe erforderlich"], "complete": False}
        count = 0
        def inaccessible(error):
            raise error
        for dirname, dirnames, filenames, dirfd in os.fwalk(".", dir_fd=root_fd, topdown=True, follow_symlinks=False, onerror=inaccessible):
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                permitted()
                if count >= MAX_FILES:
                    errors.append(_error("scan", "mehr als 2.000 Dateien"))
                    return {"observed": observed, "errors": errors[:30], "complete": False}
                try:
                    if stat.S_ISLNK(os.stat(name, dir_fd=dirfd, follow_symlinks=False).st_mode):
                        continue
                    fd = os.open(name, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0), dir_fd=dirfd)
                    try:
                        before = os.fstat(fd)
                        if not stat.S_ISREG(before.st_mode):
                            continue
                        rel = str(Path(dirname) / name)
                        rel = rel.replace(os.sep, "/")
                        observed.append(rel)
                        count += 1
                        suffix = Path(name).suffix.lower()
                        if suffix not in supported:
                            continue
                        if time.time() - before.st_mtime <= 2:
                            errors.append(_error(rel, "Datei wird noch geschrieben; nächster Versuch folgt"))
                            continue
                        if before.st_size > MAX_BYTES:
                            if before.st_size > MAX_BYTES:
                                errors.append(_error(rel, "Datei überschreitet 5 MiB"))
                            continue
                        limit = MAX_TEXT if suffix in TEXT else MAX_BYTES
                        permitted()
                        data = b""
                        while len(data) <= limit:
                            chunk = os.read(fd, min(1024 * 1024, limit + 1 - len(data)))
                            if not chunk:
                                break
                            data += chunk
                        after = os.fstat(fd)
                        if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
                            errors.append(_error(rel, "Datei wurde während des Lesens geändert"))
                        elif len(data) > limit:
                            errors.append(_error(rel, "Datei überschreitet die erlaubte Größe"))
                        else:
                            consume(rel, data, before.st_mtime) if with_mtime else consume(rel, data)
                    finally:
                        os.close(fd)
                except (OSError, UnicodeError, ValueError) as exc:
                    errors.append(_error(name, "Datei konnte nicht gelesen werden"))
        end_stat = os.stat(root, follow_symlinks=False)
        complete = (root_stat.st_dev, root_stat.st_ino, root_stat.st_mtime_ns) == (end_stat.st_dev, end_stat.st_ino, end_stat.st_mtime_ns)
        if not complete:
            errors.append(_error("root", "Ordner hat sich geändert"))
        return {"observed": observed, "errors": errors[:30], "complete": complete and not errors}
    except (OSError, ValueError) as exc:
        return {"observed": observed, "errors": errors[:29] + [_error("root", "Ordner ist nicht erreichbar")], "complete": False}

    finally:
        if root_fd is not None:
            os.close(root_fd)


def root_id(folder: str | Path) -> str:
    selected = Path(folder).expanduser()
    info = selected.lstat()
    if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
        raise ValueError('kein sicherer Ordner')
    path = selected.resolve(strict=True)
    info = os.stat(path, follow_symlinks=False)
    value = f"{path}\0{info.st_dev}\0{info.st_ino}".encode()
    return hashlib.sha256(value).hexdigest()[:32]


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Api:
    def __init__(self, url, token, prefix='/api/v1/folder-sync'):
        parsed = urlparse(url)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or parsed.username
                or parsed.password or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise ValueError('Nur die lokale Kingfisher-Adresse ist erlaubt.')
        self.url = url.rstrip('/')
        self.prefix = prefix
        self.token = token
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, path='', body=None):
        request = urllib.request.Request(self.url + self.prefix + path,
            data=None if body is None else json.dumps(body).encode(),
            headers={'X-Icarus-Token': self.token, 'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=30) as response:
            return json.load(response)

    def bytes(self, path=''):
        """Eine Binärantwort (das Archiv der Akten) mit ihren Kopfzeilen."""
        request = urllib.request.Request(self.url + self.prefix + path, headers={'X-Icarus-Token': self.token})
        with self.opener.open(request, timeout=120) as response:
            return response.read(), dict(response.headers)


def synchronize(api, folder, state, *, supported=SUPPORTED, with_mtime=False):
    scope = {'root_id': state['root_id'], 'generation': state['generation']}
    run = api.call('/begin', scope)
    scope['run_id'] = run['run_id']
    def permitted():
        try:
            current = api.call()
        except OSError as exc:
            raise StopSync() from exc
        if (not current['enabled'] or current['generation'] != scope['generation']
                or current['root_id'] != scope['root_id']):
            raise StopSync()
    def consume(name, data, mtime=None):
        permitted()
        try:
            extra = {'modified': mtime} if mtime is not None else {}
            api.call('/files', {**scope, 'filename': name, **extra,
                'content_base64': base64.b64encode(data).decode('ascii')})
        except urllib.error.HTTPError as exc:
            if exc.code == 422:
                raise ValueError('Datei konnte nicht übernommen werden.') from exc
            raise StopSync() from exc
        except OSError as exc:
            raise StopSync() from exc
    report = scan(folder, consume, permitted=permitted, expected_root_id=scope['root_id'],
                  supported=supported, with_mtime=with_mtime)
    permitted()
    return api.call('/finish', {**scope, **report})


class Auswahl:
    """Der gewählte Mitschriftenordner, dauerhaft neben der privaten Konfiguration gemerkt."""

    def __init__(self, datei: Path):
        self.datei = Path(datei)
        self.folder: Path | None = None
        try:
            gemerkt = json.loads(self.datei.read_text())['folder']
            if isinstance(gemerkt, str) and Path(gemerkt).is_absolute():
                self.folder = Path(gemerkt)
        except (OSError, ValueError, KeyError, TypeError):
            pass

    def setzen(self, folder: Path) -> None:
        self.folder = Path(folder)
        self.datei.write_text(json.dumps({'folder': str(self.folder)}))
        os.chmod(self.datei, 0o600)

    def vergessen(self) -> None:
        self.folder = None
        try:
            self.datei.unlink()
        except FileNotFoundError:
            pass


def osascript_dialog(frage: str = "Ordner für Meeting-Mitschriften wählen") -> Path | None:
    """Der Auswahldialog des Mac. Abbruch durch den Nutzer ergibt nichts."""
    skript = (f'POSIX path of (choose folder with prompt "{frage}" '
              'default location (path to documents folder))')
    try:
        ergebnis = subprocess.run(['osascript', '-e', skript], capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.SubprocessError):
        return None
    text = ergebnis.stdout.strip()
    return Path(text).expanduser() if ergebnis.returncode == 0 and text.startswith('/') else None


def waehle_ordner(modus: str, *, dialog=osascript_dialog, home: Path | None = None,
                  vorgabe: tuple = VORGABE_ORDNER) -> Path | None:
    """`vorgabe`: Dokumente/Kingfisher/Transkripte anlegen; `waehlen`: der Dialog. Sonst nichts."""
    if modus == 'vorgabe':
        ordner = Path(home or Path.home()).joinpath(*vorgabe)
        ordner.mkdir(parents=True, exist_ok=True)
        return ordner
    if modus == 'waehlen':
        return dialog()
    return None


def transkript_schritt(api, auswahl: Auswahl, waehle=waehle_ordner) -> dict:
    """Ein Durchgang der Rolle `transkripte`: dem Server den Stand melden und auf Anfragen antworten.

    Der Server kann nur bitten, den Dialog zu zeigen; den Ordner bestimmt allein die Wahl am Mac.
    Nach dem Trennen bietet der Helfer den gemerkten Ordner nicht mehr an.
    """
    anmeldung = {}
    if auswahl.folder is not None:
        try:
            anmeldung = {'root_id': root_id(auswahl.folder), 'folder': str(auswahl.folder)}
        except (OSError, ValueError):
            anmeldung = {}      # Ordner gerade nicht erreichbar: nichts anbieten, die Wahl bleibt gemerkt
    state = api.call('/worker', anmeldung)
    anfrage = state.get('pick_request')
    if anfrage:
        gewaehlt = waehle(anfrage.get('modus'))
        if gewaehlt is None:
            return api.call('/worker', {'cancelled': anfrage['id']})
        auswahl.setzen(gewaehlt)
        return api.call('/worker', {'root_id': root_id(gewaehlt), 'folder': str(gewaehlt), 'picked': anfrage['id']})
    if state.get('getrennt') and auswahl.folder is not None:
        auswahl.vergessen()
    return state


def main_transkripte(args, token) -> None:
    api = Api(args.url, token, '/api/v1/transcript-sync')
    auswahl = Auswahl(args.env_file.with_suffix('.transkripte.json'))
    lock = args.env_file.with_suffix('.transkripte.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    last_sync, generation = 0, None
    while True:
        try:
            state = transkript_schritt(api, auswahl)
            if (auswahl.folder is not None and state.get('enabled') and state.get('root_id')
                    and state['root_id'] == root_id(auswahl.folder)
                    and (state['generation'] != generation or time.monotonic() - last_sync >= 60)):
                synchronize(api, auswahl.folder, state, supported=TRANSKRIPTE, with_mtime=True)
                last_sync, generation = time.monotonic(), state['generation']
        except (OSError, ValueError, StopSync):
            print('Mitschriften-Eingang unterbrochen; erneuter Versuch folgt.', flush=True)
        time.sleep(5)


# -- Akten als Ordner: abholen und ablegen (nur Schreiben, nie Zurücklesen) --

def akten_dialog() -> Path | None:
    return osascript_dialog("Ordner für die Akten wählen")


def waehle_akten_ordner(modus: str, *, dialog=akten_dialog, home: Path | None = None) -> Path | None:
    return waehle_ordner(modus, dialog=dialog, home=home, vorgabe=VORGABE_AKTEN)


def akten_ordner_tauschen(neu: Path, ziel: Path) -> None:
    """Setzt `neu` an die Stelle von `ziel`: erst das alte beiseite, dann das neue hin, dann das alte weg.

    Dieselbe Logik wie `icarus_memory.atomic.ordner_tauschen`; der Helfer läuft ohne das Paket, deshalb steht
    sie hier ein zweites Mal (ein Test prüft beide gegeneinander). Bricht etwas zwischen den beiden
    Umbenennungen ab, stellt der nächste Lauf die alte Fassung wieder her.
    """
    alt = ziel.with_name(f".{ziel.name}.alt")
    if alt.exists():
        if ziel.exists():
            shutil.rmtree(alt, ignore_errors=True)
        else:
            os.replace(alt, ziel)
    if ziel.exists():
        os.replace(ziel, alt)
    try:
        os.replace(neu, ziel)
    except BaseException:
        if alt.exists() and not ziel.exists():
            os.replace(alt, ziel)
        raise
    shutil.rmtree(alt, ignore_errors=True)


def akten_ablegen(folder: Path, archiv: bytes, name: str = AKTEN_ORDNERNAME) -> int:
    """Legt das ZIP der Akten als `folder/name` ab und gibt die Dateizahl zurück.

    Ersetzt wird nur ein vorhandener Ordner mit der Marke `.kingfisher-akten`; alles andere (fremde Dateien,
    ein Verweis, eine Datei gleichen Namens) bleibt unberührt und wird mit einem Satz abgelehnt. Das ZIP wird
    geprüft, bevor etwas geschrieben wird: keine absoluten oder aufwärts führenden Pfade, Größen begrenzt, die
    Marke muss dabei sein.
    """
    if not folder.is_dir() or folder.is_symlink():
        raise ValueError("Der Ordner ist nicht erreichbar.")
    ziel = folder / name
    if ziel.is_symlink() or (ziel.exists() and not (ziel.is_dir() and (ziel / AKTEN_MARKE).is_file())):
        raise ValueError(f"Im Ordner liegt schon „{name}“ mit anderem Inhalt. Bitte einen anderen Ordner wählen.")
    try:
        zf = zipfile.ZipFile(io.BytesIO(archiv))
    except zipfile.BadZipFile as exc:
        raise ValueError("Das Archiv der Akten ist beschädigt.") from exc
    with zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        namen = [i.filename for i in infos]
        if (len(infos) > AKTEN_MAX_DATEIEN or sum(i.file_size for i in infos) > AKTEN_MAX_GESAMT
                or any(i.file_size > AKTEN_MAX_DATEI for i in infos)):
            raise ValueError("Das Archiv der Akten ist zu groß.")
        for n in namen:
            teile = n.split("/")
            if "\\" in n or "\x00" in n or any(t in ("", ".", "..") for t in teile):
                raise ValueError("Das Archiv der Akten enthält einen unsicheren Pfad.")
        if AKTEN_MARKE not in namen:
            raise ValueError("Das Archiv der Akten ist unvollständig.")
        neu = Path(tempfile.mkdtemp(prefix=f".{name}.neu-", dir=folder))
        try:
            for i in infos:
                datei = neu.joinpath(*i.filename.split("/"))
                datei.parent.mkdir(parents=True, exist_ok=True)
                datei.write_bytes(zf.read(i))
            akten_ordner_tauschen(neu, ziel)
        except BaseException:
            shutil.rmtree(neu, ignore_errors=True)
            raise
    return len(infos)


def akten_spiegeln(api, folder: Path) -> dict:
    """Holt das Archiv, legt es ab und meldet dem Server Erfolg oder Grund (ein Satz, ohne Pfade)."""
    daten, kopf = api.bytes("/archiv")
    paket = next((wert for schluessel, wert in kopf.items() if schluessel.lower() == "x-akten-paket"), "")
    try:
        anzahl = akten_ablegen(folder, daten)
    except ValueError as exc:
        return api.call("/gespiegelt", {"paket": paket, "dateien": 0, "fehler": str(exc)[:280]})
    except OSError:
        return api.call("/gespiegelt", {"paket": paket, "dateien": 0,
                                        "fehler": "Der Ordner lässt sich nicht beschreiben. Bitte einen anderen wählen."})
    return api.call("/gespiegelt", {"paket": paket, "dateien": anzahl})


def akten_schritt(api, auswahl: Auswahl, waehle=waehle_akten_ordner) -> dict:
    """Ein Durchgang der Rolle `akten`: dem Server melden, dass der Helfer lebt, und auf Anfragen antworten.

    Der Server kann nur bitten, den Dialog zu zeigen; den Ordner bestimmt allein die Wahl am Mac. Nach dem
    Trennen (der Server kennt keinen Ordner mehr) vergisst der Helfer seinen gemerkten Ordner.
    """
    state = api.call("/worker", {})
    anfrage = state.get("pick_request")
    if anfrage:
        gewaehlt = waehle(anfrage.get("modus"))
        if gewaehlt is None:
            return api.call("/worker", {"cancelled": anfrage["id"]})
        auswahl.setzen(gewaehlt)
        return api.call("/worker", {"folder": str(gewaehlt), "picked": anfrage["id"]})
    if not state.get("ordner") and auswahl.folder is not None:
        auswahl.vergessen()
    return state


def main_akten(args, token) -> None:
    api = Api(args.url, token, '/api/v1/akten/export')
    auswahl = Auswahl(args.env_file.with_suffix('.akten.json'))
    lock = args.env_file.with_suffix('.akten.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    while True:
        try:
            state = akten_schritt(api, auswahl)
            # Nur in den Ordner schreiben, den der Server als den gewählten kennt: Wahl und Freigabe stimmen überein.
            if state.get('abholen') and auswahl.folder is not None and state.get('ordner') == str(auswahl.folder):
                akten_spiegeln(api, auswahl.folder)
        except (OSError, ValueError, StopSync):
            print('Akten-Ordner unterbrochen; erneuter Versuch folgt.', flush=True)
        time.sleep(5)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--role', choices=('dokumente', 'transkripte', 'akten'), default='dokumente')
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--env-file', required=True, type=Path)
    parser.add_argument('--url', default='http://127.0.0.1:8891')
    args = parser.parse_args()
    private = dict(line.split('=', 1) for line in args.env_file.read_text().splitlines()
                   if '=' in line and not line.startswith('#'))
    token = private.get('ICARUS_SIDECAR_TOKEN')
    if not token:
        parser.error('Lokale Kingfisher-Konfiguration fehlt.')
    if args.role == 'transkripte':
        return main_transkripte(args, token)
    if args.role == 'akten':
        return main_akten(args, token)
    if args.folder is None:
        parser.error('--folder fehlt.')
    folder = args.folder.expanduser().absolute()
    api = Api(args.url, token)
    lock = args.env_file.with_suffix('.folder.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return
    last_sync, generation, rid = 0, None, None
    while True:
        try:
            try:
                rid = root_id(folder)
            except (OSError, ValueError):
                if rid is None:
                    raise ValueError('Ordner nicht erreichbar.')
            state = api.call('/worker', {'root_id': rid, 'folder': str(folder)})
            if state['enabled'] and (state['generation'] != generation or time.monotonic() - last_sync >= 60):
                synchronize(api, folder, state)
                last_sync, generation = time.monotonic(), state['generation']
        except (OSError, ValueError, StopSync):
            print('Ordneraufnahme unterbrochen; erneuter Versuch folgt.', flush=True)
        time.sleep(5)


if __name__ == '__main__':
    main()
