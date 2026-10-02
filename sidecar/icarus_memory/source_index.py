"""Dauerhafter Suchindex über die Rohtexte aller verwendbaren Quellen.

Aufgabe dieses Moduls: zu einer Frage die Quellen (Episoden-IDs) nennen, in
denen ihre Wörter vorkommen, geordnet nach BM25. Es kennt weder Arbeitsgedächtnis
noch Antwortkontext; der Aufrufer prüft jede genannte Quelle vor der Verwendung
erneut (Belegprüfung, Frischeprüfung).

Warum Trigramme statt ganzer Wörter: Deutsche Komposita. „Stromrechnung“ und
„Rechnung Strom“ teilen kein Wort, aber die Zeichenfolge. FTS5 mit dem Tokenizer
``trigram`` findet jede Zeichenfolge von mindestens drei Zeichen mitten im Text.
Damit die Gegenrichtung (Frage „Stromrechnung“, Quelle „Rechnung Strom“) auch
trägt, werden Wörter der Frage mit Hilfe des Index selbst zerlegt: Ein Wort wird
nur dort geteilt, wo beide Teile im Bestand vorkommen.

Was im Index steht: Titel, Beteiligte und Text (nur gefaltet: Kleinschreibung,
ohne Akzente, ß als ss, Leerraum vereinheitlicht). Nichts davon ist eine Quelle
der Wahrheit; der Originaltext bleibt in ``episodes``. Der Index ist jederzeit
aus ``episodes`` neu aufbaubar (``neu_aufbauen``).

Verwendbar ist, was ``EpisodeStore`` als aktuelle, nicht ausgeschlossene
Quelle kennt: Art Nachricht/Dokument/Termin, nicht ignoriert, nicht durch eine
neuere Fassung ersetzt, kein Gesprächsnachschlag. Zwei Sicherungen, die sich nicht
aufeinander verlassen:

1. Pflege an den Zustandswechseln: ``synchronisieren`` nimmt eine Quelle auf oder
   entfernt sie, je nachdem, was ``episodes`` jetzt sagt.
2. Prüfung beim Lesen: ``suchen`` gibt nur Quellen zurück, die die Tabelle
   ``episodes`` in diesem Augenblick als verwendbar ausweist. Ein veralteter
   Indexeintrag kann also nie eine Quelle zurückbringen (fail-closed).

Nichts wird still begrenzt: Was der Index nicht enthalten kann (zu großer Text),
steht in ``source_index_skipped`` und wird von ``abdeckung`` und ``suchen``
gezählt; ein abgeschnittenes Ergebnis nennt die Gesamtzahl der Treffer.

Zwei Stufen (Migration 15, Einstellung ``suchindex.wortteile_jahre``): Der
Trigramm-Index ist etwa fünfmal so groß wie der Text. Wer Platz sparen will, lässt
ihn nur für die letzten N Jahre Wortteile führen; ältere Quellen stehen dann in
einem zweiten, wortbasierten Index (``source_index_woerter``, Tokenizer
``unicode61``, ganze Wörter und Wortanfänge). Jede Quelle steht in genau einem der
beiden (``source_index_docs.wortteile``); ``suchen`` fragt beide und vereint die
Treffer nach BM25-Punkten. Bei 0 (Vorgabe) stehen alle Quellen im Trigramm-Index und der
zweite bleibt leer. Der Stichtag wandert mit der Zeit: ``abgleichen`` stuft
Quellen um, die inzwischen zu alt sind.

Vertrag Version 1: Eine Änderung der Faltung oder des Tokenizers verlangt einen
Neuaufbau (neue Migration).
"""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from datetime import datetime

from .lexical import terms_v1
from .migrations import _normalized_sql
from .model import now

# Arten, die der Index aufnimmt. Zusammenfassungen und Beobachtungen sind nie
# Quelle; Gesprächsnachschläge (Tag) sind es auch nicht.
ARTEN = ("message", "document", "event")
CHAT_LOOKUP_TAG = "conversation:memory-lookup"
# Größere Quellen bleiben draußen und werden gezählt, nie still übergangen.
MAX_TEXT_BYTES = 512 * 1024
MAX_DOKUMENT_BYTES = 768 * 1024
MAX_WOERTER = 16
GEWICHTE = (4.0, 2.0, 1.0)  # Titel, Beteiligte, Text
_MIN_ZERLEGUNG = 4  # kürzester Teil eines zerlegten Worts
_MIN_ZERLEGT = 8  # kürzestes Wort, das zerlegt wird
_MAX_PROBEN = 120  # Obergrenze der Vorkommensprüfungen je Frage

# Funktionswörter, die in Fragen vorkommen und nichts unterscheiden. Nur für
# diesen Index; ``lexical.terms_v1`` bleibt unverändert (versionierter Vertrag).
FUNKTIONSWOERTER = frozenset("""
wann wer wie wo warum wozu wieso weshalb welche welcher welchen welches welchem
wieviel wieviele viel viele wem wen wessen womit worauf woran wofür wovon
muss musst müssen musste soll sollen sollte kann können konnte darf dürfen will wollen
haben hatte hatten habe hast gibt gab geben eigentlich los mal noch schon nur sehr
bitte nach beim vom ins bei aus für fuer über ueber unter gegen ohne bis seit
während wegen und oder aber auch nicht kein keine keinen keiner keinem einen einem
eines einer eine dann dort hier damit dazu dafür darüber ist sind war waren wird
werden wurde wurden worden sei ich mir mich mein meine meinen meiner meines meinem
dein deine unser unsere unseren unserer unserem ihre ihren ihrer ihrem man jemand
jemandem jemanden etwas alles alle allen allem wieder immer denn doch also sowie
dass daß weil wenn ob als wie wohl gern gerne ganz nun jetzt
""".split())

