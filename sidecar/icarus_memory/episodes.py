"""Die Mittelfristschicht: rohe Aufzeichnungen dessen, was vorlag.

Zwischen „eine Mail ist angekommen" und „diese Person arbeitet bei X" liegt
Arbeit, und die hatte bisher keinen Ort. Der Bestand nimmt nur Behauptungen über
die Person auf; alles andere existierte nicht. Das ist eine gute Regel für den
Bestand und eine unmögliche für den Alltag.

Eine Episode behauptet nichts. Sie hält fest, **dass etwas vorlag** — mit
Inhalt, Herkunft und Zeitpunkt. Ob daraus eine Aussage über die Person folgt,
entscheidet die Verdichtung, und die legt vor, statt zu schreiben. Siehe
docs/08-gedaechtnisschichten.md.

## Drei Eigenschaften, die die Schicht tragfähig machen

**Digest.** Jede Episode trägt einen SHA-256 ihres Inhalts. Damit schließt sich
die erste offene Lücke aus dem Gedächtnis-Kontrakt: Ohne Digest ist keine
Neuprüfung vor einer folgenreichen Aktion möglich, weil niemand feststellen
kann, ob die Quelle sich seither geändert hat. Ein Vorschlag, der auf einer
inzwischen geänderten Mail beruht, würde sonst ausgeführt, als wäre nichts
passiert.

**Entdopplung über den Digest.** Denselben Vault zweimal aufnehmen erzeugt keine
zweite Kopie. Ohne das ist kein Prozess denkbar, der dauerhaft mitläuft — und
genau der ist das Ziel.

**Zustand statt Löschen.** `new → consolidated → archived`, dazu `ignored` für
das, was bewusst nichts hergab. Eine Episode verschwindet nie; sie hört nur auf,
Arbeit zu erzeugen. Wer wissen will, warum eine Aussage im Bestand steht, findet
über `produced` den Weg zurück zum Rohtext.
"""

from __future__ import annotations

import hashlib
import json
from . import source_index, support_schema
from .datumstext import iso_lesen as _parse
from .store_transactions import sqlite_transaction
import sqlite3
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Iterator

from .migrations import (
    IndexContract,
    Migration,
    run_migrations,
    validate_legacy_or_empty,
    verify_schema,
)
from .model import Provenance, SourceType, ensure_aware, now

CHAT_LOOKUP_TAG = "conversation:memory-lookup"
ENTZUG_MARKE = "entzogen:"
"""Präfix der Marke, mit der das Programm einen eigenen Ausschluss kennzeichnet."""


_SPITZ = re.compile(r'<([^<>]+@[^<>]+)>\s*$')

# Nur Mailquellen können kodierte Kopfnamen tragen. Die eigentliche
# Dekodierung und Namensprüfung findet außerhalb des SQL-Vorfilters statt.
_KODIERTER_MAILNAME = ("json_extract(document, '$.provenance.source_type') = 'email' AND "
                      "json_extract(document, '$.participants') LIKE '%=?%'")


def mail_address(value: Any) -> str:
    """Die Mailadresse einer Teilnehmerangabe, kleingeschrieben, sonst ''.

    Robuster als `parseaddr` allein: „Keller, Anna <anna@x.de>“ ohne
    Anführungszeichen (so liefern Outlook und der Mac-Kalender) ergibt dort
    nichts. Hier zählt der letzte <…>-Block, sonst `parseaddr`, `mailto:` fällt weg.
    """
    from email.utils import parseaddr
    text = str(value or '').strip()
    treffer = _SPITZ.search(text)
    adresse = treffer.group(1) if treffer else parseaddr(text)[1]
    adresse = adresse.strip()
    if adresse.lower().startswith('mailto:'):
        adresse = adresse[7:]
    adresse = adresse.casefold()
    return adresse if '@' in adresse and ' ' not in adresse else ''


def _absender_text(participants: list[str], contacts: list[dict[str, Any]]) -> str:
    """Der Absender einer Mail (`kontakte.absender_text`), spät importiert: kontakte.py braucht `mail_address`."""
    from .kontakte import absender_text
    return absender_text(participants, contacts)


# Höchstzahl Adressen je Abfrage in `participants_for_addresses` (SQLite begrenzt die Tiefe einer OR-Kette).
ADRESSEN_JE_ABFRAGE = 200

class EpisodeKind(str, Enum):
    """Was für ein Vorgang festgehalten wurde.

    Bewusst grob. Eine feinere Einteilung wäre schon eine Deutung, und Deuten
    ist Sache der Verdichtung.
    """

    MESSAGE = "message"
    """Etwas, das jemand geschrieben hat — Mail, Nachricht, Gesprächsausschnitt."""

    DOCUMENT = "document"
    """Etwas Geschriebenes ohne Absender — Notiz, Datei, Seite."""

    EVENT = "event"
    """Etwas mit einem Zeitpunkt — Termin, Frist, Vorgang."""

    INTERACTION = "interaction"
    """Ein Kontakt mit jemandem oder etwas — Profil angesehen, Nachricht geschickt."""

    OBSERVATION = "observation"
    """Was das System selbst bemerkt hat. Trägt nie fremden Text."""

    SUMMARY = "summary"
    """Was aus mehreren Episoden zusammengezogen wurde.

    Die einzige Art, die Icarus selbst schreibt, und deshalb die einzige, die
    wieder verschwinden darf — die Quellen bleiben unangetastet, es geht nichts
    verloren.

    Sie ist **nie Quelle für eine Aussage**. Eine Zusammenfassung ist bereits
    eine Deutung; würde daraus abgeleitet, prüfte die Belegprüfung das Zitat
    gegen einen Text, den das Modell selbst geschrieben hat. Der Beleg zeigte
    dann auf eine Behauptung statt auf Material. Siehe docs/12-zusammenfassung.md.
    """


class EpisodeState(str, Enum):
    NEW = "new"
    CONSOLIDATED = "consolidated"
    ARCHIVED = "archived"
    IGNORED = "ignored"
    """Angesehen, gab nichts her.

    Eigener Zustand statt Löschen: Sonst sieht die Verdichtung dieselbe Episode
    beim nächsten Lauf wieder und legt denselben nutzlosen Vorschlag erneut vor.
    """


# ---------------------------------------------------------------------------
# Was als „geltende“ Quelle gilt: eine Definition, alle Nutzer importieren sie.
#
# Ein Fakt darf nur aus einer Rohquelle kommen (Mail, Nachricht, Dokument, Termin), die
# nicht ignoriert ist und deren Fassung die aktuelle ist. Wer eine neue Art
# oder einen neuen Zustand einführt, ändert genau diese Stelle. Der Test
# `test_geltende_quelle.py` sperrt hart kodierte Kopien in den Modulen.
#
# Absichtlich verschieden bleiben (und sind am Ort so kommentiert):
#   * nur `message` (Absender-/Projektvorschläge: ein Dokument hat keinen Absender),
#   * „archiviert“ zählt mit, wo Archiviertes noch gezählt werden muss
#     (`sql_quelle`, ohne Zustandsfilter: Abdeckung und Fortschritt),
#   * ohne Prüfung der aktuellen Fassung, wo auch überholte Fassungen
#     verarbeitet werden müssen (Einordnungsdurchlauf, Analyse in Seiten).
# ---------------------------------------------------------------------------

QUELLEN_ARTEN: tuple[EpisodeKind, ...] = (EpisodeKind.MESSAGE, EpisodeKind.DOCUMENT, EpisodeKind.EVENT)
"""Arten, die Rohquellen sind: durchsuchbar, einzuordnen, als Beleg zitierbar.

`summary` (selbst geschrieben) und `interaction`/`observation` (kein fremder Text)
gehören bewusst nicht dazu. Eine neue Rohquellenart wird hier eingetragen und
erreicht damit alle SQL-Bausteine unten; `test_kalendergedaechtnis` und
`test_geltende_quelle` prüfen, dass keine Stelle eine Art still auslässt.
"""

ROHQUELLEN = QUELLEN_ARTEN
"""Ältere Bezeichnung derselben Definition (Python-Prüfungen `kind in ROHQUELLEN`)."""

IGNORIERTE_ZUSTAENDE: frozenset[EpisodeState] = frozenset({EpisodeState.IGNORED})
"""Zustände, in denen eine Quelle für nichts mehr herangezogen wird."""

AUSGEBLENDETE_ZUSTAENDE: frozenset[EpisodeState] = frozenset({EpisodeState.IGNORED, EpisodeState.ARCHIVED})
"""Zustände, in denen eine Quelle in Listen und Vorschlägen nicht mehr auftaucht.

Archiviertes bleibt auffindbar (wird getrennt gezählt), ignoriertes nicht.
"""


def _sql_liste(werte: Iterable[Any]) -> str:
    return ", ".join("'" + str(getattr(wert, "value", wert)) + "'" for wert in sorted(werte, key=lambda w: str(getattr(w, "value", w))))


def sql_quelle(alias: str = "episodes") -> str:
    """Nur die Art: Rohquelle. Ohne Zustand, für Zählungen, die Ausgeschlossene mitzeigen."""
    return f"{alias}.kind IN ({_sql_liste(QUELLEN_ARTEN)})"


#: Herkunftsarten, die vom Nutzer selbst oder von Kingfisher stammen, nicht von anderen (Gespräch, eigene Angabe,
#: Korrektur, Abgeleitetes, Werkzeugausgabe).
EIGENE_HERKUNFT = ("chat", "user_stated", "manual_correction", "inference", "tool_output")


def ist_eigene_quelle(source_type: str | None, source_ref: str | None) -> bool:
    """Wahr für eine Quelle, die der Nutzer selbst eingebracht hat (Gesprächszeile, eigene Angabe, hochgeladene Datei)."""
    return (source_type or "") in EIGENE_HERKUNFT or str(source_ref or "").startswith("upload:")


MAIL_PARENT_TAG = "mail-parent:"
_MAIL_ATTACHMENT_KEY = re.compile(r"(mail:[a-f0-9]{64}):anhang:[1-9][0-9]*")


def mail_attachment_parent(connection, source_key, tags):
    """(is attachment, exact parent id); ambiguous legacy sources fail closed."""
    links = [tag for tag in tags if tag.startswith(MAIL_PARENT_TAG)]
    match = _MAIL_ATTACHMENT_KEY.fullmatch(source_key)
    if not (match or links or 'anhang' in tags):
        return False, None
    if match is None:
        return True, None
    if links:
        if len(links) != 1:
            return True, None
        identifier = links[0][len(MAIL_PARENT_TAG):]
        row = connection.execute("SELECT id FROM episodes WHERE id=? AND source_key=? AND kind='message'",
                                 (identifier, match[1])).fetchone()
        return True, row[0] if row else None
    rows = connection.execute("SELECT id,kind FROM episodes WHERE source_key=? LIMIT 2", (match[1],)).fetchall()
    return True, rows[0][0] if len(rows) == 1 and rows[0][1] == 'message' else None


def _sql_is_mail_attachment(alias: str) -> str:
    return (f"({alias}.source_key GLOB 'mail:*:anhang:*' OR EXISTS "
            f"(SELECT 1 FROM json_each({alias}.document, '$.tags') mt "
            "WHERE mt.value='anhang' OR mt.value LIKE 'mail-parent:%'))")


def _sql_direct_mail_parent_valid(alias: str) -> str:
    """Mirror snapshot parent binding before source text reaches SQL consumers."""
    key = f"{alias}.source_key"
    links = f"json_each({alias}.document, '$.tags')"
    tagged = f"(SELECT COUNT(*) FROM {links} mt WHERE mt.value LIKE 'mail-parent:%')"
    key_valid = (f"substr({key},1,5)='mail:' AND length(substr({key},6,64))=64 "
                 f"AND substr({key},6,64) NOT GLOB '*[^0-9a-f]*' AND substr({key},70,8)=':anhang:' "
                 f"AND substr({key},78) GLOB '[1-9]*' AND substr({key},78) NOT GLOB '*[^0-9]*'")
    return (f"(CASE WHEN {_sql_is_mail_attachment(alias)} THEN ({key_valid} AND EXISTS (SELECT 1 FROM episodes mp "
            f"WHERE mp.source_key=substr({key},1,69) AND mp.kind='message' AND mp.state!='ignored' "
            "AND EXISTS (SELECT 1 FROM source_heads mh WHERE mh.source_key=mp.source_key AND mh.episode_id=mp.id) "
            f"AND (({tagged}=1 AND EXISTS (SELECT 1 FROM {links} mt WHERE mt.value='mail-parent:'||mp.id)) "
            f"OR ({tagged}=0 AND (SELECT COUNT(*) FROM episodes mv WHERE mv.source_key=mp.source_key)=1)))) ELSE 1 END)")


