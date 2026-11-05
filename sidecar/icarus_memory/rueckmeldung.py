"""Rückkanal für Fehler: die Ablage der Meldungen „Stimmt nicht?“.

Sagt Kingfisher im Alltag etwas Falsches oder Unvollständiges, meldet der Nutzer das
mit einem Klick unter der Antwort. Die Meldung hält fest, was gefragt, was geantwortet
und worauf sich die Antwort gestützt hat, dazu den Modellstand. Aus ihr wird später ein
Fall für die Messlatte (`rueckmeldung_faelle.py`), sonst ginge das Wissen der ersten
Woche verloren.

Was diese Ablage **nicht** tut: Sie schreibt nichts ins Gedächtnis, ändert keine Quelle,
keine Akte und keine Antwort und sendet nichts. Eine Meldung ist eine Notiz des Nutzers
an die Entwicklung. Ausdrücklich markierte Arbeitsweisen sind zusätzlich an den
Originalauftrag gebunden; workflow_learning darf daraus nur inaktive Vorschläge ableiten.
Fakten kommen weiterhin ausschließlich über Vorschlag und Annahme in den Bestand.

Eine eigene Datei, `rueckmeldungen.sqlite3` (Tabelle `rueckmeldung`, eigene Versionierung),
in der Sicherung wie `gespraeche.sqlite3`. Sie enthält Frage- und Antworttexte des Nutzers
und verlässt den Rechner nur in einer Sicherung, die der Nutzer selbst anlegt.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .migrations import IndexContract, Migration, run_migrations, verify_schema

ARTEN = ('falsch', 'unvollstaendig', 'veraltet', 'zu_langsam', 'sonstiges')
#: Wie die Art in der Oberfläche heißt (ein Klick, Alltagssprache).
ART_TEXTE = {'falsch': 'Falsch', 'unvollstaendig': 'Unvollständig', 'veraltet': 'Veraltet',
             'zu_langsam': 'Zu langsam', 'sonstiges': 'Etwas anderes'}
STATI = ('offen', 'erledigt')

MAX_FRAGE = 4000
MAX_ANTWORT = 20000
MAX_RICHTIG = 2000

_TABELLEN = {'rueckmeldung': {'id', 'erstellt', 'frage', 'antwort', 'struktur', 'art', 'richtig', 'belege', 'modell',
                              'status', 'erledigt_am', 'gespraech_id', 'nachricht_id'}}
_SCHLUESSEL = {'rueckmeldung': {'id'}}


def _indizes() -> dict[str, IndexContract]:
    return {'idx_rueckmeldung_nachricht': IndexContract('rueckmeldung', ('nachricht_id',), unique=True),
            'idx_rueckmeldung_status': IndexContract('rueckmeldung', ('status', 'erstellt'))}


def _migrieren(conn: sqlite3.Connection) -> None:
    conn.execute("""CREATE TABLE rueckmeldung (
        id TEXT PRIMARY KEY,
        erstellt REAL NOT NULL,
        frage TEXT NOT NULL,
        antwort TEXT NOT NULL,
        struktur TEXT NOT NULL DEFAULT '{}',
        art TEXT NOT NULL CHECK(art IN ('falsch','unvollstaendig','veraltet','zu_langsam','sonstiges')),
        richtig TEXT NOT NULL DEFAULT '',
        belege TEXT NOT NULL DEFAULT '[]',
        modell TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'offen' CHECK(status IN ('offen','erledigt')),
        erledigt_am REAL,
        gespraech_id TEXT NOT NULL DEFAULT '',
        nachricht_id TEXT NOT NULL)""")
    conn.execute('CREATE UNIQUE INDEX idx_rueckmeldung_nachricht ON rueckmeldung(nachricht_id)')
    conn.execute('CREATE INDEX idx_rueckmeldung_status ON rueckmeldung(status, erstellt)')


def _pruefen(conn: sqlite3.Connection) -> None:
    verify_schema(conn, expected_tables=_TABELLEN, expected_primary_keys=_SCHLUESSEL, expected_indexes=_indizes())


_WORKFLOW_TABLES = {**_TABELLEN, 'rueckmeldung': _TABELLEN['rueckmeldung'] | {'workflow'},
                   'workflow_checks': {'request_key', 'result'}}


def _workflow_migration(conn):
    conn.execute("ALTER TABLE rueckmeldung ADD COLUMN workflow TEXT NOT NULL DEFAULT '{}'")
    conn.execute('CREATE TABLE workflow_checks (request_key TEXT PRIMARY KEY, result TEXT NOT NULL)')


def _workflow_verify(conn):
    verify_schema(conn, expected_tables=_WORKFLOW_TABLES,
        expected_primary_keys={**_SCHLUESSEL, 'workflow_checks': {'request_key'}}, expected_indexes=_indizes())


_MIGRATIONS = (Migration(1, 'rueckmeldung', _migrieren, _pruefen),
               Migration(2, 'workflow_corrections', _workflow_migration, _workflow_verify))


class RueckmeldungFehler(ValueError):
    """Eine Meldung ist unbrauchbar (unbekannte Art, leere Frage); mit lesbarem Grund."""


def _iso(zeit: float | None) -> str:
    return datetime.fromtimestamp(zeit, timezone.utc).isoformat(timespec='seconds') if zeit else ''


def _lesen(row: sqlite3.Row) -> dict[str, Any]:
    return {'id': row['id'], 'erstellt': _iso(row['erstellt']), 'frage': row['frage'], 'antwort': row['antwort'],
            'struktur': json.loads(row['struktur']), 'art': row['art'], 'art_text': ART_TEXTE[row['art']],
            'richtig': row['richtig'], 'belege': json.loads(row['belege']), 'modell': json.loads(row['modell']),
            'status': row['status'], 'erledigt_am': _iso(row['erledigt_am']),
            'gespraech_id': row['gespraech_id'], 'nachricht_id': row['nachricht_id'],
            'workflow': json.loads(row['workflow']) if 'workflow' in row.keys() else {}}


class Rueckmeldungen:
    """Die Ablage der Meldungen (eigene Datei, eigene Versionierung)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            run_migrations(self._conn, store='rueckmeldungen', path=self._path, migrations=_MIGRATIONS)
        except Exception:
            self._conn.close()
            raise

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def melden(self, *, frage: str, antwort: str, art: str, nachricht_id: str, gespraech_id: str = '',
               richtig: str = '', struktur: dict[str, Any] | None = None, belege: list[str] | None = None,
               modell: dict[str, Any] | None = None, workflow: dict | None = None) -> dict[str, Any]:
        """Legt eine Meldung an. Meldet man dieselbe Antwort noch einmal, ersetzt das Neue das Alte und macht sie wieder offen."""
        if art not in ARTEN:
            raise RueckmeldungFehler('Unbekannte Art der Meldung.')
        frage, antwort, richtig = frage.strip(), antwort.strip(), richtig.strip()
        if not frage or not nachricht_id:
            raise RueckmeldungFehler('Zu einer Meldung gehören die Frage und die Antwort, um die es geht.')
        kennung = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO rueckmeldung(id,erstellt,frage,antwort,struktur,art,richtig,belege,modell,status,"
                "erledigt_am,gespraech_id,nachricht_id,workflow) VALUES (?,?,?,?,?,?,?,?,?,'offen',NULL,?,?,?) "
                "ON CONFLICT(nachricht_id) DO UPDATE SET art=excluded.art, richtig=excluded.richtig, "
                "erstellt=excluded.erstellt, status='offen', erledigt_am=NULL, workflow=excluded.workflow",
                (kennung, time.time(), frage[:MAX_FRAGE], antwort[:MAX_ANTWORT],
                 json.dumps(struktur or {}, ensure_ascii=False), art, richtig[:MAX_RICHTIG],
                 json.dumps(sorted(set(belege or [])), ensure_ascii=False),
                 json.dumps(modell or {}, ensure_ascii=False), gespraech_id, nachricht_id,
                 json.dumps(workflow or {}, ensure_ascii=False)))
            self._conn.commit()
            row = self._conn.execute('SELECT * FROM rueckmeldung WHERE nachricht_id = ?', (nachricht_id,)).fetchone()
        return _lesen(row)

    def workflow_candidates(self, area: str) -> list[dict]:
        """Begrenztes Fenster eigener Arbeitskorrekturen; kein Durchlauf durch alle Notizen."""
        with self._lock:
            rows = self._conn.execute("SELECT * FROM rueckmeldung WHERE json_extract(workflow, '$.area')=? "
                'ORDER BY erstellt DESC, id LIMIT 32', (area,)).fetchall()
        return [_lesen(row) for row in rows]

    def for_conversation(self, conversation_id: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute('SELECT * FROM rueckmeldung WHERE gespraech_id=?', (conversation_id,)).fetchall()
        return [_lesen(row) for row in rows]

    def withdraw_workflow(self, identifier: str) -> bool:
        with self._lock, self._conn:
            return self._conn.execute("UPDATE rueckmeldung SET workflow='{}' WHERE id=?", (identifier,)).rowcount == 1

    def workflow_result(self, key: str) -> dict | None:
        with self._lock:
            row = self._conn.execute('SELECT result FROM workflow_checks WHERE request_key=?', (key,)).fetchone()
        return json.loads(row['result']) if row else None

    def save_workflow_result(self, key: str, result: dict) -> None:
        with self._lock, self._conn:
            self._conn.execute('INSERT OR REPLACE INTO workflow_checks VALUES (?,?)',
                (key, json.dumps(result, ensure_ascii=False)))

    def liste(self, *, status: str | None = None) -> list[dict[str, Any]]:
        """Alle Meldungen, neueste zuerst; optional nur `offen` oder `erledigt`."""
        with self._lock:
            if status is None:
                rows = self._conn.execute('SELECT * FROM rueckmeldung ORDER BY erstellt DESC, id').fetchall()
            else:
                rows = self._conn.execute('SELECT * FROM rueckmeldung WHERE status = ? ORDER BY erstellt DESC, id',
                                          (status,)).fetchall()
        return [_lesen(row) for row in rows]

    def zaehlen(self) -> dict[str, int]:
        with self._lock:
            offen = self._conn.execute("SELECT COUNT(*) FROM rueckmeldung WHERE status = 'offen'").fetchone()[0]
            gesamt = self._conn.execute('SELECT COUNT(*) FROM rueckmeldung').fetchone()[0]
        return {'gesamt': gesamt, 'offen': offen, 'erledigt': gesamt - offen}

    def hole(self, kennung: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute('SELECT * FROM rueckmeldung WHERE id = ?', (kennung,)).fetchone()
        return _lesen(row) if row else None

    def erledigt(self, kennung: str) -> dict[str, Any] | None:
        """Setzt „erledigt“. Die Meldung bleibt stehen: Sie ist der Fall in der Exportdatei, der Regressionstest."""
        with self._lock:
            self._conn.execute("UPDATE rueckmeldung SET status = 'erledigt', "
                               "erledigt_am = COALESCE(erledigt_am, ?) WHERE id = ?", (time.time(), kennung))
            self._conn.commit()
        return self.hole(kennung)

    @classmethod
    def nur_lesen(cls, path: str | Path) -> list[dict[str, Any]]:
        """Liest eine Datei `rueckmeldungen.sqlite3` ohne sie zu verändern (für den Export ohne laufende Instanz)."""
        verbindung = sqlite3.connect(f'{Path(path).resolve().as_uri()}?mode=ro', uri=True)
        verbindung.row_factory = sqlite3.Row
        try:
            return [_lesen(row) for row in verbindung.execute('SELECT * FROM rueckmeldung ORDER BY erstellt, id')]
        except sqlite3.Error as fehler:
            raise RueckmeldungFehler(f'{path}: keine Datei mit Rückmeldungen ({fehler}).') from None
        finally:
            verbindung.close()