_KOMBINIEREND = re.compile("[\u0300-\u036f]")  # kombinierende Akzentzeichen

TABLES = {
    "source_index": {"title", "people", "body"},
    "source_index_data": {"id", "block"},
    "source_index_idx": {"segid", "term", "pgno"},
    "source_index_content": {"id", "c0", "c1", "c2"},
    "source_index_docsize": {"id", "sz"},
    "source_index_config": {"k", "v"},
    "source_index_docs": {"doc", "episode_id", "kind"},
    "source_index_skipped": {"episode_id", "reason"},
}
PRIMARY_KEYS = {
    "source_index": set(),
    "source_index_data": {"id"},
    "source_index_idx": {"segid", "term"},
    "source_index_content": {"id"},
    "source_index_docsize": {"id"},
    "source_index_config": {"k"},
    "source_index_docs": {"doc"},
    "source_index_skipped": {"episode_id"},
}
INDEXES: dict = {}

# Migration 15: der zweite, wortbasierte Index und die Einstellung.
WOERTER_TABLES = {
    "source_index_woerter": {"title", "people", "body"},
    "source_index_woerter_data": {"id", "block"},
    "source_index_woerter_idx": {"segid", "term", "pgno"},
    "source_index_woerter_content": {"id", "c0", "c1", "c2"},
    "source_index_woerter_docsize": {"id", "sz"},
    "source_index_woerter_config": {"k", "v"},
    "source_index_meta": {"schluessel", "wert"},
}
WOERTER_PRIMARY_KEYS = {
    "source_index_woerter": set(),
    "source_index_woerter_data": {"id"},
    "source_index_woerter_idx": {"segid", "term"},
    "source_index_woerter_content": {"id"},
    "source_index_woerter_docsize": {"id"},
    "source_index_woerter_config": {"k"},
    "source_index_meta": {"schluessel"},
}


def tabellen(neu: bool = True) -> tuple[dict, dict]:
    """Tabellen und Primärschlüssel für die Schemaprüfung; ``neu=False`` ist der Stand von Migration 12 bis 14."""
    if not neu:
        return dict(TABLES), dict(PRIMARY_KEYS)
    return ({**TABLES, "source_index_docs": TABLES["source_index_docs"] | {"wortteile"}, **WOERTER_TABLES},
            {**PRIMARY_KEYS, **WOERTER_PRIMARY_KEYS})


_FTS = ("CREATE VIRTUAL TABLE source_index USING fts5("
        "title, people, body, tokenize='trigram')")
_SCHATTEN = {
    "source_index_data": "CREATE TABLE 'source_index_data'(id INTEGER PRIMARY KEY, block BLOB)",
    "source_index_idx": "CREATE TABLE 'source_index_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID",
    "source_index_content": "CREATE TABLE 'source_index_content'(id INTEGER PRIMARY KEY, c0, c1, c2)",
    "source_index_docsize": "CREATE TABLE 'source_index_docsize'(id INTEGER PRIMARY KEY, sz BLOB)",
    "source_index_config": "CREATE TABLE 'source_index_config'(k PRIMARY KEY, v) WITHOUT ROWID",
}
_DOCS = ("CREATE TABLE source_index_docs (doc INTEGER PRIMARY KEY, "
         "episode_id TEXT NOT NULL UNIQUE, kind TEXT NOT NULL)")
_SKIPPED = ("CREATE TABLE source_index_skipped (episode_id TEXT PRIMARY KEY, "
            "reason TEXT NOT NULL)")
_DOCS_SPALTE = "wortteile INTEGER NOT NULL DEFAULT 1"
_FTS_WOERTER = ("CREATE VIRTUAL TABLE source_index_woerter USING fts5("
                "title, people, body, tokenize='unicode61')")
_SCHATTEN_WOERTER = {
    name.replace("source_index", "source_index_woerter", 1): sql.replace("source_index", "source_index_woerter")
    for name, sql in _SCHATTEN.items()
}
_META = "CREATE TABLE source_index_meta (schluessel TEXT PRIMARY KEY, wert TEXT NOT NULL)"
_JAHRE = "wortteile_jahre"



def _verwendbar() -> str:
    """Was „verwendbar“ heißt: die geltende Quelle, an genau einer Stelle (`episodes.sql_geltend`).

    ``e`` ist die Tabelle episodes. Erst zur Aufrufzeit importiert: `episodes` importiert
    dieses Modul, ein Import auf Modulebene wäre zirkulär. `ARTEN` bleibt deshalb
    eine benannte Kopie der Rohquellenarten; `test_source_index` prüft die Gleichheit.
    """
    from .episodes import sql_geltend
    return sql_geltend('e')


_OHNE_NACHSCHLAG = (
    "NOT EXISTS (SELECT 1 FROM json_each(e.document, '$.tags') AS tag "
    "WHERE tag.value = '" + CHAT_LOOKUP_TAG + "')"
)


# -- Faltung ---------------------------------------------------------------

def falte(text: str) -> str:
    """Text für Index und Frage gleich falten: klein, ohne Akzente, ß = ss."""
    text = text.casefold()
    if not text.isascii():
        text = _KOMBINIEREND.sub("", unicodedata.normalize("NFKD", text))
    return " ".join(text.split())


# -- Schema ----------------------------------------------------------------