def sql_mail_parent_valid(alias: str = "episodes") -> str:
    """Include attachment ancestry of corrections without reopening their targets.

    Missing targets, cycles and overlong chains fail closed. The snapshot allows
    eight reads including the source; an attachment also needs its parent read.
    Ordinary sources use the direct predicate; only corrections traverse.
    """
    return (f"(CASE WHEN {alias}.source_key GLOB 'source-correction:*' THEN ("
            "WITH RECURSIVE attachment_lineage(id,source_key,document,depth) AS ("
            f"SELECT {alias}.id,{alias}.source_key,{alias}.document,0 UNION ALL "
            "SELECT t.id,t.source_key,t.document,l.depth+1 FROM attachment_lineage l "
            "JOIN episodes t ON t.id=substr(l.source_key,19) "
            "WHERE l.source_key GLOB 'source-correction:*' AND l.depth<7) "
            "SELECT EXISTS (SELECT 1 FROM attachment_lineage l WHERE l.source_key NOT GLOB 'source-correction:*') "
            f"AND NOT EXISTS (SELECT 1 FROM attachment_lineage l WHERE NOT {_sql_direct_mail_parent_valid('l')})"
            f" AND NOT EXISTS (SELECT 1 FROM attachment_lineage l WHERE l.depth>=7 AND {_sql_is_mail_attachment('l')})"
            f") ELSE {_sql_direct_mail_parent_valid(alias)} END)")


def sql_nicht_ignoriert(alias: str = "episodes") -> str:
    return f"{alias}.state NOT IN ({_sql_liste(IGNORIERTE_ZUSTAENDE)}) AND {sql_mail_parent_valid(alias)}"


def sql_aktuelle_fassung(alias: str = "episodes") -> str:
    """Die aktuelle Fassung ihrer Quelle (oder eine Quelle ohne Schlüssel)."""
    return (f"({alias}.source_key = '' OR EXISTS (SELECT 1 FROM source_heads h "
            f"WHERE h.source_key = {alias}.source_key AND h.episode_id = {alias}.id))")


def sql_aktuell(alias: str = "episodes") -> str:
    """Nicht ignoriert und aktuelle Fassung, gleich welcher Art."""
    return f"{sql_nicht_ignoriert(alias)} AND {sql_aktuelle_fassung(alias)}"


def sql_rohquelle(alias: str = "episodes") -> str:
    """Rohquelle, nicht ignoriert; alle Fassungen (für den Durchlauf, der auch Überholtes ordnet)."""
    return f"{sql_quelle(alias)} AND {sql_nicht_ignoriert(alias)}"


def sql_nachricht(alias: str = "episodes") -> str:
    """Nur Nachrichten, nicht ignoriert: wo es auf einen Absender ankommt (ein Dokument hat keinen)."""
    return f"{alias}.kind = '{EpisodeKind.MESSAGE.value}' AND {sql_nicht_ignoriert(alias)}"


def sql_geltend(alias: str = "episodes") -> str:
    """Die geltende Quelle: Rohquelle, nicht ignoriert, aktuelle Fassung."""
    return f"{sql_quelle(alias)} AND {sql_aktuell(alias)}"


def sql_nicht_ausgeblendet(alias: str = "episodes") -> str:
    """Weder ignoriert noch archiviert, gleich welcher Art."""
    return f"{alias}.state NOT IN ({_sql_liste(AUSGEBLENDETE_ZUSTAENDE)}) AND {sql_mail_parent_valid(alias)}"


def sql_sichtbar(alias: str = "episodes") -> str:
    """Rohquelle, weder ignoriert noch archiviert (Listen, Treffer, Ausleseansichten)."""
    return f"{sql_quelle(alias)} AND {sql_nicht_ausgeblendet(alias)}"


def digest_of(text: str) -> str:
    """SHA-256 des Inhalts, als `sha256:…`.

    Das Präfix steht dabei, weil das Beispielprofil die Konvention
    `"sha256:9b1c…"` bereits im Freitext benutzt — jetzt als Struktur statt als
    Absprache.
    """
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class Episode:
    id: str
    kind: EpisodeKind
    title: str
    body: str
    provenance: Provenance
    recorded_at: datetime
    """Wann Icarus davon erfahren hat."""

    digest: str = ""
    occurred_at: datetime | None = None
    """Wann es tatsächlich geschah.

    Getrennt von `recorded_at`, weil beides auseinanderfällt: Ein Vault, der
    heute importiert wird, enthält Notizen von vor drei Jahren. Ohne die
    Trennung wäre der ganze Bestand nach einem Import gleich alt — und die
    Alterungsurteile aus `currency.py` wären wertlos.
    """

    state: EpisodeState = EpisodeState.NEW
    project_id: str | None = None
    participants: list[str] = field(default_factory=list)
    """Wer beteiligt war. Die Rohdaten für Kontakte und Verläufe.

    Bei Mail: Absender zuerst, dann An, Cc (und bei eigenen gesendeten Mails
    Bcc), jeweils in der Form „Name <adresse>“.
    """

    contacts: list[dict[str, Any]] = field(default_factory=list)
    """Dieselben Beteiligten mit Rolle (`von`/`an`/`cc`/`bcc`), Name, Adresse und
    `ich`-Kennzeichen, siehe `kontakte.py`. Leer bei Quellen ohne Rollen (Notizen,
    ältere Mails); dort gilt allein `participants`."""

    produced: list[str] = field(default_factory=list)
    """Kennungen der Aussagen, die aus dieser Episode entstanden sind."""

    consolidated_at: datetime | None = None
    tags: list[str] = field(default_factory=list)

    covers: list[str] = field(default_factory=list)
    """Nur bei `summary`: die Episoden, die darin aufgegangen sind.

    Der Weg zurück ins Rohmaterial. Ohne ihn wäre eine Zusammenfassung eine
    Behauptung ohne Herkunft — also genau das, was dieses Projekt vermeidet.
    """

    period: str = ""
    """Nur bei `summary`: der Zeitraum als `JJJJ-MM`.

    Nicht Schmuck, sondern die Bedingung für Wiederholbarkeit: Ein zweiter Lauf
    erkennt daran, dass es den April schon gibt. Über den Digest ginge das nicht
    — ein Modell schreibt zweimal denselben Monat mit anderen Worten.
    """

    def __post_init__(self) -> None:
        if not self.digest:
            self.digest = digest_of(self.body)

    def reference_time(self) -> datetime:
        """Der Zeitpunkt, auf den es fachlich ankommt."""
        return self.occurred_at or self.recorded_at

    def to_dict(self) -> dict[str, Any]:
        def iso(v: datetime | None) -> str | None:
            return v.astimezone().isoformat() if v else None

        return {
            "id": self.id,
            "kind": self.kind.value,
            "title": self.title,
            "body": self.body,
            "digest": self.digest,
            "provenance": self.provenance.to_dict(),
            "recorded_at": iso(self.recorded_at),
            "occurred_at": iso(self.occurred_at),
            "state": self.state.value,
            "project_id": self.project_id,
            "participants": list(self.participants),
            "contacts": [dict(c) for c in self.contacts],
            "produced": list(self.produced),
            "consolidated_at": iso(self.consolidated_at),
            "tags": list(self.tags),
            "covers": list(self.covers),
            "period": self.period,
        }


_CREATE_EPISODES = """
CREATE TABLE IF NOT EXISTS episodes (
    id          TEXT PRIMARY KEY,
    digest      TEXT NOT NULL,
    kind        TEXT NOT NULL,
    state       TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    occurred_at TEXT,
    project_id  TEXT,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL,
    document    TEXT NOT NULL
)
"""

_INDEXES = (
    # Die Entdopplung hängt an dieser Bedingung, nicht an einer Prüfung im Code.
    # Ein zweiter Aufnahmeweg könnte die Prüfung vergessen; den Index nicht.
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_episodes_digest ON episodes(digest)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_state ON episodes(state)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_occurred ON episodes(occurred_at)",
    "CREATE INDEX IF NOT EXISTS idx_episodes_project ON episodes(project_id)",
)
_INDEX_CONTRACTS = {
    "idx_episodes_digest": IndexContract("episodes", ("digest",), unique=True),
    "idx_episodes_state": IndexContract("episodes", ("state",)),
    "idx_episodes_occurred": IndexContract("episodes", ("occurred_at",)),
    "idx_episodes_project": IndexContract("episodes", ("project_id",)),
}

_LEGACY_SCHEMA = {
    "episodes": {
        "id",
        "digest",
        "kind",
        "state",
        "recorded_at",
        "occurred_at",
        "project_id",
        "title",
        "body",
        "document",
    }
}
_PRIMARY_KEYS = {"episodes": {"id"}}


def _migrate_v1(connection: sqlite3.Connection) -> None:
    validate_legacy_or_empty(
        connection,
        store="episodes",
        path=connection.execute("PRAGMA database_list").fetchone()[2],
        expected_tables=_LEGACY_SCHEMA,
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )
    connection.execute(_CREATE_EPISODES)
    for statement in _INDEXES:
        connection.execute(statement)


def _verify_v1(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables=_LEGACY_SCHEMA,
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys=_PRIMARY_KEYS,
    )


def _migrate_v2(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE mail_progress (account_id TEXT PRIMARY KEY, cursor TEXT NOT NULL)")


def _verify_v2(connection: sqlite3.Connection) -> None:
    verify_schema(
        connection,
        expected_tables={**_LEGACY_SCHEMA, "mail_progress": {"account_id", "cursor"}},
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, "mail_progress": {"account_id"}},
    )



def _migrate_v3(connection: sqlite3.Connection) -> None:
    connection.execute("CREATE TABLE source_heads (source_key TEXT PRIMARY KEY, episode_id TEXT NOT NULL)")


def _verify_v3(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={**_LEGACY_SCHEMA, "mail_progress": {"account_id", "cursor"},
                         "source_heads": {"source_key", "episode_id"}},
        expected_indexes=_INDEX_CONTRACTS,
        expected_primary_keys={**_PRIMARY_KEYS, "mail_progress": {"account_id"}, "source_heads": {"source_key"}})