def install(connection: sqlite3.Connection) -> int:
    """Migration: Tabellen anlegen und alle verwendbaren Quellen aufnehmen."""
    connection.execute(_DOCS)
    connection.execute(_SKIPPED)
    try:
        connection.execute(_FTS)
    except sqlite3.OperationalError as exc:
        raise sqlite3.DatabaseError(
            "Der Suchindex braucht SQLite ab Version 3.34 mit FTS5 (Tokenizer trigram); "
            f"vorhanden ist {sqlite3.sqlite_version}: {exc}") from exc
    return neu_aufbauen(connection)


def migrate_woerter(connection: sqlite3.Connection) -> None:
    """Migration 15: zweiter Index für ältere Quellen und die Ablage der Einstellung.

    Ändert keine Zeile: Alle Quellen bleiben im Trigramm-Index (Einstellung 0).
    """
    connection.execute(f"ALTER TABLE source_index_docs ADD COLUMN {_DOCS_SPALTE}")
    connection.execute(_META)
    try:
        connection.execute(_FTS_WOERTER)
    except sqlite3.OperationalError as exc:
        raise sqlite3.DatabaseError(f"Der Wortindex braucht SQLite mit FTS5 (Tokenizer unicode61): {exc}") from exc


def verify(connection: sqlite3.Connection, *, woerter: bool = True) -> None:
    """Start-Prüfung des Schemas; die Zeilen prüft ``abgleichen``. ``woerter=False``: Stand von Migration 12 bis 14."""
    docs = _DOCS[:-1] + ", " + _DOCS_SPALTE + ")" if woerter else _DOCS
    erwartet = {"source_index": _FTS, "source_index_docs": docs,
                "source_index_skipped": _SKIPPED, **_SCHATTEN}
    if woerter:
        erwartet.update({"source_index_woerter": _FTS_WOERTER, "source_index_meta": _META, **_SCHATTEN_WOERTER})
    for name, sql in erwartet.items():
        row = connection.execute("SELECT sql FROM sqlite_schema WHERE name=?", (name,)).fetchone()
        if row is None or _normalized_sql(row[0]) != _normalized_sql(sql):
            raise sqlite3.DatabaseError(f"Suchindex: Schema von {name} weicht ab")
    for tabelle, spalten in tabellen(woerter)[0].items():
        rows = connection.execute(f'PRAGMA table_info("{tabelle}")').fetchall()
        if {row[1] for row in rows} != spalten:
            raise sqlite3.DatabaseError(f"Suchindex: Spalten von {tabelle} weichen ab")


def neu_aufbauen(connection: sqlite3.Connection) -> int:
    """Index leeren und aus ``episodes`` vollständig neu füllen. Gibt die Zahl der Quellen zurück."""
    connection.execute("DELETE FROM source_index")
    if _hat_woerter(connection):
        connection.execute("DELETE FROM source_index_woerter")
    connection.execute("DELETE FROM source_index_docs")
    connection.execute("DELETE FROM source_index_skipped")
    return _nachziehen(connection, alle=True)


# -- Einstellung: Wortteile für die letzten N Jahre --------------------------

def _hat_woerter(connection: sqlite3.Connection) -> bool:
    """Ob das Schema schon den zweiten Index kennt (während der Migrationen 12 bis 14 nicht)."""
    return connection.execute("SELECT 1 FROM sqlite_schema WHERE name='source_index_woerter'").fetchone() is not None


def wortteile_jahre(connection: sqlite3.Connection) -> int:
    """Wie viele Jahre zurück Quellen Wortteile im Index haben; 0 heißt alle (Vorgabe)."""
    try:
        row = connection.execute("SELECT wert FROM source_index_meta WHERE schluessel=?", (_JAHRE,)).fetchone()
    except sqlite3.OperationalError:  # Schema vor Migration 15
        return 0
    return int(row[0]) if row else 0


def einstellen(connection: sqlite3.Connection, jahre: int) -> bool:
    """Die Einstellung ablegen (der Aufrufer stuft danach um, ``umstufen``). Gibt an, ob sie sich änderte."""
    if type(jahre) is not int or not 0 <= jahre <= 100:
        raise ValueError("Die Zahl der Jahre muss eine ganze Zahl von 0 bis 100 sein.")
    if wortteile_jahre(connection) == jahre:
        return False
    connection.execute("INSERT INTO source_index_meta VALUES (?, ?) ON CONFLICT(schluessel) DO UPDATE SET wert=excluded.wert",
                       (_JAHRE, str(jahre)))
    return True


def _vor_jahren(zeitpunkt: datetime, jahre: int) -> datetime:
    try:
        return zeitpunkt.replace(year=zeitpunkt.year - jahre)
    except ValueError:  # 29. Februar
        return zeitpunkt.replace(year=zeitpunkt.year - jahre, day=28)


def _grenze(connection: sqlite3.Connection) -> float | None:
    """Julianischer Tag, ab dem eine Quelle Wortteile bekommt; ``None``, wenn alle sie bekommen."""
    jahre = wortteile_jahre(connection)
    if jahre <= 0:
        return None
    return connection.execute("SELECT julianday(?)", (_vor_jahren(now(), jahre).isoformat(),)).fetchone()[0]


# -- Pflege ----------------------------------------------------------------

_ZEILE = ("SELECT e.id, e.kind, e.title, e.body, "
          "COALESCE(json_extract(e.document, '$.participants'), '[]') AS people, e.rowid, "
          "length(CAST(e.body AS BLOB)), length(CAST(e.document AS BLOB)), "
          "julianday(COALESCE(e.occurred_at, e.recorded_at)) "
          "FROM episodes e WHERE ")


def _einfuegen(connection: sqlite3.Connection, row, grenze: float | None = None) -> str:
    """Eine verwendbare Quelle aufnehmen (oder als zu groß vermerken).

    ``grenze`` (``_grenze``): Ältere Quellen kommen nur in den Wortindex.
    """
    episode_id, art, titel, text, beteiligte = row[0], row[1], row[2], row[3], row[4]
    if row[6] > MAX_TEXT_BYTES or row[7] > MAX_DOKUMENT_BYTES:
        connection.execute("INSERT OR REPLACE INTO source_index_skipped VALUES (?, 'zu_gross')", (episode_id,))
        return "zu_gross"
    connection.execute("DELETE FROM source_index_skipped WHERE episode_id=?", (episode_id,))
    wortteile = _mit_wortteilen(row[8], grenze)
    if wortteile:
        cursor = connection.execute("INSERT INTO source_index_docs(episode_id, kind) VALUES (?, ?)", (episode_id, art))
    else:
        cursor = connection.execute("INSERT INTO source_index_docs(episode_id, kind, wortteile) VALUES (?, ?, 0)",
                                    (episode_id, art))
    people = " ".join(_beteiligte(beteiligte))
    # Leerzeichen an beiden Enden machen Wortanfang und Wortende prüfbar (Phrase „ strom“).
    connection.execute(f"INSERT INTO {_tabelle(wortteile)}(rowid, title, people, body) VALUES (?, ?, ?, ?)",
                       (cursor.lastrowid, f" {falte(titel)} ", f" {falte(people)} ", f" {falte(text)} "))
    return "aufgenommen"


def _mit_wortteilen(zeit: float | None, grenze: float | None) -> bool:
    """Ob die Quelle in den Trigramm-Index gehört: ohne Grenze immer, sonst wenn sie jung genug ist (oder undatiert)."""
    return grenze is None or zeit is None or zeit >= grenze


def _tabelle(wortteile: bool) -> str:
    return "source_index" if wortteile else "source_index_woerter"


def _beteiligte(wert) -> list[str]:
    try:
        liste = json.loads(wert) if isinstance(wert, str) else []
    except ValueError:
        return []
    return [eintrag for eintrag in liste if isinstance(eintrag, str)] if isinstance(liste, list) else []


def entfernen(connection: sqlite3.Connection, episode_id: str) -> bool:
    """Eine Quelle aus dem Index nehmen. Gibt an, ob etwas entfernt wurde."""
    row = connection.execute("SELECT doc, wortteile FROM source_index_docs WHERE episode_id=?", (episode_id,)).fetchone()
    vermerkt = connection.execute("DELETE FROM source_index_skipped WHERE episode_id=?", (episode_id,)).rowcount
    if row is None:
        return bool(vermerkt)
    connection.execute(f"DELETE FROM {_tabelle(bool(row[1]))} WHERE rowid=?", (row[0],))
    connection.execute("DELETE FROM source_index_docs WHERE doc=?", (row[0],))
    return True


def synchronisieren(connection: sqlite3.Connection, episode_id: str, *, neu: bool = False) -> str:
    """Den Indexstand einer Quelle an ``episodes`` angleichen.

    Idempotent und zustandslos: Es zählt nur, was ``episodes`` jetzt sagt. Wer
    einen Zustandswechsel vornimmt (aufnehmen, ignorieren, wieder öffnen, durch
    eine neuere Fassung ersetzen, löschen), ruft dies danach in derselben
    Transaktion auf. ``neu`` erzwingt erneutes Einlesen (geänderte Beteiligte).
    Rückgabe: ``aufgenommen``, ``zu_gross``, ``entfernt`` oder ``unveraendert``.
    """
    row = connection.execute(_ZEILE + "e.id=? AND " + _verwendbar() + " AND " + _OHNE_NACHSCHLAG,
                             (episode_id,)).fetchone()
    if row is None:
        return "entfernt" if entfernen(connection, episode_id) else "unveraendert"
    zu_gross = row[6] > MAX_TEXT_BYTES or row[7] > MAX_DOKUMENT_BYTES
    if (not neu and not zu_gross
            and connection.execute("SELECT 1 FROM source_index_docs WHERE episode_id=?", (episode_id,)).fetchone()):
        return "unveraendert"
    entfernen(connection, episode_id)
    return _einfuegen(connection, row, _grenze(connection))


def _nachziehen(connection: sqlite3.Connection, *, alle: bool = False, grenze: int | None = None) -> int:
    """Verwendbare, noch nicht aufgenommene Quellen aufnehmen (alle oder höchstens ``grenze``).

    Seitenweise nach ``rowid``: Es wird nie in eine Tabelle geschrieben, aus der
    dieselbe Abfrage gerade liest.
    """
    # Billige Bedingungen zuerst: Das Tag-Prüfen liest das Dokument.
    bedingung = _verwendbar()
    if not alle:
        bedingung += (" AND NOT EXISTS (SELECT 1 FROM source_index_docs d WHERE d.episode_id=e.id)"
                      " AND NOT EXISTS (SELECT 1 FROM source_index_skipped s WHERE s.episode_id=e.id)")
    bedingung += " AND " + _OHNE_NACHSCHLAG
    stufe = _grenze(connection)
    zaehler, nach = 0, -1
    while grenze is None or zaehler < grenze:
        seite = 500 if grenze is None else min(500, grenze - zaehler)
        rows = connection.execute(_ZEILE + "e.rowid > ? AND " + bedingung + " ORDER BY e.rowid LIMIT ?",
                                  (nach, seite)).fetchall()
        if not rows:
            break
        for row in rows:
            _einfuegen(connection, row, stufe)
        zaehler += len(rows)
        nach = rows[-1][5]
    return zaehler