def _migrate_v4(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE episodes ADD COLUMN source_key TEXT NOT NULL DEFAULT ''")
    connection.execute("DROP INDEX idx_episodes_digest")
    connection.execute("CREATE UNIQUE INDEX idx_episodes_digest ON episodes(digest, source_key)")
    # Eindeutige bisherige Zuordnungen behalten ihre Episode und Belege.
    connection.execute("UPDATE episodes SET source_key = (SELECT source_key FROM source_heads WHERE episode_id = episodes.id) WHERE (SELECT COUNT(*) FROM source_heads WHERE episode_id = episodes.id) = 1")


def _verify_v4(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={"episodes": _LEGACY_SCHEMA["episodes"] | {"source_key"},
                         "mail_progress": {"account_id", "cursor"},
                         "source_heads": {"source_key", "episode_id"}},
        expected_indexes={**_INDEX_CONTRACTS,
            "idx_episodes_digest": IndexContract("episodes", ("digest", "source_key"), unique=True)},
        expected_primary_keys={**_PRIMARY_KEYS, "mail_progress": {"account_id"}, "source_heads": {"source_key"}})


def source_metadata_digest(document: dict[str, Any]) -> str:
    """Quellenangaben unabhängig von Aufnahmezeit und späterer Bearbeitung.

    Inhaltsdigest bleibt SHA-256 des Originaltexts. Mengenreihenfolge und
    verschiedene Zeitzonenschreibweisen desselben Zeitpunkts ändern nichts.
    """
    occurred = document.get("occurred_at")
    if occurred:
        occurred = ensure_aware(datetime.fromisoformat(occurred)).astimezone(timezone.utc).isoformat()
    metadata = {
        "kind": document["kind"], "title": document["title"],
        "occurred_at": occurred,
        "participants": sorted(set(document.get("participants") or [])),
        "tags": sorted(set(document.get("tags") or [])),
    }
    # Another final public URL is another provenance version of the same text.
    # Capture time alone does not create a new version.
    provenance = document.get("provenance") or {}
    if provenance.get("source_type") == SourceType.WEB.value and provenance.get("source_ref"):
        metadata["web_source_ref"] = provenance["source_ref"]
    return hashlib.sha256(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _migrate_v5(connection: sqlite3.Connection) -> None:
    connection.execute("ALTER TABLE episodes ADD COLUMN metadata_digest TEXT NOT NULL DEFAULT ''")
    for row in connection.execute("SELECT id, document FROM episodes WHERE source_key != ''").fetchall():
        connection.execute("UPDATE episodes SET metadata_digest = ? WHERE id = ?",
                           (source_metadata_digest(json.loads(row[1])), row[0]))
    connection.execute("DROP INDEX idx_episodes_digest")
    connection.execute("CREATE UNIQUE INDEX idx_episodes_digest ON episodes(digest, source_key, metadata_digest)")


def _verify_v5(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={"episodes": _LEGACY_SCHEMA["episodes"] | {"source_key", "metadata_digest"},
                         "mail_progress": {"account_id", "cursor"},
                         "source_heads": {"source_key", "episode_id"}},
        expected_indexes={**_INDEX_CONTRACTS,
            "idx_episodes_digest": IndexContract("episodes", ("digest", "source_key", "metadata_digest"), unique=True)},
        expected_primary_keys={**_PRIMARY_KEYS, "mail_progress": {"account_id"}, "source_heads": {"source_key"}})


def _verify_v6(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={"episodes": _LEGACY_SCHEMA["episodes"] | {"source_key", "metadata_digest", "support_generation"},
                         "mail_progress": {"account_id", "cursor"},
                         "source_heads": {"source_key", "episode_id"}, **support_schema.EPISODE_TABLES},
        expected_triggers=support_schema.EPISODE_TRIGGERS,
        expected_indexes={**_INDEX_CONTRACTS,
            "idx_source_heads_episode": IndexContract("source_heads", ("episode_id",)),
            "idx_episode_produced_episode": IndexContract("episode_produced_assertions", ("episode_id",)),
            "idx_episodes_digest": IndexContract("episodes", ("digest", "source_key", "metadata_digest"), unique=True)},
        expected_primary_keys={**_PRIMARY_KEYS, "mail_progress": {"account_id"}, "source_heads": {"source_key"}, "episode_produced_assertions": {"assertion_id","episode_id"}})


def _migrate_v7(connection: sqlite3.Connection) -> None:
    # Only source references and one-way token hashes live here. Original text
    # remains solely in episodes, including for the lexical search index.
    connection.execute("""CREATE TABLE working_memory_sources (
        episode_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('complete','failed','deferred','dismissed')),
        model TEXT NOT NULL DEFAULT '', retry_after REAL)""")
    connection.execute("""CREATE TABLE working_memory_items (
        id TEXT PRIMARY KEY, episode_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
        start INTEGER NOT NULL, end INTEGER NOT NULL, kind TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE working_memory_tokens (
        item_id TEXT NOT NULL, token_hash TEXT NOT NULL,
        PRIMARY KEY(item_id, token_hash))""")
    connection.execute("CREATE TABLE working_memory_scan (id INTEGER PRIMARY KEY CHECK(id=1), cursor TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 0 CHECK(revision>=0))")
    connection.execute("INSERT INTO working_memory_scan(id,cursor,revision) VALUES(1,'',0)")
    connection.execute("CREATE INDEX idx_working_memory_items_episode ON working_memory_items(episode_id)")
    connection.execute("CREATE INDEX idx_working_memory_tokens_hash ON working_memory_tokens(token_hash, item_id)")


def _verify_v7(connection: sqlite3.Connection) -> None:
    verify_schema(connection,
        expected_tables={"episodes": _LEGACY_SCHEMA["episodes"] | {"source_key", "metadata_digest", "support_generation"},
                         "mail_progress": {"account_id", "cursor"},
                         "source_heads": {"source_key", "episode_id"}, **support_schema.EPISODE_TABLES,
                         "working_memory_sources": {"episode_id", "fingerprint", "status", "model", "retry_after"},
                         "working_memory_items": {"id", "episode_id", "fingerprint", "start", "end", "kind"},
                         "working_memory_tokens": {"item_id", "token_hash"},
                         "working_memory_scan": {"id", "cursor", "revision"}},
        expected_triggers=support_schema.EPISODE_TRIGGERS,
        expected_indexes={**_INDEX_CONTRACTS,
            "idx_source_heads_episode": IndexContract("source_heads", ("episode_id",)),
            "idx_episode_produced_episode": IndexContract("episode_produced_assertions", ("episode_id",)),
            "idx_episodes_digest": IndexContract("episodes", ("digest", "source_key", "metadata_digest"), unique=True),
            "idx_working_memory_items_episode": IndexContract("working_memory_items", ("episode_id",)),
            "idx_working_memory_tokens_hash": IndexContract("working_memory_tokens", ("token_hash", "item_id"))},
        expected_primary_keys={**_PRIMARY_KEYS, "mail_progress": {"account_id"},
            "source_heads": {"source_key"}, "episode_produced_assertions": {"assertion_id","episode_id"},
            "working_memory_sources": {"episode_id"}, "working_memory_items": {"id"},
            "working_memory_tokens": {"item_id", "token_hash"}, "working_memory_scan": {"id"}})


def _migrate_v8(connection: sqlite3.Connection) -> None:
    from .working_memory_words import backfill
    backfill(connection)


def _migrate_v9(connection: sqlite3.Connection) -> None:
    from .working_memory_store import rekey_without_project
    rekey_without_project(connection, EpisodeStore._from_row)


def _migrate_v10(connection: sqlite3.Connection) -> None:
    from .working_memory_store import compact_index
    compact_index(connection)


def _verify_v10(connection: sqlite3.Connection, *, intake=False, index=False, bezuege=False, lagen=False,
                woerter=False, kreis=False, intake_grund=False, analysis_version=False,
                failure_diagnostics=False) -> None:
    from . import mail_intake
    extra_tables = dict(mail_intake.TABLES if intake_grund else mail_intake.TABLES_V11) if intake else {}
    extra_keys = dict(mail_intake.PRIMARY_KEYS) if intake else {}
    extra_indexes = dict(mail_intake.INDEXES) if intake else {}
    if index:
        tabellen, schluessel = source_index.tabellen(woerter)
        extra_tables.update(tabellen)
        extra_keys.update(schluessel)
        extra_indexes.update(source_index.INDEXES)
    if intake:
        from . import memory_categories
        category_tables = {table: set(columns) for table, columns in memory_categories.TABLES.items()}
        if not failure_diagnostics:
            category_tables["memory_category_sources"] -= {"failure_code"}
        extra_tables.update(category_tables)
        extra_keys.update(memory_categories.PRIMARY_KEYS)
        extra_indexes.update(memory_categories.INDEXES)
    if bezuege:
        from . import bezuege as bezuege_modul
        extra_tables.update(bezuege_modul.TABLES)
        extra_keys.update(bezuege_modul.PRIMARY_KEYS)
        extra_indexes.update(bezuege_modul.INDEXES)
    if lagen:
        from . import lage as lage_modul
        extra_tables.update(lage_modul.TABLES)
        extra_keys.update(lage_modul.PRIMARY_KEYS)
    if kreis:
        from . import akten_arten, kreis as kreis_modul
        extra_tables.update({**kreis_modul.TABLES, **akten_arten.TABLES})
        extra_keys.update({**kreis_modul.PRIMARY_KEYS, **akten_arten.PRIMARY_KEYS})
    verify_schema(connection,
        expected_tables={**extra_tables,"episodes": _LEGACY_SCHEMA["episodes"] | {"source_key", "metadata_digest", "support_generation"},
                         "mail_progress": {"account_id", "cursor"},
                         "source_heads": {"source_key", "episode_id"}, **support_schema.EPISODE_TABLES,
                         "working_memory_sources": ({"episode_id", "fingerprint", "status", "model", "retry_after"}
                                                    | ({"analysis_version"} if analysis_version else set())),
                         "working_memory_items": {"id", "episode_id", "fingerprint", "start", "end", "kind", "key"},
                         "working_memory_terms": {"term", "item"},
                         "working_memory_scan": {"id", "cursor", "revision"}},
        expected_triggers=support_schema.EPISODE_TRIGGERS,
        expected_indexes={**extra_indexes,**_INDEX_CONTRACTS,
            "idx_source_heads_episode": IndexContract("source_heads", ("episode_id",)),
            "idx_episode_produced_episode": IndexContract("episode_produced_assertions", ("episode_id",)),
            "idx_episodes_digest": IndexContract("episodes", ("digest", "source_key", "metadata_digest"), unique=True),
            "idx_working_memory_items_episode": IndexContract("working_memory_items", ("episode_id",)),
            "idx_working_memory_items_key": IndexContract("working_memory_items", ("key",), unique=True),
            "idx_working_memory_terms_item": IndexContract("working_memory_terms", ("item",))},
        expected_primary_keys={**extra_keys,**_PRIMARY_KEYS, "mail_progress": {"account_id"},
            "source_heads": {"source_key"}, "episode_produced_assertions": {"assertion_id","episode_id"},
            "working_memory_sources": {"episode_id"}, "working_memory_items": {"id"},
            "working_memory_terms": {"term", "item"}, "working_memory_scan": {"id"}})


def _migrate_v11(connection):
    from . import mail_intake, memory_categories
    mail_intake.migrate(connection)
    memory_categories.migrate(connection)


def _verify_v11(connection):
    _verify_v10(connection, intake=True)
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)


def _migrate_v12(connection):
    # Volltextindex über alle verwendbaren Quellen, mit Erstbefüllung.
    source_index.install(connection)


def _verify_v12(connection):
    _verify_v10(connection, intake=True, index=True)
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=False)


def _migrate_v13(connection):
    from . import bezuege, memory_categories
    memory_categories.migrate_ort(connection)
    bezuege.migrate(connection)


def _verify_v13(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True)
    from . import bezuege
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=False)
    bezuege.verify(connection)


def _migrate_v14(connection):
    from . import lage
    lage.migrate(connection)


def _verify_v14(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True, lagen=True)
    from . import bezuege, lage
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=False)
    bezuege.verify(connection)
    lage.verify(connection)


def _migrate_v15(connection):
    from . import source_index
    source_index.migrate_woerter(connection)


def _verify_v15(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True, lagen=True, woerter=True)
    from . import bezuege, lage
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=True)
    bezuege.verify(connection)
    lage.verify(connection)


def _migrate_v16(connection):
    # Kreis je Person und private Akten-Arten (M4): nur, was ein Mensch bestätigt hat.
    from . import akten_arten, kreis
    kreis.migrate(connection)
    akten_arten.migrate(connection)


def _verify_v16(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True, lagen=True, woerter=True, kreis=True)
    from . import bezuege, lage
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=True)
    bezuege.verify(connection)
    lage.verify(connection)


def _migrate_v17(connection):
    # Gescheiterte Mails tragen ihren Grund (Fremdprobe 3, Befund 2).
    from . import mail_intake
    mail_intake.migrate_grund(connection)


def _verify_v17(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True, lagen=True, woerter=True, kreis=True,
                intake_grund=True)
    from . import bezuege, lage
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=True)
    bezuege.verify(connection)
    lage.verify(connection)


def _migrate_v18(connection):
    # Versionierte Einordnung, ohne bestehende aktuelle Referenzen neu zu berechnen.
    connection.execute(
        "ALTER TABLE working_memory_sources ADD COLUMN analysis_version INTEGER NOT NULL DEFAULT 1")