def verdichten(connection: sqlite3.Connection) -> None:
    """Die Indizes zusammenführen (FTS5 „optimize“).

    Gelöschte Quellen geben ihren Platz in einem FTS5-Index erst beim Zusammenführen frei; ohne diesen
    Schritt wüchse die Datei nach einem Umbau sogar. Der freie Platz geht danach an das Dateisystem zurück
    (`EpisodeStore._platz_zurueckgeben`).
    """
    for tabelle in ("source_index", "source_index_woerter"):
        connection.execute(f"INSERT INTO {tabelle}({tabelle}) VALUES('optimize')")


@dataclass(frozen=True)
class Abgleich:
    """Ergebnis von ``abgleichen``: was gefehlt hat und was zu viel war."""
    nachgezogen: int = 0
    entfernt: int = 0
    offen: int = 0  # bleibt für den nächsten Lauf übrig (Grenze erreicht)
    umgestuft: int = 0  # in den anderen Index verschoben (zu alt geworden oder Einstellung geändert)


def _abweichungen(connection: sqlite3.Connection, grenze: int):
    """Nur lesend: Einträge zu Quellen, die nicht mehr verwendbar sind, und ob Quellen fehlen."""
    zuviel = [row[0] for row in connection.execute(
        "SELECT d.episode_id FROM source_index_docs d LEFT JOIN episodes e ON e.id=d.episode_id "
        "WHERE e.id IS NULL OR NOT (" + _verwendbar() + ") LIMIT ?", (grenze + 1,))]
    fehlt = connection.execute(
        "SELECT 1 FROM episodes e WHERE " + _verwendbar() +
        " AND NOT EXISTS (SELECT 1 FROM source_index_docs d WHERE d.episode_id=e.id)"
        " AND NOT EXISTS (SELECT 1 FROM source_index_skipped s WHERE s.episode_id=e.id)"
        " AND " + _OHNE_NACHSCHLAG + " LIMIT 1").fetchone() is not None
    return zuviel, fehlt


def _falsch_gestuft(connection: sqlite3.Connection, grenze: int) -> list[str]:
    """Quellen (höchstens ``grenze``), die im anderen Index stehen müssten: zu alt geworden oder Einstellung geändert."""
    stufe = _grenze(connection)
    if stufe is None:  # alle mit Wortteilen: nichts darf im Wortindex stehen
        rows = connection.execute("SELECT episode_id FROM source_index_docs WHERE wortteile=0 LIMIT ?", (grenze,))
    else:
        rows = connection.execute(
            "SELECT d.episode_id FROM source_index_docs d JOIN episodes e ON e.id=d.episode_id "
            "WHERE (d.wortteile=1 AND julianday(COALESCE(e.occurred_at, e.recorded_at)) < ?) "
            "OR (d.wortteile=0 AND (julianday(COALESCE(e.occurred_at, e.recorded_at)) >= ? "
            "OR julianday(COALESCE(e.occurred_at, e.recorded_at)) IS NULL)) LIMIT ?", (stufe, stufe, grenze))
    return [row[0] for row in rows]


def umstufen(connection: sqlite3.Connection, *, grenze: int = 500) -> int:
    """Höchstens ``grenze`` Quellen in den Index verschieben, in den sie jetzt gehören. Gibt die Zahl zurück.

    Eine Quelle steht dabei nie in keinem Index: Aus dem einen wird sie in derselben
    Transaktion entfernt, in den anderen aufgenommen. Das Ergebnis nach dem letzten
    Aufruf ist dasselbe wie nach ``neu_aufbauen``, nur ohne alles neu zu lesen.
    """
    ids = _falsch_gestuft(connection, grenze)
    for episode_id in ids:
        synchronisieren(connection, episode_id, neu=True)
    return len(ids)


def stimmt(connection: sqlite3.Connection) -> bool:
    """Ob Index und ``episodes`` übereinstimmen (nur lesend, ohne Schreibsperre)."""
    zuviel, fehlt = _abweichungen(connection, 0)
    return not zuviel and not fehlt and not _falsch_gestuft(connection, 1)


def abgleichen(connection: sqlite3.Connection, *, grenze: int = 2000) -> Abgleich:
    """Index und ``episodes`` in Einklang bringen, höchstens ``grenze`` Änderungen je Lauf.

    Fängt ab, was eine Pflege am Zustandswechsel verfehlt hat (Absturz zwischen
    zwei Schritten, Änderung an ``episodes`` von außen). Beim Lesen schützt
    ``suchen`` ohnehin; dieser Abgleich hält den Index klein und vollständig.
    Schreibt der Aufrufer nicht ohnehin, prüft er vorher mit ``stimmt``, um keine
    Schreibsperre ohne Not zu nehmen.
    """
    zuviel, _ = _abweichungen(connection, grenze)
    entfernt = 0
    for episode_id in zuviel[:grenze]:
        entfernt += entfernen(connection, episode_id)
    nachgezogen = _nachziehen(connection, grenze=max(0, grenze - entfernt))
    umgestuft = umstufen(connection, grenze=max(0, grenze - entfernt - nachgezogen))
    _, fehlt = _abweichungen(connection, 0)
    offen = max(0, len(zuviel) - grenze) + (1 if fehlt else 0) + (1 if _falsch_gestuft(connection, 1) else 0)
    return Abgleich(nachgezogen, entfernt, offen, umgestuft)