def _verify_v18(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True, lagen=True, woerter=True, kreis=True,
                intake_grund=True, analysis_version=True)
    from . import bezuege, lage
    from .memory_categories import verify
    verify(connection, failure_diagnostics=False)
    source_index.verify(connection, woerter=True)
    bezuege.verify(connection)
    lage.verify(connection)


def _migrate_v19(connection):
    # Die Gesundheitsansicht erhält eine Taxonomieoption, aber keine alten
    # Quellen werden allein deshalb erneut ausgewertet oder umgeschrieben.
    from .memory_areas import ensure_health_taxonomy
    ensure_health_taxonomy(connection)


def _verify_v19(connection):
    _verify_v18(connection)
    from .memory_areas import verify_health_taxonomy
    verify_health_taxonomy(connection)


def _migrate_v20(connection):
    # Fehlergründe bleiben geschlossene, inhaltsfreie Codes; Altbestände bleiben NULL.
    from .memory_categories import migrate_failure_diagnostics
    migrate_failure_diagnostics(connection)


def _verify_v20(connection):
    _verify_v10(connection, intake=True, index=True, bezuege=True, lagen=True, woerter=True, kreis=True,
                intake_grund=True, analysis_version=True, failure_diagnostics=True)
    from . import bezuege, lage
    from .memory_categories import verify
    verify(connection, failure_diagnostics=True)
    source_index.verify(connection, woerter=True)
    bezuege.verify(connection)
    lage.verify(connection)
    from .memory_areas import verify_health_taxonomy
    verify_health_taxonomy(connection)


_MIGRATIONS = (
    Migration(1, "initial_explicit_version", _migrate_v1, _verify_v1),
    Migration(2, "mail_sync_progress", _migrate_v2, _verify_v2),
    Migration(3, "source_version_heads", _migrate_v3, _verify_v3),
    Migration(4, "source_scoped_digest", _migrate_v4, _verify_v4),
    Migration(5, "source_metadata_versions", _migrate_v5, _verify_v5),
    Migration(6, "episode_support_generation_and_produced", support_schema.migrate_episodes, _verify_v6),
    Migration(7, "working_memory_source_references", _migrate_v7, _verify_v7),
    Migration(8, "working_memory_suffix_candidates", _migrate_v8, _verify_v7),
    Migration(9, "working_memory_fingerprint_without_project", _migrate_v9, _verify_v7),
    Migration(10, "working_memory_compact_terms", _migrate_v10, _verify_v10),
    Migration(11, "mail_intake_and_categories", _migrate_v11, _verify_v11),
    Migration(12, "source_index_fts", _migrate_v12, _verify_v12),
    Migration(13, "bezuege_akten_und_orte", _migrate_v13, _verify_v13),
    Migration(14, "lagen", _migrate_v14, _verify_v14),
    Migration(15, "source_index_woerter", _migrate_v15, _verify_v15),
    Migration(16, "kreis_und_akten_arten", _migrate_v16, _verify_v16),
    Migration(17, "mail_intake_grund", _migrate_v17, _verify_v17),
    Migration(18, "working_memory_analysis_version", _migrate_v18, _verify_v18),
    Migration(19, "memory_area_health_taxonomy", _migrate_v19, _verify_v19),
    Migration(20, "category_failure_diagnostics", _migrate_v20, _verify_v20),
)


class EpisodeError(Exception):
    """Eine Episode ist unbekannt oder ein Zustandswechsel ist nicht erlaubt."""


class EpisodeStore:
    """Episoden in einer lokalen Datei, neben dem Selbstmodell."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        try:
            with self._lock:
                run_migrations(
                    self._conn,
                    store="episodes",
                    path=self._path,
                    migrations=_MIGRATIONS,
                )
            with self._lock:
                # Fängt ab, was die Pflege an den Zustandswechseln verfehlt hat;
                # ohne Abweichung keine Schreibsperre.
                if not source_index.stimmt(self._conn):
                    with self.transaction():
                        source_index.abgleichen(self._conn)
        except Exception:
            self._conn.close()
            raise

    # -- Suchindex: Wortteile für die letzten Jahre --------------------------

    def suchindex_jahre(self) -> int:
        """Die Einstellung allein (billig): Wortteile für so viele Jahre zurück, 0 = alle."""
        with self._lock:
            return source_index.wortteile_jahre(self._conn)

    def suchindex_stand(self) -> dict:
        """Einstellung, Verteilung der Quellen auf die beiden Indizes und belegter Platz (Bytes, sonst ``None``)."""
        with self._lock:
            zahlen = source_index.abdeckung(self._conn)
            return {"wortteile_jahre": source_index.wortteile_jahre(self._conn),
                    "quellen": zahlen["aufgenommen"], "zu_gross": zahlen["zu_gross"],
                    **source_index.verteilung(self._conn), "bytes": source_index.groesse(self._conn)}

    def suchindex_einstellen(self, jahre: int, *, seite: int = 500) -> dict:
        """Wortteile nur für Quellen der letzten ``jahre`` Jahre (0 = alle) und den Index danach umbauen.

        Stuft seitenweise um: Zwischen den Seiten gibt die Sperre frei, und keine Quelle
        fehlt im Index, solange es läuft. Gibt den Stand zurück, ergänzt um ``umgestuft``
        und ``verdichtet`` (ob der freigewordene Platz an das Dateisystem zurückging).
        """
        with self.transaction():
            geaendert = source_index.einstellen(self._conn, jahre)
        umgestuft = 0
        # Jeder Durchgang bringt `seite` Quellen an ihren Platz; mehr Durchgänge als Quellen gibt es nicht
        # (sonst drehte sich eine Quelle, die nie am Platz ankommt, endlos im Kreis).
        with self._lock:
            quellen = self._conn.execute("SELECT count(*) FROM source_index_docs").fetchone()[0]
        for _ in range(quellen // seite + 2):
            with self.transaction():
                schritt = source_index.umstufen(self._conn, grenze=seite)
            umgestuft += schritt
            if schritt < seite:
                break
        if umgestuft:
            with self.transaction():
                source_index.verdichten(self._conn)
        return {**self.suchindex_stand(), "geaendert": geaendert, "umgestuft": umgestuft,
                "verdichtet": self._platz_zurueckgeben() if umgestuft else False}

    def _platz_zurueckgeben(self, *, mindestens: int = 8 * 1024 * 1024) -> bool:
        """Freien Platz der Datei zurückgeben (VACUUM), wenn es sich lohnt. Ein Fehler bleibt folgenlos."""
        with self._lock:
            try:
                frei = self._conn.execute("PRAGMA freelist_count").fetchone()[0] * \
                    self._conn.execute("PRAGMA page_size").fetchone()[0]
                if frei < mindestens:
                    return False
                self._conn.commit()
                self._conn.execute("VACUUM")
                return True
            except sqlite3.Error:
                return False

    # -- Aufnehmen ---------------------------------------------------------

    def mail_cursor(self, account_id: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT cursor FROM mail_progress WHERE account_id = ?", (account_id,)).fetchone()
        return row[0] if row else None

    def advance_mail_cursor(self, account_id: str, expected: str | None, cursor: str) -> None:
        """Erst nach Quellenaufnahme aufrufen; konkurrierender Fortschritt gewinnt."""
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                row = self._conn.execute("SELECT cursor FROM mail_progress WHERE account_id = ?", (account_id,)).fetchone()
                if (row[0] if row else None) != expected:
                    raise EpisodeError("Der Mail-Fortschritt wurde inzwischen geändert.")
                self._conn.execute("INSERT INTO mail_progress(account_id, cursor) VALUES (?, ?) ON CONFLICT(account_id) DO UPDATE SET cursor = excluded.cursor", (account_id, cursor))
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def source_heads(self) -> list[tuple[str, Episode]]:
        """Aktuelle Zuordnungen samt unverändertem Quellenbeleg."""
        with self._lock:
            rows = self._conn.execute("SELECT h.source_key, e.document FROM source_heads h JOIN episodes e ON e.id=h.episode_id").fetchall()
        return [(row[0], self._from_row(row)) for row in rows]

    def source_head(self, source_key: str) -> str | None:
        with self._lock:
            row = self._conn.execute("SELECT episode_id FROM source_heads WHERE source_key = ?", (source_key,)).fetchone()
        return row[0] if row else None

    def heads_with_prefix(self, prefix: str) -> list[tuple[str, str, str, str, str | None]]:
        """Aktuelle Fassungen aller Quellen, deren Schlüssel mit `prefix` beginnt.

        Je Quelle: (Schlüssel, Episode, Inhaltsdigest, Zustand, Zeitpunkt). Ohne
        Texte geladen; der Bereichsvergleich nutzt den Primärschlüssel der
        Zeigertabelle statt eines Durchgangs über alle Episoden.
        """
        obergrenze = prefix[:-1] + chr(ord(prefix[-1]) + 1) if prefix else ""
        with self._lock:
            rows = self._conn.execute(
                "SELECT h.source_key, e.id, e.digest, e.state, e.occurred_at FROM source_heads h "
                "JOIN episodes e ON e.id = h.episode_id "
                "WHERE h.source_key >= ? AND h.source_key < ?", (prefix, obergrenze)).fetchall()
        return [tuple(row) for row in rows]

    def advance_source_head(self, source_key: str, expected: str | None, episode_id: str) -> None:
        """Versionszeiger erst nach Sperren des alten Belegs umstellen."""
        with self.transaction():
            current = self._conn.execute("SELECT episode_id FROM source_heads WHERE source_key = ?", (source_key,)).fetchone()
            if (current[0] if current else None) != expected:
                raise EpisodeError("Die Quellenversion wurde inzwischen geändert. Bitte erneut aufnehmen.")
            if not self._conn.execute("SELECT 1 FROM episodes WHERE id = ?", (episode_id,)).fetchone():
                raise EpisodeError("Unbekannte Quellenversion")
            self._conn.execute("INSERT INTO source_heads VALUES (?, ?) ON CONFLICT(source_key) DO UPDATE SET episode_id=excluded.episode_id", (source_key, episode_id))
            # Die neue Fassung wird durchsuchbar, die ersetzte verschwindet aus dem Index.
            if current:
                source_index.synchronisieren(self._conn, current[0])
            source_index.synchronisieren(self._conn, episode_id)

    def record(
        self,
        kind: EpisodeKind,
        title: str,
        body: str,
        provenance: Provenance,
        *,
        occurred_at: datetime | None = None,
        project_id: str | None = None,
        participants: list[str] | None = None,
        tags: list[str] | None = None,
        at: datetime | None = None,
        source_key: str = "",
        contacts: list[dict[str, Any]] | None = None,
    ) -> tuple[Episode, bool]:
        """Nimmt eine Episode auf. Gibt sie zurück und ob sie **neu** war.

        Der zweite Wert ist der Grund, warum diese Methode kein schlichtes
        `add()` ist: Ein Aufnahmelauf über einen Vault mit tausend Dateien muss
        berichten können, was er tatsächlich getan hat. „847 aufgenommen, 153
        schon bekannt" ist die Zeile, die den Nutzer beruhigt; „1000 verarbeitet"
        ist die, die ihn misstrauisch macht.

        Bei einem bekannten Digest bleibt der **bestehende** Eintrag stehen. Ihn
        zu überschreiben hieße, Zustand und `produced` zu verlieren — die
        Episode käme erneut in die Verdichtung, und der Nutzer bekäme Vorschläge
        vorgelegt, die er längst entschieden hat.
        """
        metadata_digest = source_metadata_digest({
            "kind": kind.value, "title": title,
            "occurred_at": occurred_at.isoformat() if occurred_at else None,
            "participants": participants, "tags": tags,
            "provenance": provenance.to_dict(),
        }) if source_key else ""
        # Mehrdeutige Altzuordnungen nicht durch Neuaufnahme umdeuten.
        # Ihre konservative Sperre bleibt bis zur expliziten Klärung erhalten.
        if source_key:
            previous = self.source_head(source_key)
            if previous:
                legacy = self.get(previous)
                with self._lock:
                    row = self._conn.execute("SELECT source_key FROM episodes WHERE id = ?", (previous,)).fetchone()
                if row[0] == "" and legacy.digest == digest_of(body) and source_metadata_digest(legacy.to_dict()) == metadata_digest:
                    return legacy, False
        existing = self.by_digest(digest_of(body), source_key=source_key, metadata_digest=metadata_digest)
        if existing is not None:
            return existing, False
        if project_id is None and source_key:
            # Eine neue Fassung derselben Quelle bleibt im Projekt, dem der
            # Nutzer die bisherige zugeordnet hat.
            head = self.source_head(source_key)
            if head:
                project_id = self.get(head).project_id

        episode = Episode(
            id=f"e-{uuid.uuid4().hex[:12]}",
            kind=kind,
            title=title,
            body=body,
            provenance=provenance,
            recorded_at=ensure_aware(at) or now(),
            occurred_at=ensure_aware(occurred_at),
            project_id=project_id,
            participants=list(participants or []),
            contacts=[dict(c) for c in contacts or []],
            tags=list(tags or []),
        )
        self._put(episode, source_key=source_key)
        return episode, True

    def add_mail_headers(self, episode_id: str, tags: list[str]) -> Episode:
        """Append advisory header links without changing original, identity, date or exclusion."""
        with self.transaction():
            episode = self.get(episode_id)
            if episode.state is EpisodeState.IGNORED:
                return episode
            added = [t for t in tags if t not in episode.tags]
            if not added:
                return episode
            episode.tags.extend(added)
            document = episode.to_dict()
            self._conn.execute(
                "UPDATE episodes SET document=?, metadata_digest=?, support_generation=support_generation+1 WHERE id=?",
                (json.dumps(document, ensure_ascii=False), source_metadata_digest(document), episode_id))
            return episode

    def set_mail_attachment_report(self, episode_id: str, report: dict) -> Episode:
        """Replace advisory intake coverage without changing the original text."""
        tag = 'mail:attachments:' + json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self.transaction():
            episode = self.get(episode_id)
            if episode.state is EpisodeState.IGNORED:
                return episode
            tags = [value for value in episode.tags if not value.startswith('mail:attachments:')]
            tags.append(tag)
            if tags == episode.tags:
                return episode
            episode.tags = tags
            document = episode.to_dict()
            self._conn.execute(
                'UPDATE episodes SET document=?,metadata_digest=?,support_generation=support_generation+1 WHERE id=?',
                (json.dumps(document, ensure_ascii=False), source_metadata_digest(document), episode_id))
            return episode

    def _mail_attachment_descendants(self, parent_id: str) -> list[str]:
        """All stored child versions for withdrawal, including ambiguous legacy ones."""
        with self._lock:
            parent = self._conn.execute('SELECT source_key FROM episodes WHERE id=?', (parent_id,)).fetchone()
            if parent is None or not re.fullmatch(r'mail:[a-f0-9]{64}', parent[0]):
                return []
            rows = self._conn.execute(
                "SELECT id,source_key,document FROM episodes WHERE source_key LIKE ?",
                (parent[0] + ':anhang:%',)).fetchall()
            result = []
            for row in rows:
                tags = json.loads(row['document']).get('tags', [])
                links = [tag for tag in tags if tag.startswith(MAIL_PARENT_TAG)]
                if not links or MAIL_PARENT_TAG + parent_id in links:
                    result.append(row['id'])
            return result

    def mail_attachment_children(self, parent_id: str) -> list[str]:
        """Current child versions bound to this parent; never guess legacy ancestry."""
        with self._lock:
            result = []
            for identifier in self._mail_attachment_descendants(parent_id):
                row = self._conn.execute('SELECT source_key,document FROM episodes WHERE id=?', (identifier,)).fetchone()
                _, bound = mail_attachment_parent(self._conn, row['source_key'], json.loads(row['document']).get('tags', []))
                if bound == parent_id and self.source_head(row['source_key']) == identifier:
                    result.append(identifier)
            return result

    def add_contacts(self, episode_id: str, contacts: list[dict[str, Any]],
                     participants: list[str]) -> Episode:
        """Ergänzt Beteiligte einer schon aufgenommenen Quelle (Nachtrag).

        Der Originaltext, sein Digest und der Zustand bleiben unberührt. Nur
        Metadaten wachsen: Wer schon eingetragen war, bleibt, neue Beteiligte
        kommen hinzu. Der Metadaten-Fingerabdruck wird nachgeführt, damit ein
        späteres, gleichlautendes Einlesen keine zweite Fassung anlegt, und die
        Stützgeneration steigt, damit die Auswertung die Quelle neu ansieht.
        """
        with self.transaction():
            episode = self.get(episode_id)
            if episode.state is EpisodeState.IGNORED:
                raise EpisodeError("Ausgeschlossene Quelle wird nicht ergänzt")
            bekannt = {(c.get("adresse") or (c.get("name") or "").casefold(), c.get("rolle"))
                       for c in episode.contacts}
            for eintrag in contacts:
                schluessel = (eintrag.get("adresse") or (eintrag.get("name") or "").casefold(),
                              eintrag.get("rolle"))
                if schluessel not in bekannt:
                    bekannt.add(schluessel)
                    episode.contacts.append(dict(eintrag))
            for text in participants:
                if text not in episode.participants:
                    episode.participants.append(text)
            document = episode.to_dict()
            row = self._conn.execute("SELECT source_key FROM episodes WHERE id=?", (episode_id,)).fetchone()
            self._conn.execute(
                "UPDATE episodes SET document=?, metadata_digest=?, support_generation=support_generation+1 WHERE id=?",
                (json.dumps(document, ensure_ascii=False),
                 source_metadata_digest(document) if row[0] else "", episode_id))
            return episode

    def remove_contacts(self, episode_id: str, contacts: list[dict[str, Any]],
                        participants: list[str]) -> Episode:
        """Nimmt Beteiligte zurück, die `add_contacts` nachgetragen hatte (Rücknahme einer Übernahme).

        Entfernt wird nur, was genau so übergeben wird; alles andere bleibt. Text, Digest
        und Zustand bleiben unberührt, Fingerabdruck und Stützgeneration werden wie beim
        Nachtrag nachgeführt.
        """
        with self.transaction():
            episode = self.get(episode_id)
            weg = {(c.get("adresse") or (c.get("name") or "").casefold(), c.get("rolle")) for c in contacts}
            episode.contacts = [c for c in episode.contacts
                                if (c.get("adresse") or (c.get("name") or "").casefold(), c.get("rolle")) not in weg]
            episode.participants = [t for t in episode.participants if t not in set(participants)]
            document = episode.to_dict()
            row = self._conn.execute("SELECT source_key FROM episodes WHERE id=?", (episode_id,)).fetchone()
            self._conn.execute(
                "UPDATE episodes SET document=?, metadata_digest=?, support_generation=support_generation+1 WHERE id=?",
                (json.dumps(document, ensure_ascii=False),
                 source_metadata_digest(document) if row[0] else "", episode_id))
            return episode

    def enrich_chat_source(
        self, episode_id: str, source_ref: str, *, participants: list[str] | None = None,
        tags: list[str] | None = None, project_id: str | None = None,
    ) -> Episode:
        """Attach explicit Merke hints to its already captured user turn.

        The original text, digest, and state cannot change. Updating the
        metadata fingerprint invalidates any earlier automatic analysis.
        """
        with self.transaction():
            episode = self.get(episode_id)
            if (episode.kind is not EpisodeKind.MESSAGE
                    or episode.provenance.source_type is not SourceType.CHAT
                    or episode.provenance.source_ref != source_ref
                    or episode.state is EpisodeState.IGNORED):
                raise EpisodeError("Gesprächsquelle ist nicht ergänzbar")
            episode.participants = sorted(set(episode.participants) | set(participants or []))
            episode.tags = sorted(set(episode.tags) | set(tags or []))
            if project_id is not None:
                episode.project_id = project_id
            document = episode.to_dict()
            row = self._conn.execute("SELECT source_key FROM episodes WHERE id=?", (episode_id,)).fetchone()
            self._conn.execute(
                "UPDATE episodes SET project_id=?, document=?, metadata_digest=?, support_generation=support_generation+1 WHERE id=?",
                (episode.project_id, json.dumps(document, ensure_ascii=False),
                 source_metadata_digest(document) if row[0] else "", episode_id),
            )
            source_index.synchronisieren(self._conn, episode_id, neu=True)
            return episode

    # -- Zustand -----------------------------------------------------------

    def mark_consolidated(
        self, episode_id: str, produced: list[str] | None = None,
        at: datetime | None = None,
    ) -> Episode:
        """Hält fest, dass die Verdichtung diese Episode angesehen hat.

        `produced` ist der Rückweg: Wer eine Aussage im Bestand sieht, kommt
        über `derived_from` zur Episode und von dort zum Rohtext. Ohne diesen
        Weg wäre die Verdichtung eine Blackbox, die Behauptungen erzeugt.
        """
        with self.transaction():
            episode = self.get(episode_id)
            episode.state = EpisodeState.CONSOLIDATED
            episode.consolidated_at = ensure_aware(at) or now()
            # Ergänzen statt ersetzen: Ein zweiter Lauf kann weitere Aussagen
            # hervorbringen, und die erste Herleitung darf dabei nicht verschwinden.
            for assertion_id in produced or []:
                if assertion_id not in episode.produced:
                    episode.produced.append(assertion_id)
            self._put(episode)
            return episode

    def ignore(self, episode_id: str, *, grund: str = "") -> Episode:
        """Schließt eine Quelle aus.

        `grund` ist leer, wenn der Nutzer sie ausschließt. Setzt das Programm
        selbst den Ausschluss (ersetzte Fassung, entzogene Kalenderquelle),
        steht er als Marke `entzogen:<grund>` an der Episode. Nur daran ist
        später zu erkennen, dass eine wiederkehrende Fassung (Termin zurück
        verschoben, Kalender neu verbunden) wieder gelten darf, ein Ausschluss
        des Nutzers dagegen bleibt.
        """
        with self.transaction():
            episode = self.get(episode_id)
            children = self._mail_attachment_descendants(episode_id)
            episode.state = EpisodeState.IGNORED
            if grund and (marke := f"{ENTZUG_MARKE}{grund}") not in episode.tags:
                episode.tags.append(marke)
            self._put(episode)
            # Eine spätere ausdrückliche Sperre entzieht auch Berichtigungen
            # ihren Bezug. Das gilt selbst dann, wenn das Original bereits
            # beim Anlegen einer Berichtigung ausgeschlossen worden war.
            if self.source_head('source-correction:' + episode_id):
                self._conn.execute('UPDATE episodes SET support_generation=support_generation+1 WHERE id=?',
                                   (episode_id,))
            for child_id in children:
                self.ignore(child_id, grund=grund)
                correction = self.source_head('source-correction:' + child_id)
                seen = set()
                while correction and correction not in seen:
                    seen.add(correction)
                    self.ignore(correction, grund=grund)
                    correction = self.source_head('source-correction:' + correction)
            return episode

    def reopen(self, episode_id: str) -> Episode:
        """Gespeicherten Rohtext ausdrücklich erneut prüfen, nie Wissen bestätigen."""
        with self.transaction():
            episode = self.get(episode_id)
            snapshot = self.support_snapshot(episode_id)
            if not snapshot.mail_parent_valid:
                raise EpisodeError('Die zugehörige Mail ist ausgeschlossen, ersetzt oder nicht eindeutig zugeordnet.')
            if not snapshot.correction_valid:
                raise EpisodeError('Der Bezug dieser Berichtigung ist nicht mehr gültig. Bitte die aktuelle Quelle prüfen.')
            if episode.state is not EpisodeState.IGNORED:
                return episode
            if self.source_head('source-correction:' + episode_id):
                raise EpisodeError('Zu dieser Quelle gibt es eine Berichtigung. Bitte die Berichtigung prüfen; das Original bleibt ausgeschlossen.')
            with self._lock:
                row = self._conn.execute("SELECT source_key FROM episodes WHERE id = ?", (episode_id,)).fetchone()
                if row[0]:
                    head = self._conn.execute("SELECT episode_id FROM source_heads WHERE source_key = ?", (row[0],)).fetchone()
                    if head is not None and head[0] != episode_id:
                        raise EpisodeError("Es gibt eine andere aktuelle Fassung dieser Quelle.")
            episode.state = EpisodeState.NEW
            episode.tags = [tag for tag in episode.tags if not tag.startswith(ENTZUG_MARKE)]
            self._put(episode, _reopen=True)
            return episode

    def archive_before(self, cutoff: datetime) -> int:
        """Archiviert Verdichtetes, das älter ist als `cutoff`.

        Ignorierte Quellen bleiben ausgeschlossen, auch nach Zeitablauf.

        `new` bleibt unangetastet, egal wie alt: Eine Episode, die nie jemand
        angesehen hat, verschwindet nicht in der Ablage, nur weil Zeit vergeht.
        Das wäre stilles Vergessen, und zwar genau des Materials, das noch
        Arbeit erzeugen sollte.
        """
        cutoff = ensure_aware(cutoff) or cutoff
        betroffen = [
            e for e in self.all_episodes(limit=100000)
            if e.state is EpisodeState.CONSOLIDATED
            and e.reference_time() < cutoff
        ]
        for episode in betroffen:
            episode.state = EpisodeState.ARCHIVED
            self._put(episode)
        return len(betroffen)

    # -- Zusammenfassungen -------------------------------------------------
    #
    # Die einzigen Episoden, die Icarus selbst schreibt. Deshalb gelten für sie
    # zwei Regeln, die für Rohmaterial nicht gälten: Sie kommen nie in die
    # Verdichtung, und sie dürfen wieder verschwinden.

    def record_summary(
        self,
        title: str,
        body: str,
        period: str,
        covers: list[str],
        *,
        extracted_by: str = "",
        at: datetime | None = None,
    ) -> Episode:
        """Legt eine Zusammenfassung an und archiviert, was darin aufgeht.

        Sie entsteht direkt als `consolidated`, nicht als `new`. Eine
        Zusammenfassung, die auf Verdichtung wartet, wäre der Kreis, den die
        Belegprüfung nicht mehr schließen kann: Das Modell prüfte sein Zitat
        gegen einen Text, den es selbst geschrieben hat.
        """
        if not covers:
            raise EpisodeError(
                "Eine Zusammenfassung ohne Quellen ist eine Behauptung ohne Herkunft."
            )
        zeit = ensure_aware(at) or now()
        episode = Episode(
            id=f"z-{uuid.uuid4().hex[:12]}",
            kind=EpisodeKind.SUMMARY,
            title=title,
            body=body,
            provenance=Provenance(
                source_type=SourceType.INFERENCE,
                source_ref=f"episoden:{len(covers)}",
                captured_at=zeit,
                extracted_by=extracted_by or None,
            ),
            recorded_at=zeit,
            state=EpisodeState.CONSOLIDATED,
            consolidated_at=zeit,
            covers=list(covers),
            period=period,
        )
        self._put(episode)

        # Erst jetzt archivieren. Bricht das Anlegen ab, ist nichts weggeräumt,
        # was danach niemand mehr in der Liste findet.
        for quelle in covers:
            original = self.get(quelle)
            original.state = EpisodeState.ARCHIVED
            self._put(original)
        return episode

    def summary_for(self, period: str) -> Episode | None:
        """Gibt es den Monat schon? Die Bedingung für einen zweiten Lauf."""
        for episode in self.summaries():
            if episode.period == period:
                return episode
        return None

    def summaries(self, limit: int = 200) -> list[Episode]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM episodes WHERE kind = ? "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC LIMIT ?",
                (EpisodeKind.SUMMARY.value, limit),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def delete_summary(self, episode_id: str) -> int:
        """Nimmt eine Zusammenfassung zurück und holt die Quellen hervor.

        Der einzige Weg, auf dem eine Episode je verschwindet — und er gilt
        ausschließlich für das, was Icarus selbst geschrieben hat. Rohmaterial
        wird nie gelöscht: Es ist der Beleg, auf den sich alles andere beruft.

        Ohne diesen Weg wäre die Zusammenfassung eine Einbahnstraße. Ein Modell,
        das einen Monat falsch zusammenfasst, hätte den Monat dann faktisch
        ersetzt, und niemand käme mehr an die Übersicht darüber heran.
        """
        episode = self.get(episode_id)
        if episode.kind is not EpisodeKind.SUMMARY:
            raise EpisodeError(
                "Nur Zusammenfassungen dürfen gelöscht werden. "
                f"{episode_id} ist Rohmaterial ({episode.kind.value})."
            )

        zurueck = 0
        for quelle in episode.covers:
            try:
                original = self.get(quelle)
            except EpisodeError:
                continue
            if original.state is EpisodeState.ARCHIVED:
                original.state = EpisodeState.CONSOLIDATED
                self._put(original)
                zurueck += 1

        with self._lock:
            self._conn.execute("DELETE FROM episodes WHERE id = ?", (episode_id,))
            source_index.entfernen(self._conn, episode_id)
            self._conn.commit()
        return zurueck

    def link_project(self, episode_id: str, project_id: str | None) -> Episode:
        episode = self.get(episode_id)
        episode.project_id = project_id
        self._put(episode)
        return episode

    # -- Lesen -------------------------------------------------------------

    def get(self, episode_id: str) -> Episode:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM episodes WHERE id = ?", (episode_id,)
            ).fetchone()
        if row is None:
            raise EpisodeError(f"Unbekannte Episode: {episode_id}")
        return self._from_row(row)

    def by_digest(self, digest: str, *, source_key: str | None = None, metadata_digest: str | None = None) -> Episode | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT document FROM episodes WHERE digest = ?"
                + (" AND source_key = ?" if source_key is not None else "")
                + (" AND metadata_digest = ?" if metadata_digest is not None else "")
                + " ORDER BY recorded_at, id LIMIT 1",
                (digest,) + ((source_key,) if source_key is not None else ())
                + ((metadata_digest,) if metadata_digest is not None else ()) ,
            ).fetchone()
        return self._from_row(row) if row else None

    def pending(self, limit: int = 100) -> list[Episode]:
        """Was auf Verdichtung wartet, Ältestes zuerst.

        Die Reihenfolge ist Absicht: Verdichtung soll chronologisch arbeiten,
        sonst entstehen Aussagen aus dem Mai, bevor die aus dem März gesehen
        wurden — und die Ersetzungskette steht auf dem Kopf.
        """
        with self._lock:
            rows = self._conn.execute(
                # Termine (Kalender) sind Rohmaterial zum Wiederfinden, keine
                # Vorlage für Vorschläge: Drei Jahre Kalender würden sonst
                # (Ältestes zuerst) die Verdichtung der Mails verdrängen.
                "SELECT document FROM episodes WHERE state = ? AND kind != ? "
                "ORDER BY COALESCE(occurred_at, recorded_at) ASC LIMIT ?",
                (EpisodeState.NEW.value, EpisodeKind.EVENT.value, limit),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def recent(self, days: int = 7, limit: int = 100,
               at: datetime | None = None) -> list[Episode]:
        cutoff = (at or now()) - timedelta(days=days)
        return [
            e for e in self.all_episodes(limit=limit * 4)
            if e.reference_time() >= cutoff
        ][:limit]

    def sender_episode_ids(self, account_id: str, address: str, limit: int = 500) -> tuple[list[str], bool]:
        """Aktuelle Mails genau dieses Absenders in genau diesem Konto, neueste zuerst.

        Die Textsuche in der Datenbank ist nur ein Vorfilter; jede Zeile wird
        danach an Herkunft, Konto und einziger Absenderadresse geprüft. Zweiter
        Wert: ob es mehr als ``limit`` solcher Mails gibt.
        """
        from email.utils import parseaddr
        address = address.strip().casefold()
        if not address or not account_id or any(ch in address for ch in '%_\\'):
            return [], False
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM episodes WHERE {sql_nachricht()} "
                "AND lower(document) LIKE ? ORDER BY COALESCE(occurred_at, recorded_at) DESC, id",
                (f'%{address}%',)).fetchall()
        found = []
        for row in rows:
            episode = self._from_row(row)
            ref = episode.provenance.source_ref
            if (episode.provenance.source_type is SourceType.EMAIL and isinstance(ref, str)
                    and ref.startswith(account_id + ':')
                    and parseaddr(_absender_text(episode.participants, episode.contacts))[1].casefold() == address):
                found.append(episode.id)
                if len(found) > limit:
                    return found[:limit], True
        return found, False

    def by_project(self, project_id: str, limit: int = 100) -> list[Episode]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM episodes WHERE project_id = ? "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def search(self, query: str, limit: int = 20) -> list[Episode]:
        pattern = f"%{query}%"
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM episodes WHERE title LIKE ? OR body LIKE ? "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC LIMIT ?",
                (pattern, pattern, limit),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def analysis_batch(self, after_id: str = "", limit: int = 100) -> list[Episode]:
        """Rohquellen in stabilen, begrenzten Seiten für unabhängige Analysen."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM episodes WHERE id > ? AND {sql_rohquelle()} "
                "ORDER BY id LIMIT ?",
                (after_id, max(1, min(limit, 200))),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def mentions(self, term: str, *, limit: int = 5000) -> tuple[list[dict[str, Any]], bool]:
        """Rohquellen, deren Titel, Text oder Beteiligte den Begriff als Wort enthalten.

        Für die erste Suchstufe: schnell, ohne Modell und ohne Suchindex, also
        auch für noch nicht eingeordnete Quellen. Ein Anhang wie in „Mainzer“
        zählt mit, ein längeres Wort wie „Mainzelmännchen“ nicht. Geliefert
        werden Kopfdaten und die ersten 400 Zeichen des Textes (`anfang`), nie
        der ganze Text. Mehr als `limit` Treffer werden als abgeschnitten
        gemeldet, nicht still verworfen. Neueste zuerst.
        """
        if not isinstance(term, str) or len(term.strip()) < 2:
            return [], False
        clean = term.strip()
        word = re.compile(r"(?<!\w)" + re.escape(clean) + r"(?:s|es|er|ern)?(?!\w)", re.I)
        # LIKE faltet Groß- und Kleinschreibung nur für ASCII: „öko“ soll „Öko“ finden.
        variants = list(dict.fromkeys([clean, clean.casefold(), clean.capitalize(), clean.upper()]
                                      if not clean.isascii() else [clean]))
        patterns = ["%" + v.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                    for v in variants]
        like = " OR ".join("title LIKE ? ESCAPE '\\' OR body LIKE ? ESCAPE '\\' "
                           "OR json_extract(document, '$.participants') LIKE ? ESCAPE '\\'" for _ in patterns)
        found: list[dict[str, Any]] = []
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, title, kind, occurred_at, recorded_at, project_id, body, "
                "json_extract(document, '$.participants'), "
                "json_extract(document, '$.provenance.source_type') "
                f"FROM episodes e WHERE {sql_geltend('e')} "
                # Eigene Suchfragen aus dem Gespräch sind keine Erwähnung, und
                # von einer mehrfach gelesenen Quelle zählt nur die aktuelle Fassung.
                "AND NOT EXISTS (SELECT 1 FROM json_each(e.document, '$.tags') AS tag WHERE tag.value = ?) "
                # Was der Nutzer selbst im Gespräch geschrieben hat, ist keine
                # Bedeutung des Begriffs, sondern seine eigene Frage.
                "AND json_extract(document, '$.provenance.source_type') != 'chat' "
                f"AND ({like}) "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC",
                (CHAT_LOOKUP_TAG, *[p for pattern in patterns for p in (pattern, pattern, pattern)]),
            )
            for row in cursor:
                participants = json.loads(row[7]) if row[7] else []
                where = [field for field, text in (("title", row[1]), ("participants", " ".join(participants)),
                                                   ("body", row[6])) if word.search(text or "")]
                if not where:
                    continue
                if len(found) == limit:
                    return found, True
                found.append({
                    "id": row[0], "title": row[1], "kind": row[2], "occurred_at": row[3],
                    "recorded_at": row[4], "project_id": row[5], "participants": participants,
                    "source_type": row[8], "matched_in": where,
                    # Nur der Anfang, für die Zuordnung eines Termins oder einer Notiz zu einer Bedeutung.
                    "anfang": (row[6] or "")[:400],
                })
        return found, False

    def usable_ids(self, ids: Iterable[str]) -> set[str]:
        """Welche dieser Episoden noch gelten: vorhanden, nicht ignoriert, aktuelle Fassung."""
        wanted = [value for value in dict.fromkeys(ids) if isinstance(value, str)]
        found: set[str] = set()
        with self._lock:
            for start in range(0, len(wanted), 500):
                chunk = wanted[start:start + 500]
                rows = self._conn.execute(
                    f"SELECT id FROM episodes WHERE id IN ({','.join('?' for _ in chunk)}) AND {sql_aktuell()}",
                    chunk).fetchall()
                found.update(row[0] for row in rows)
        return found

    def participants_for_addresses(self, addresses: Iterable[str], *, anzeigenamen: bool = False) -> dict[str, dict[str, Any]]:
        """Wie Mailadressen im Bestand als Beteiligte auftreten, in einem Durchgang.

        Je Adresse: die Schreibweisen mit Anzahl („Anna Keller <anna@x.de>“),
        der letzte Zeitpunkt und je Quelle ihr Projekt, damit eine Nachricht an
        mehrere Teilnehmer nur einmal zählt. Geprüft wird die Adresse genau,
        die Textsuche ist nur Vorfilter. Ein Durchgang für alle Adressen einer
        Anfrage, nicht einer je Teilnehmer. Mit `anzeigenamen` werden nur die
        Anzeigenamen ausgegeben; RFC-2047-Dekodierung gilt ausschließlich für
        Mailquellen. Die gespeicherten Beteiligten bleiben unverändert.
        """
        gesucht = sorted({mail_address(a) for a in addresses if mail_address(a)})
        ergebnis: dict[str, dict[str, Any]] = {a: {'namen': {}, 'zuletzt': None, 'quellen': {}} for a in gesucht}
        if not gesucht:
            return ergebnis
        muster = ['%' + a.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%' for a in gesucht]
        # In Paketen: Eine OR-Kette über tausende Adressen sprengt SQLite („Expression tree is too large“).
        # Eine Quelle, die mehrere Pakete trifft, zählt trotzdem nur einmal.
        rows: dict[str, tuple] = {}
        for start in range(0, len(muster), ADRESSEN_JE_ABFRAGE):
            teil = muster[start:start + ADRESSEN_JE_ABFRAGE]
            bedingung = ' OR '.join("lower(json_extract(document, '$.participants')) LIKE ? ESCAPE '\\'" for _ in teil)
            with self._lock:
                for zeile in self._conn.execute(
                        "SELECT id, json_extract(document, '$.participants'), COALESCE(occurred_at, recorded_at), project_id, "
                        "json_extract(document, '$.provenance.source_type') "
                        f"FROM episodes WHERE {sql_aktuell()} AND ({bedingung})", teil):
                    rows.setdefault(zeile[0], zeile)
        for episode_id, teilnehmer, zeit, projekt, art in rows.values():
            for wert in json.loads(teilnehmer or '[]'):
                adresse = mail_address(str(wert))
                if adresse not in ergebnis:
                    continue
                eintrag = ergebnis[adresse]
                name = str(wert).strip()
                if anzeigenamen:
                    from .kontakte import anzeigename
                    name = anzeigename(name, kopfzeile=art == "email") or adresse
                eintrag['namen'][name] = eintrag['namen'].get(name, 0) + 1
                eintrag['quellen'][episode_id] = projekt
                if zeit and (eintrag['zuletzt'] is None or zeit > eintrag['zuletzt']):
                    eintrag['zuletzt'] = zeit
        return ergebnis

    def participants_for_address(self, address: str, *, anzeigenamen: bool = False) -> list[dict[str, Any]]:
        """Die Schreibweisen einer Adresse, häufigste zuerst (für einzelne Abfragen)."""
        eintrag = self.participants_for_addresses([address], anzeigenamen=anzeigenamen).get(mail_address(address))
        if not eintrag:
            return []
        return [{'name': name, 'anzahl': anzahl} for name, anzahl
                in sorted(eintrag['namen'].items(), key=lambda item: (-item[1], item[0]))]

    def _beteiligte_zu(self, name: str) -> list[tuple[str, list[str], str]]:
        """Geltende Quellen, deren Beteiligte zur Angabe passen könnten (Vorfilter, neueste zuerst).

        Vorgefiltert wird nur über Wörter aus reinem ASCII: SQLite vergleicht
        Umlaute in `LIKE` nicht ohne Rücksicht auf Groß- und Kleinschreibung.
        Die genaue Prüfung macht der Aufrufer.
        """
        adresse = mail_address(name)
        woerter = [adresse] if adresse else [w for w in name.strip().casefold().replace(",", " ").split()
                                             if w.isascii()]
        if not adresse and not name.strip():
            return []
        bedingung = " AND ".join("lower(json_extract(document, '$.participants')) LIKE ? ESCAPE '\\'"
                                 for _ in woerter) or "1"
        if not adresse:
            # Kodierte Mailnamen sind im Rohtext nicht über ihren Namen auffindbar.
            # Sie sind nur Kandidaten; der anschließende Vergleich bleibt exakt.
            bedingung = f"({bedingung}) OR ({_KODIERTER_MAILNAME})"
        muster = ["%" + w.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%" for w in woerter]
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, json_extract(document, '$.participants'), "
                "json_extract(document, '$.provenance.source_type') FROM episodes "
                f"WHERE {sql_aktuell()} AND ({bedingung}) "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC, id", muster).fetchall()
        return [(row[0], [str(v) for v in json.loads(row[1] or '[]')], row[2]) for row in rows]

    def reference_times(self, episode_ids: list[str]) -> list[datetime]:
        """Die fachlichen Zeitpunkte (Ereignis, sonst Aufnahme) der genannten Quellen, ohne sie zu laden."""
        zeiten: list[datetime] = []
        ids = list(dict.fromkeys(episode_ids))
        with self._lock:
            for start in range(0, len(ids), 500):
                chunk = ids[start:start + 500]
                rows = self._conn.execute(
                    f"SELECT COALESCE(occurred_at, recorded_at) FROM episodes WHERE id IN ({','.join('?' for _ in chunk)})",
                    chunk).fetchall()
                zeiten += [ensure_aware(_parse(row[0])) for row in rows if row[0]]
        return zeiten

    def participants_containing(self, woerter: list[str], *, mit_herkunft: bool = False) -> list:
        """Geltende Quellen, deren Beteiligte eines der Wörter enthalten, mit ihren Beteiligten.

        Ein Durchgang für alle Wörter einer Frage. Nur Vorfilter: Wörter mit
        Umlauten oder Sonderzeichen werden ohne Rücksicht auf Groß- und
        Kleinschreibung nur für ASCII verglichen; die genaue Prüfung macht der
        Aufrufer. Mit `mit_herkunft` trägt jeder Rückgabeeintrag zusätzlich den
        Quellentyp; kodierte Mailnamen werden dann ebenfalls als Kandidaten gelesen.
        """
        muster = ["%" + w.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
                  for w in woerter if w.strip()]
        if not muster:
            return []
        bedingung = " OR ".join("lower(json_extract(document, '$.participants')) LIKE ? ESCAPE '\\'"
                                for _ in muster)
        if mit_herkunft:
            bedingung = f"({bedingung}) OR ({_KODIERTER_MAILNAME})"
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, json_extract(document, '$.participants'), "
                "json_extract(document, '$.provenance.source_type') FROM episodes "
                f"WHERE {sql_aktuell()} AND ({bedingung}) "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC, id", muster).fetchall()
        return [(row[0], [str(v) for v in json.loads(row[1] or '[]')], row[2]) if mit_herkunft
                else (row[0], [str(v) for v in json.loads(row[1] or '[]')]) for row in rows]

    def participant_ids(self, name: str) -> list[str]:
        """Geltende Quellen, an denen genau diese Person beteiligt ist.

        Dieselbe Regel wie im Personenverzeichnis (`identitaet.py`): Eine Adresse
        trifft alle Quellen dieser Adresse, gleich unter welchem Namen. Ein Name
        trifft jeden Beteiligten, der ihn als Anzeigenamen trägt („Keller, Anna“
        wie „Anna Keller“). Gehört der Name mehreren Adressen, prüft der
        Aufrufer das mit `addresses_for_name`. Ohne die Episoden zu laden; die
        Textsuche ist nur Vorfilter.
        """
        from .identitaet import name_schluessel
        from .kontakte import anzeigename
        adresse = mail_address(name)
        gesucht = name_schluessel(name)
        gefunden = []
        for episode_id, teilnehmer, art in self._beteiligte_zu(name):
            for wert in teilnehmer:
                if adresse:
                    passt = mail_address(wert) == adresse
                else:
                    text = anzeigename(wert, kopfzeile=art == "email") if mail_address(wert) else wert
                    passt = name_schluessel(text) == gesucht
                if passt:
                    gefunden.append(episode_id)
                    break
        return gefunden

    def addresses_for_name(self, name: str) -> list[str]:
        """Die Adressen, unter denen ein Anzeigename vorkommt (mehr als eine: zwei Menschen)."""
        from .identitaet import name_schluessel
        from .kontakte import anzeigename
        gesucht = name_schluessel(name)
        adressen = set()
        for _, teilnehmer, art in self._beteiligte_zu(name):
            for wert in teilnehmer:
                adresse = mail_address(wert)
                if adresse and name_schluessel(anzeigename(wert, kopfzeile=art == "email")) == gesucht:
                    adressen.add(adresse)
        return sorted(adressen)

    def project_heads(self, project_id: str, *, limit: int = -1) -> list[dict[str, Any]]:
        """Kopfdaten der geltenden Quellen eines Projekts, neueste zuerst, ohne Text."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, occurred_at, recorded_at FROM episodes WHERE project_id = ? "
                f"AND {sql_geltend()} "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC, id LIMIT ?",
                (project_id, limit)).fetchall()
        return [{"id": row[0], "occurred_at": row[1], "recorded_at": row[2]} for row in rows]

    def each_episode(self, *, page: int = 500) -> Iterator[Episode]:
        """Alle Episoden, seitenweise gelesen, ohne Obergrenze.

        Für Ansichten, die den ganzen Bestand abbilden müssen (Graph, Akten,
        Personenverzeichnis). Eine feste Obergrenze ließe ältere Quellen still
        herausfallen; eine Liste aller Episoden hielte bei Jahren an Mail zu
        viel auf einmal im Speicher. Die Reihenfolge ist die der Aufnahme;
        wer eine zeitliche Ordnung braucht, sortiert das Ergebnis selbst.
        """
        after = 0
        size = max(1, int(page))
        while True:
            with self._lock:
                rows = self._conn.execute(
                    "SELECT rowid, document FROM episodes WHERE rowid > ? ORDER BY rowid LIMIT ?",
                    (after, size),
                ).fetchall()
            if not rows:
                return
            after = rows[-1][0]
            for row in rows:
                yield self._from_row({"document": row[1]})

    def each_geltende(self, *, page: int = 500) -> Iterator[Episode]:
        """Alle geltenden Episoden (nicht ignoriert, aktuelle Fassung), seitenweise gelesen.

        Wie `each_episode`, aber ohne entzogene, ignorierte und überholte Fassungen. Die Sperre
        gilt nur je Seite, nie über den ganzen Bestand.
        """
        after = 0
        size = max(1, int(page))
        while True:
            with self._lock:
                rows = self._conn.execute(
                    f"SELECT rowid, document FROM episodes WHERE rowid > ? AND {sql_aktuell()} ORDER BY rowid LIMIT ?",
                    (after, size)).fetchall()
            if not rows:
                return
            after = rows[-1][0]
            for row in rows:
                yield self._from_row({"document": row[1]})

    def geltender_stand(self) -> tuple[int, int, int, int]:
        """Kennung der geltenden Quellen: ändert sich bei neuer Fassung, Entzug, Wiedereröffnung und Nachtrag.

        (Anzahl, größte Zeilennummer, Summe der Zeilennummern, Summe der Stützgenerationen) über die
        geltenden Episoden. `ignore` senkt die Anzahl, `add_contacts` erhöht die Stützgeneration, eine
        neue Fassung erhöht die größte Zeilennummer.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*), COALESCE(MAX(rowid), 0), COALESCE(SUM(rowid), 0), COALESCE(SUM(support_generation), 0) "
                f"FROM episodes WHERE {sql_aktuell()}").fetchone()
        return (row[0], row[1], row[2], row[3])

    def all_episodes(self, limit: int = 500) -> list[Episode]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM episodes "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._from_row(r) for r in rows]

    def geltende_zuletzt(self, kind: EpisodeKind, *, limit: int = 400) -> list[Episode]:
        """Geltende Quellen dieser Art (nicht ignoriert, aktuelle Fassung), jüngste zuerst.

        Anders als `all_episodes` liefert das nie eine entzogene, ignorierte oder überholte
        Fassung: Ansichten für den Nutzer lesen nur, was noch gilt.
        """
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM episodes WHERE kind = ? AND {sql_aktuell()} "
                "ORDER BY COALESCE(occurred_at, recorded_at) DESC LIMIT ?",
                (kind.value, limit)).fetchall()
        return [self._from_row(r) for r in rows]

    def events_between(self, von: datetime, bis: datetime, *, limit: int = 2000) -> list[Episode]:
        """Geltende Termine (Art `event`, nicht ausgeschlossen), deren Beginn in [von, bis] liegt.

        Der Vergleich läuft über `datetime()` von SQLite, das den Zeitversatz der
        gespeicherten Angabe einrechnet; ein Textvergleich wäre bei
        unterschiedlichen Versätzen falsch.
        """
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM episodes WHERE kind = ? AND {sql_nicht_ignoriert()} AND occurred_at IS NOT NULL "
                "AND datetime(occurred_at) BETWEEN datetime(?) AND datetime(?) "
                "ORDER BY datetime(occurred_at) LIMIT ?",
                (EpisodeKind.EVENT.value,
                 ensure_aware(von).isoformat(), ensure_aware(bis).isoformat(), limit)).fetchall()
        return [self._from_row(row) for row in rows]

    def tagged(self, tag: str, *, kind: EpisodeKind = EpisodeKind.DOCUMENT, limit: int = 5000) -> list[Episode]:
        """Geltende Quellen der Art `kind` mit dieser Marke (etwa `transkript`), neueste zuerst."""
        with self._lock:
            rows = self._conn.execute(
                f"SELECT document FROM episodes WHERE kind = ? AND {sql_nicht_ignoriert()} AND EXISTS "
                "(SELECT 1 FROM json_each(episodes.document, '$.tags') WHERE value = ?) "
                "ORDER BY recorded_at DESC, id DESC LIMIT ?",
                (kind.value, tag, limit)).fetchall()
        return [self._from_row(row) for row in rows]

    def uploaded_documents(self, *, offset: int = 0, limit: int = 50) -> list[Episode]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT document FROM episodes WHERE kind = ? "
                "AND json_extract(document, '$.provenance.source_type') = ? "
                "AND substr(json_extract(document, '$.provenance.source_ref'), 1, 7) = 'upload:' "
                "ORDER BY recorded_at DESC, id DESC LIMIT ? OFFSET ?",
                (EpisodeKind.DOCUMENT.value, SourceType.DOCUMENT.value, limit, offset),
            ).fetchall()
        return [self._from_row(row) for row in rows]

    def neue_von_aussen(self) -> int:
        """Neue, noch ungesichtete Quellen, die nicht vom Nutzer selbst stammen: Mails, Termine, Mitschriften, Dateien
        aus freigegebenen Ordnern.

        Nicht dabei sind die eigenen Zeilen im Gespräch mit Kingfisher, eigene Angaben, Korrekturen, Abgeleitetes und
        Dateien, die der Nutzer eben selbst hochgeladen hat (Fremdprobe 2, Befund 22): Das sind keine „relevanten
        Nachrichten“; er kennt sie schon.
        """
        with self._lock:
            zeile = self._conn.execute(
                "SELECT COUNT(*) FROM episodes WHERE state = ? "
                f"AND json_extract(document, '$.provenance.source_type') NOT IN ({_sql_liste(EIGENE_HERKUNFT)}) "
                "AND substr(COALESCE(json_extract(document, '$.provenance.source_ref'), ''), 1, 7) != 'upload:'",
                (EpisodeState.NEW.value,)).fetchone()
        return int(zeile[0])

    def counts(self) -> dict[str, int]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT state, COUNT(*) AS n FROM episodes GROUP BY state"
            ).fetchall()
        return {r["state"]: r["n"] for r in rows}

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- Intern ------------------------------------------------------------

    def transaction(self):
        return sqlite_transaction(self._conn, self._lock)

    def support_snapshot(self, episode_id):
        from .source_snapshot import read_snapshot
        with self._lock:
            return read_snapshot(self._conn, episode_id, self._from_row)

    def belegbarer_snapshot(self, episode_id: str, *, max_bytes: int | None = None):
        """Stand einer Quelle, wenn sie als Beleg taugt; sonst `None`.

        Tauglich ist die geltende Fassung einer Rohquelle, die weder eine eigene Suchfrage des
        Gesprächs ist noch selbst abgeleitete Aussagen trägt. Eine Quelle über `max_bytes` (Größe des
        Dokuments) gilt als nicht tauglich; ein unstimmiger Bestand wirft ValueError wie `read_snapshot`.
        """
        from .source_snapshot import read_snapshot
        with self._lock:
            snapshot = read_snapshot(self._conn, episode_id, self._from_row, max_bytes=max_bytes)
            if (snapshot is None or not snapshot.current()
                    or snapshot.episode.kind not in QUELLEN_ARTEN
                    or CHAT_LOOKUP_TAG in snapshot.episode.tags
                    or snapshot.episode.produced
                    or self._conn.execute('SELECT 1 FROM episode_produced_assertions WHERE episode_id=? LIMIT 1',
                                          (episode_id,)).fetchone()):
                return None
            return snapshot

    def quellen_kopf(self, limit: int = 2000) -> tuple[int, list[dict[str, Any]]]:
        """Zahl aller Rohquellen und die Kopfdaten der jüngsten `limit` (ohne Volltext).

        Je Quelle `id`, `digest`, `state` und `source_truncated` (1, wenn der Text gekürzt aufgenommen
        wurde). Ausgeschlossene und archivierte sind dabei, der Aufrufer zählt sie getrennt.
        """
        with self._lock:
            gesamt = self._conn.execute(f"SELECT COUNT(*) FROM episodes WHERE {sql_quelle()}").fetchone()[0]
            zeilen = self._conn.execute(
                "SELECT id,digest,state,EXISTS(SELECT 1 FROM json_each(episodes.document,'$.tags') "
                "WHERE value='source:truncated') AS source_truncated,support_generation,metadata_digest "
                f"FROM episodes WHERE {sql_quelle()} "
                "ORDER BY recorded_at DESC,id LIMIT ?", (limit,)).fetchall()
        return gesamt, [{"id": z[0], "digest": z[1], "state": z[2], "source_truncated": z[3],
                         "support_generation": z[4], "metadata_digest": z[5]} for z in zeilen]

    def termine_nach_herkunft(self, muster: str) -> list[tuple[str, str, str | None]]:
        """(Id, Text, Herkunftsangabe) geltender Termine, deren Herkunft auf das LIKE-Muster passt.

        Das Muster gilt für `provenance.source_ref` und ist bereits maskiert (`ESCAPE '\\'`).
        """
        with self._lock:
            zeilen = self._conn.execute(
                "SELECT id, body, json_extract(document, '$.provenance.source_ref') FROM episodes "
                f"WHERE kind = 'event' AND {sql_aktuell()} AND "
                "json_extract(document, '$.provenance.source_ref') LIKE ? ESCAPE '\\'", (muster,)).fetchall()
        return [(z[0], z[1], z[2]) for z in zeilen]

    def nachrichten_mit_text(self, text: str, *, ausser: str, limit: int) -> list[Episode]:
        """Andere, nicht ausgeschlossene Nachrichten, deren Dokument den Text (ohne Groß-/Kleinschreibung) enthält, neueste zuerst."""
        with self._lock:
            zeilen = self._conn.execute(
                f"SELECT document FROM episodes WHERE {sql_nachricht()} AND id!=? "
                "AND lower(document) LIKE ? ORDER BY COALESCE(occurred_at, recorded_at) DESC, id LIMIT ?",
                (ausser, f"%{text}%", limit)).fetchall()
        return [self._from_row(z) for z in zeilen]

    def quellen_mit_aussagen_ab(self, nach: str, limit: int) -> list[str]:
        """Ids von Aussagen, zu denen Quellen Belege tragen, aufsteigend nach `nach`."""
        with self._lock:
            return [r[0] for r in self._conn.execute(
                'SELECT DISTINCT assertion_id FROM episode_produced_assertions WHERE assertion_id>? '
                'ORDER BY assertion_id LIMIT ?', (nach, limit))]

    def produced_support_links(self, assertion_id):
        with self._lock:
            return [r[0] for r in self._conn.execute(
                'SELECT episode_id FROM episode_produced_assertions WHERE assertion_id=? LIMIT 2', (assertion_id,))]

    def _put(self, episode: Episode, *, source_key: str = "", _reopen=False) -> None:
        d = episode.to_dict()
        with self.transaction():
            old = self._conn.execute('SELECT state,source_key FROM episodes WHERE id=?', (episode.id,)).fetchone()
            if old:
                if old[0] == 'ignored' and episode.state is not EpisodeState.IGNORED and not _reopen:
                    raise EpisodeError('An ignored source requires explicit reopen')
                # Zustandsgründe ergänzen Tags; deren Digest muss zum Dokument
                # passen. Der gespeicherte Quellenschlüssel bleibt unverändert.
                self._conn.execute('UPDATE episodes SET state=?,project_id=?,document=?,metadata_digest=? WHERE id=?',
                    (d['state'],d['project_id'],json.dumps(d,ensure_ascii=False),
                     source_metadata_digest(d) if old[1] else '',d['id']))
            else:
                self._conn.execute('INSERT INTO episodes (id,digest,kind,state,recorded_at,occurred_at,project_id,title,body,document,source_key,metadata_digest) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                    (d['id'],d['digest'],d['kind'],d['state'],d['recorded_at'],d['occurred_at'],d['project_id'],d['title'],d['body'],json.dumps(d,ensure_ascii=False),source_key,source_metadata_digest(d) if source_key else ''))
            # Der Suchindex folgt jedem Zustandswechsel (ignoriert, wieder geöffnet, neu aufgenommen).
            source_index.synchronisieren(self._conn, d['id'])

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Episode:
        d = json.loads(row["document"])
        p = d["provenance"]
        return Episode(
            id=d["id"],
            kind=EpisodeKind(d["kind"]),
            title=d["title"],
            body=d["body"],
            provenance=Provenance(
                source_type=SourceType(p["source_type"]),
                source_ref=p.get("source_ref"),
                captured_at=_parse(p.get("captured_at")),
                extracted_by=p.get("extracted_by"),
                verbatim=p.get("verbatim"),
            ),
            recorded_at=_parse(d["recorded_at"]),  # type: ignore[arg-type]
            digest=d["digest"],
            occurred_at=_parse(d.get("occurred_at")),
            state=EpisodeState(d["state"]),
            project_id=d.get("project_id"),
            participants=list(d.get("participants", [])),
            contacts=[dict(c) for c in d.get("contacts", [])],
            produced=list(d.get("produced", [])),
            consolidated_at=_parse(d.get("consolidated_at")),
            tags=list(d.get("tags", [])),
            # Mit Vorgabe gelesen: Episoden, die vor der Zusammenfassungsschicht
            # entstanden sind, haben diese Felder nicht — und sollen deshalb
            # nicht unlesbar werden.
            covers=list(d.get("covers", [])),
            period=str(d.get("period", "")),
        )


__all__ = [
    "Episode",
    "EpisodeError",
    "EpisodeKind",
    "EpisodeState",
    "EpisodeStore",
    "ROHQUELLEN",
    "digest_of",
]