def _zu_gross(connection: sqlite3.Connection) -> int:
    """Verwendbare Quellen, die wegen ihrer Größe nicht im Index stehen."""
    ids = [row[0] for row in connection.execute("SELECT episode_id FROM source_index_skipped")]
    return len(_verwendbare(connection, ids))


def abdeckung(connection: sqlite3.Connection) -> dict:
    """Wie vollständig der Index ist: aufgenommene Quellen und Quellen, die zu groß dafür sind."""
    aufgenommen = connection.execute("SELECT count(*) FROM source_index_docs").fetchone()[0]
    return {"aufgenommen": aufgenommen, "zu_gross": _zu_gross(connection)}


def verteilung(connection: sqlite3.Connection) -> dict:
    """Wie sich die aufgenommenen Quellen auf die beiden Indizes verteilen."""
    mit_wortteilen = connection.execute("SELECT count(*) FROM source_index_docs WHERE wortteile=1").fetchone()[0]
    nur_woerter = connection.execute("SELECT count(*) FROM source_index_docs WHERE wortteile=0").fetchone()[0]
    return {"mit_wortteilen": mit_wortteilen, "nur_woerter": nur_woerter}


def groesse(connection: sqlite3.Connection) -> int | None:
    """Belegter Platz aller Tabellen des Suchindex in Bytes; ``None``, wenn diese SQLite ihn nicht nennen kann."""
    try:
        return connection.execute(
            "SELECT coalesce(sum(pgsize), 0) FROM dbstat WHERE name LIKE 'source\\_index%' ESCAPE '\\'").fetchone()[0]
    except sqlite3.OperationalError:
        return None


# -- Suche -----------------------------------------------------------------

@dataclass(frozen=True)
class Suchergebnis:
    """Treffer in Rangfolge und alles, was der Aufrufer über Grenzen wissen muss."""
    episoden: tuple[str, ...] = ()
    woerter: tuple[str, ...] = ()  # gesucht (gefaltet, ohne Funktionswörter)
    zusatz: tuple[str, ...] = ()  # zusätzlich gesucht: Teile zerlegter Wörter
    ohne_treffer: tuple[str, ...] = ()  # gesuchte Wörter, die im Bestand nicht vorkommen
    gesamt: int = 0  # verwendbare Quellen mit mindestens einem Suchwort
    begrenzt: bool = False  # ``gesamt`` übersteigt die gelieferten Treffer
    nicht_indexiert: int = 0  # verwendbare Quellen, die der Index nicht enthält
    frageworte_gekuerzt: bool = False  # mehr als MAX_WOERTER Wörter in der Frage


def _wort_ausdruck(wort: str, *, praefix: bool = True) -> str:
    """Suchausdruck für den Wortindex: das Wort als Phrase, mit ``praefix`` auch als Wortanfang („rechnung“ ~ „rechnungen“)."""
    return '"' + wort.replace('"', '""') + '"' + (" *" if praefix else "")


def _woerter_gefuellt(connection: sqlite3.Connection) -> bool:
    """Ob der Wortindex Quellen enthält; bei Einstellung 0 nie, dann kostet er keine Abfrage."""
    return connection.execute("SELECT rowid FROM source_index_woerter LIMIT 1").fetchone() is not None


def _quote(wort: str, *, anfang: bool = False, ganz: bool = False) -> str:
    """Suchausdruck für eine Zeichenfolge; ``anfang`` verlangt einen Wortanfang, ``ganz`` ein ganzes Wort."""
    return '"' + (" " if anfang or ganz else "") + wort.replace('"', '""') + (" " if ganz else "") + '"'


class _Vorkommen:
    """Kommt eine Zeichenfolge im Bestand vor? Antworten werden je Frage gemerkt.

    Teile eines zerlegten Wortes müssen als ganze Wörter vorkommen: Die
    Zeichenfolge „rech“ steht irgendwo, aber kein Wort ist so.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._bekannt: dict[tuple[str, str], bool] = {}
        self.proben = 0
        self.woerter = _woerter_gefuellt(connection)  # ältere Quellen im Wortindex?

    def __call__(self, teil: str, modus: str = "infix") -> bool:
        """``modus``: ``infix`` (irgendwo), ``anfang`` (Wortanfang) oder ``ganz`` (ganzes Wort)."""
        schluessel = (teil, modus)
        if schluessel not in self._bekannt:
            if self.proben >= _MAX_PROBEN:
                return False
            self.proben += 1
            self._bekannt[schluessel] = self._probe(teil, modus)
        return self._bekannt[schluessel]

    def _probe(self, teil: str, modus: str) -> bool:
        if self._connection.execute(
                "SELECT 1 FROM source_index WHERE source_index MATCH ? LIMIT 1",
                (_quote(teil, anfang=modus == "anfang", ganz=modus == "ganz"),)).fetchone() is not None:
            return True
        # Ältere Quellen kennen nur Wörter: ein ganzes Wort, sonst ein Wortanfang.
        return self.woerter and self._connection.execute(
            "SELECT 1 FROM source_index_woerter WHERE source_index_woerter MATCH ? LIMIT 1",
            (_wort_ausdruck(teil, praefix=modus != "ganz"),)).fetchone() is not None


_FUGEN = ("s", "es", "n", "en", "e")


def _zerlegen(wort: str, vorkommt) -> tuple[str, str] | None:
    """Teilt ein zusammengesetztes Wort dort, wo beide Teile im Bestand vorkommen.

    Bevorzugt die Teilung mit dem längsten kürzeren Teil („Stromrechnung“ →
    „strom“ + „rechnung“, nicht „stro“ + „mrechnung“). Fugenlaute am Ende des
    ersten Teils (s, es, n, en, e) fallen dabei weg.
    """
    if len(wort) < _MIN_ZERLEGT:
        return None
    beste, beste_laenge = None, 0
    for schnitt in range(_MIN_ZERLEGUNG, len(wort) - _MIN_ZERLEGUNG + 1):
        rechts, roh = wort[schnitt:], wort[:schnitt]
        for links in (roh, *(roh[:-len(fuge)] for fuge in _FUGEN if roh.endswith(fuge))):
            laenge = min(len(links), len(rechts))
            if laenge >= _MIN_ZERLEGUNG and laenge > beste_laenge and vorkommt(rechts, "ganz") and vorkommt(links, "ganz"):
                beste, beste_laenge = (links, rechts), laenge
    return beste


def woerter(frage: str) -> tuple[list[str], bool]:
    """Suchwörter einer Frage: gefaltet, ohne Funktionswörter, höchstens MAX_WOERTER."""
    gefaltet = sorted({falte(wort) for wort in terms_v1(frage)} - FUNKTIONSWOERTER)
    return gefaltet[:MAX_WOERTER], len(gefaltet) > MAX_WOERTER


def suchen(connection: sqlite3.Connection, frage: str, *, limit: int = 64,
           episode_ids=None, arten=None) -> Suchergebnis:
    """Quellen zur Frage in BM25-Reihenfolge; nur, was ``episodes`` jetzt als verwendbar ausweist.

    ``episode_ids`` begrenzt auf einen Bereich (höchstens 500 IDs), ``arten`` auf
    Arten (Vorgabe: alle aufgenommenen). Bei Gleichstand gewinnt die neuere Quelle.
    """
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("limit muss eine ganze Zahl von 1 bis 1000 sein")
    if episode_ids is not None and len(list(episode_ids)) > 500:
        raise ValueError("höchstens 500 Quellen im Bereich")
    ausgewaehlt, gekuerzt = woerter(frage)
    nicht_indexiert = _zu_gross(connection)
    if not ausgewaehlt or (episode_ids is not None and not list(episode_ids)):
        return Suchergebnis(woerter=tuple(ausgewaehlt), nicht_indexiert=nicht_indexiert, frageworte_gekuerzt=gekuerzt)

    vorkommt = _Vorkommen(connection)
    zusatz: list[str] = []
    ohne_treffer: list[str] = []
    for wort in ausgewaehlt:
        gefunden = vorkommt(wort)
        if not gefunden:
            ohne_treffer.append(wort)
        teile = _zerlegen(wort, vorkommt)
        if teile:
            zusatz.extend(teil for teil in teile if teil not in ausgewaehlt and teil not in zusatz)
    ausdruecke = {"source_index": " OR ".join([*(_quote(wort) for wort in ausgewaehlt),
                                              *(_quote(teil, anfang=True) for teil in zusatz)])}
    if vorkommt.woerter:
        ausdruecke["source_index_woerter"] = " OR ".join(_wort_ausdruck(wort) for wort in [*ausgewaehlt, *zusatz])

    bereich, parameter = "", []
    if episode_ids is not None:
        ids = list(dict.fromkeys(episode_ids))
        bereich = " AND d.episode_id IN (" + ",".join("?" for _ in ids) + ")"
        parameter += ids
    if arten is not None:
        gewaehlt = [art for art in arten if art in ARTEN]
        bereich += " AND d.kind IN (" + ",".join("?" for _ in gewaehlt) + ")"
        parameter += gewaehlt
    listen = []
    for tabelle, ausdruck in ausdruecke.items():
        punkte = f"bm25({tabelle}, " + ", ".join(str(g) for g in GEWICHTE) + ")"
        gefunden = _treffer(connection, tabelle, ausdruck, bereich, parameter, punkte=punkte, benoetigt=limit + 1)
        gefunden.sort(key=lambda t: t[0])  # Reihenfolge nach Punkten (kleiner ist besser)
        listen.append(gefunden)
    treffer = _vereinen(listen)
    gesamt = len(treffer)
    begrenzt = gesamt > limit
    if begrenzt:
        gesamt = sum(_anzahl(connection, tabelle, ausdruck, bereich, parameter)
                     for tabelle, ausdruck in ausdruecke.items())
    return Suchergebnis(
        episoden=tuple(t[2] for t in treffer[:limit]), woerter=tuple(ausgewaehlt), zusatz=tuple(zusatz),
        ohne_treffer=tuple(ohne_treffer), gesamt=gesamt, begrenzt=begrenzt,
        nicht_indexiert=nicht_indexiert, frageworte_gekuerzt=gekuerzt)


def _vereinen(listen: list[list[tuple]]) -> list[tuple]:
    """Die Trefferlisten der beiden Indizes nach BM25-Punkten vereinen.

    Beide Indizes bewerten mit demselben Verfahren, Gewichten und Wortstatistik der
    eigenen Quellen; die Punkte sind nicht identisch skaliert, aber vergleichbar genug,
    dass ein starker Treffer in einem der beiden vor einem schwachen im anderen steht.
    (Ein Abwechseln nach Rang hätte die kleinere Liste bevorzugt: Ihr erster Platz stünde
    gleichauf mit dem ersten der großen.) Bei gleichen Punkten gewinnt die neuere Quelle,
    dann die kleinere ID; mit einer Liste bleibt ihre Reihenfolge.
    """
    if len(listen) == 1:
        return listen[0]
    alle = sorted((t for liste in listen for t in liste), key=lambda t: t[2])  # ID aufsteigend
    alle.sort(key=lambda t: t[1], reverse=True)  # neuere zuerst; stabil
    alle.sort(key=lambda t: t[0])  # zuletzt: Punkte (kleiner ist besser)
    return alle


_MAX_HOLEN = 20_000


def _verwendbare(connection: sqlite3.Connection, ids) -> dict[str, str]:
    """Von diesen Quellen die, die ``episodes`` jetzt als verwendbar ausweist, mit ihrem Zeitpunkt."""
    ergebnis: dict[str, str] = {}
    ids = list(ids)
    for start in range(0, len(ids), 500):
        stueck = ids[start:start + 500]
        for row in connection.execute(
                "SELECT e.id, COALESCE(e.occurred_at, e.recorded_at) FROM episodes e WHERE e.id IN ("
                + ",".join("?" for _ in stueck) + ") AND " + _verwendbar(), stueck):
            ergebnis[row[0]] = row[1]
    return ergebnis


def _treffer(connection: sqlite3.Connection, tabelle: str, ausdruck: str, bereich: str, parameter, *,
             punkte: str, benoetigt: int) -> list[tuple]:
    """Treffer des Index, geprüft gegen ``episodes``: Liste aus (Punkte, Zeit-absteigend, ID).

    Der Index liefert zuerst die besten Kandidaten allein (ohne ``episodes``
    zu verbinden, das wäre bei Tausenden Treffern langsam); danach werden nur
    diese gegen ``episodes`` geprüft. Bleiben dadurch weniger als ``benoetigt``
    übrig, obwohl der Index mehr hätte, wird die Kandidatenmenge vergrößert.
    Die Liste ist nach Zeitpunkt (neu zuerst) und ID vorsortiert; wer nach
    Punkten sortiert, erhält bei Gleichstand die neuere Quelle zuerst.
    """
    holen = max(benoetigt * 3, 64)
    while True:
        rows = connection.execute(
            f"SELECT d.episode_id, {punkte} FROM {tabelle} "
            f"JOIN source_index_docs d ON d.doc = {tabelle}.rowid "
            f"WHERE {tabelle} MATCH ?" + bereich + f" ORDER BY {punkte} LIMIT ?",
            (ausdruck, *parameter, holen)).fetchall()
        zeiten = _verwendbare(connection, (row[0] for row in rows))
        gut = [row for row in rows if row[0] in zeiten]
        if len(gut) >= benoetigt or len(rows) < holen or holen >= _MAX_HOLEN:
            break
        holen = min(holen * 4, _MAX_HOLEN)
    gut.sort(key=lambda row: row[0])  # ID aufsteigend
    gut.sort(key=lambda row: zeiten[row[0]], reverse=True)  # neuere zuerst; stabil
    return [(row[1], zeiten[row[0]], row[0]) for row in gut]


def _anzahl(connection: sqlite3.Connection, tabelle: str, ausdruck: str, bereich: str, parameter) -> int:
    """Zahl der Treffer in einem Index (bei ungestörter Pflege genau die verwendbaren)."""
    verbund = f" JOIN source_index_docs d ON d.doc = {tabelle}.rowid" if bereich else ""
    return connection.execute(f"SELECT count(*) FROM {tabelle}" + verbund +
                              f" WHERE {tabelle} MATCH ?" + bereich, (ausdruck, *parameter)).fetchone()[0]


def literal_kandidaten(connection: sqlite3.Connection, literal: str, *, seite: int = 200):
    """Erzeugt die Kandidaten für eine wörtliche Zeichenfolge (mindestens drei Zeichen) nach Quellen-ID.

    Seitenweise und nur verwendbare Quellen: Wer die ersten Treffer braucht, liest
    nicht den ganzen Bestand. Der Index faltet Akzente und Leerraum, findet also ein
    Übermaß; wer die exakte Semantik braucht, prüft jeden Kandidaten am Originaltext.
    Quellen im Wortindex (ältere, siehe Einstellung) liefert er, wenn die Zeichenfolge
    mit ganzen Wörtern beginnt; das letzte Wort darf ein Wortanfang sein.
    """
    gefaltet = falte(literal)
    if len(gefaltet) < 3:
        return
    bereich = " AND d.kind IN (" + ",".join("'" + art + "'" for art in ARTEN) + ")"
    ausdruecke = {"source_index": _quote(gefaltet)}
    if _woerter_gefuellt(connection):
        ausdruecke["source_index_woerter"] = _wort_ausdruck(gefaltet)
    letzte = ""
    while True:
        rows, volle = [], []
        for tabelle, ausdruck in ausdruecke.items():
            stueck = [row[0] for row in connection.execute(
                f"SELECT d.episode_id FROM {tabelle} JOIN source_index_docs d ON d.doc = {tabelle}.rowid "
                f"WHERE {tabelle} MATCH ?" + bereich + " AND d.episode_id > ? ORDER BY d.episode_id LIMIT ?",
                (ausdruck, letzte, seite))]
            rows += stueck
            if len(stueck) == seite:
                volle.append(stueck[-1])
        # Was hinter der letzten ID einer vollen Seite liegt, fehlt womöglich noch in den anderen Seiten.
        rows = sorted(row for row in rows if not volle or row <= min(volle))
        if not rows:
            return
        verwendbar = _verwendbare(connection, rows)
        for episode_id in rows:
            if episode_id in verwendbar:
                yield episode_id
        if not volle:
            return
        letzte = rows[-1]
