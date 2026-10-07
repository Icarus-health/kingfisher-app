"""Tests für Sicherung, Wiederherstellung und Schlüsselbund."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from icarus_memory import Kind, Provenance, SelfModelStore, SourceType, SqliteBackend
from icarus_memory.backup import (
    BackupError,
    export_model,
    import_model,
    list_snapshots,
    restore,
    restore_all,
    snapshot,
    snapshot_all,
    verify_snapshot_set,
)
from icarus_memory.conversations import ConversationStore
from icarus_memory.model import now
from icarus_memory.regeln import RegelStore
from icarus_memory.secrets import KNOWN, Keychain, load_into_env, migrate_env_file


@pytest.fixture
def befuellte_db(tmp_path: Path) -> Path:
    path = tmp_path / "self-model.sqlite3"
    backend = SqliteBackend(path)
    store = SelfModelStore(backend, subject_id="test")
    alt = store.record("Wohnt in Hamburg.", Kind.STATE,
                       Provenance(source_type=SourceType.CHAT, source_ref="chat:1"))
    store.record("Wohnt in Leipzig.", Kind.STATE,
                 Provenance(source_type=SourceType.EMAIL), supersedes=[alt.id])
    backend.close()
    return path


# -- Snapshots -------------------------------------------------------------


def test_snapshot_ist_vollstaendig(befuellte_db: Path, tmp_path: Path) -> None:
    ziel = snapshot(befuellte_db, tmp_path / "sicherungen")
    assert ziel.is_file()

    # Der Snapshot muss für sich allein lesbar sein.
    store = SelfModelStore(SqliteBackend(ziel), subject_id="test")
    assert [a.statement for a in store.usable()] == ["Wohnt in Leipzig."]
    # Und die Ersetzungskette muss mitgekommen sein.
    assert len(store.export().assertions) == 2


def test_snapshot_waehrend_schreibzugriff(befuellte_db: Path, tmp_path: Path) -> None:
    """Offene Verbindung: ein blosses Dateikopieren ergäbe hier Bruch."""
    backend = SqliteBackend(befuellte_db)
    store = SelfModelStore(backend, subject_id="test")
    store.record("Noch was.", Kind.EPISODE, Provenance(source_type=SourceType.CHAT))

    ziel = snapshot(befuellte_db, tmp_path / "sicherungen")
    conn = sqlite3.connect(str(ziel))
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    conn.close()
    backend.close()


def test_rotation_haelt_die_anzahl(befuellte_db: Path, tmp_path: Path) -> None:
    ordner = tmp_path / "sicherungen"
    basis = now()
    for i in range(8):
        snapshot(befuellte_db, ordner, keep=3, at=basis + timedelta(minutes=i))
    assert len(list_snapshots(ordner)) == 3


def test_vollstaendiger_snapshot_sichert_gespraeche_und_einstellungen(tmp_path: Path) -> None:
    """Die tägliche Sicherung darf nicht am Selbstmodell enden."""
    data_dir = tmp_path / "daten"
    backend = SqliteBackend(data_dir / "self-model.sqlite3")
    model = SelfModelStore(backend, subject_id="test")
    model.record("Vor der Sicherung.", Kind.IDENTITY,
                 Provenance(source_type=SourceType.CHAT))
    conversations = ConversationStore(data_dir / "conversations.sqlite3")
    conversation = conversations.create("Wichtig")
    conversations.add_message(conversation.id, "user", "Die erste Frage")
    (data_dir / "einstellungen.json").write_text('{"provider": "ollama"}', encoding="utf-8")

    snapshot_path = snapshot_all(data_dir, data_dir / "sicherungen")
    verified = verify_snapshot_set(snapshot_path)
    assert {entry["name"] for entry in verified} >= {
        "self-model.sqlite3", "conversations.sqlite3", "einstellungen.json"
    }

    model.record("Nach der Sicherung.", Kind.IDENTITY,
                 Provenance(source_type=SourceType.CHAT))
    conversations.add_message(conversation.id, "assistant", "Eine neue Antwort")
    (data_dir / "einstellungen.json").write_text('{"provider": "openai"}', encoding="utf-8")
    backend.close()
    conversations.close()

    aside = restore_all(snapshot_path, data_dir)

    restored_model = SelfModelStore(SqliteBackend(data_dir / "self-model.sqlite3"), subject_id="test")
    restored_conversations = ConversationStore(data_dir / "conversations.sqlite3")
    assert {assertion.statement for assertion in restored_model.export().assertions} == {"Vor der Sicherung."}
    assert [message.content for message in restored_conversations.messages(conversation.id)] == ["Die erste Frage"]
    assert (data_dir / "einstellungen.json").read_text(encoding="utf-8") == '{"provider": "ollama"}'
    assert any(path.name.startswith("self-model.vor-wiederherstellung-") for path in aside)
    restored_conversations.close()


def test_restore_liest_wal_snapshot_aus_nicht_schreibbarem_ordner(tmp_path: Path) -> None:
    if os.name != "posix" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("Benötigt einen nicht privilegierten POSIX-Prozess für echte Read-only-Rechte")
    data_dir = tmp_path / "live"
    rules = RegelStore(data_dir / "regeln.sqlite3")
    rules.close()
    snapshot_path = snapshot_all(data_dir, tmp_path / "backups")
    database = snapshot_path / "regeln.sqlite3"
    connection = sqlite3.connect(database)
    assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    connection.close()
    assert not Path(str(database) + "-wal").exists()
    assert not Path(str(database) + "-shm").exists()

    for path in snapshot_path.iterdir():
        path.chmod(0o444 if path.is_file() else 0o555)
    snapshot_path.chmod(0o555)
    try:
        restored = tmp_path / "restored"
        restore_all(snapshot_path, restored)
        assert (restored / "regeln.sqlite3").is_file()
    finally:
        snapshot_path.chmod(0o755)
        for path in snapshot_path.iterdir():
            path.chmod(0o644 if path.is_file() else 0o755)


def test_vollrestore_akzeptiert_aeltere_unversionierte_schema_version(tmp_path: Path) -> None:
    daten = tmp_path / "daten"
    backend = SqliteBackend(daten / "self-model.sqlite3")
    SelfModelStore(backend, subject_id="test").record(
        "Aelterer Snapshot.", Kind.IDENTITY,
        Provenance(source_type=SourceType.CHAT),
    )
    snapshot_path = snapshot_all(daten, tmp_path / "snapshot-speicher")
    backend.close()

    source = sqlite3.connect(snapshot_path / "self-model.sqlite3")
    source.execute("PRAGMA user_version = 0")
    source.commit()
    source.close()
    manifest = json.loads((snapshot_path / "manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["files"] if item["name"] == "self-model.sqlite3")
    entry["sha256"] = hashlib.sha256((snapshot_path / "self-model.sqlite3").read_bytes()).hexdigest()
    (snapshot_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    restore_all(snapshot_path, daten)

    restored = SelfModelStore(SqliteBackend(daten / "self-model.sqlite3"), subject_id="test")
    assert {item.statement for item in restored.export().assertions} == {"Aelterer Snapshot."}


def test_beschaedigter_vollsnapshot_laesst_bestand_unberuehrt(tmp_path: Path) -> None:
    data_dir = tmp_path / "daten"
    backend = SqliteBackend(data_dir / "self-model.sqlite3")
    model = SelfModelStore(backend, subject_id="test")
    model.record("Der Bestand bleibt.", Kind.IDENTITY,
                 Provenance(source_type=SourceType.CHAT))
    snapshot_path = snapshot_all(data_dir, data_dir / "sicherungen")
    (snapshot_path / "self-model.sqlite3").write_bytes(b"changed")
    backend.close()

    with pytest.raises(BackupError, match="fehlt oder wurde verändert"):
        restore_all(snapshot_path, data_dir)

    retained = SelfModelStore(SqliteBackend(data_dir / "self-model.sqlite3"), subject_id="test")
    assert {assertion.statement for assertion in retained.export().assertions} == {"Der Bestand bleibt."}


@pytest.mark.parametrize("invalid_version", [-1, 999])
def test_vollrestore_lehnt_ungueltige_schema_version_vor_dem_austausch_ab(
    tmp_path: Path, invalid_version: int
) -> None:
    daten = tmp_path / "daten"
    backend = SqliteBackend(daten / "self-model.sqlite3")
    SelfModelStore(backend, subject_id="test").record(
        "Aktueller Bestand.", Kind.IDENTITY,
        Provenance(source_type=SourceType.CHAT),
    )
    snapshot_path = snapshot_all(daten, tmp_path / "snapshot-speicher")
    backend.close()

    source = sqlite3.connect(snapshot_path / "self-model.sqlite3")
    source.execute(f"PRAGMA user_version = {invalid_version}")
    source.commit()
    source.close()
    # Die Prüfsumme stimmt zum Snapshotinhalt; nur die Versionskompatibilität
    # soll den Restore verhindern.
    manifest = json.loads((snapshot_path / "manifest.json").read_text(encoding="utf-8"))
    manifest_entry = next(item for item in manifest["files"] if item["name"] == "self-model.sqlite3")
    manifest_entry["sha256"] = hashlib.sha256((snapshot_path / "self-model.sqlite3").read_bytes()).hexdigest()
    (snapshot_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(BackupError, match="nicht unterstützte Schema-Version"):
        restore_all(snapshot_path, daten)

    retained = SelfModelStore(SqliteBackend(daten / "self-model.sqlite3"), subject_id="test")
    assert {item.statement for item in retained.export().assertions} == {"Aktueller Bestand."}
    assert not list(daten.glob("*.vor-wiederherstellung-*"))


def test_vollstaendiger_restore_entfernt_spaeter_hinzugekommene_einstellungen(tmp_path: Path) -> None:
    data_dir = tmp_path / "daten"
    backend = SqliteBackend(data_dir / "self-model.sqlite3")
    SelfModelStore(backend, subject_id="test")
    snapshot_path = snapshot_all(data_dir, data_dir / "sicherungen")
    (data_dir / "einstellungen.json").write_text('{"provider": "openai"}', encoding="utf-8")
    backend.close()

    aside = restore_all(snapshot_path, data_dir)

    assert not (data_dir / "einstellungen.json").exists()
    assert any(path.name.startswith("einstellungen.vor-wiederherstellung-") for path in aside)


# -- Wiederherstellung -----------------------------------------------------


def test_wiederherstellung_legt_den_alten_stand_beiseite(
    befuellte_db: Path, tmp_path: Path
) -> None:
    ziel = snapshot(befuellte_db, tmp_path / "sicherungen")

    # Nach dem Snapshot etwas hinzufügen, das verloren gehen soll.
    backend = SqliteBackend(befuellte_db)
    SelfModelStore(backend, subject_id="test").record(
        "Nach der Sicherung.", Kind.EPISODE, Provenance(source_type=SourceType.CHAT))
    backend.close()

    restore(ziel, befuellte_db)

    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    aussagen = [a.statement for a in store.export().assertions]
    assert "Nach der Sicherung." not in aussagen

    # Der überschriebene Stand ist nicht weg, sondern beiseitegelegt.
    beiseite = list(befuellte_db.parent.glob("*vor-wiederherstellung*"))
    assert len(beiseite) == 1


def test_einzelrestore_lehnt_zukuenftiges_schema_vor_dem_austausch_ab(
    befuellte_db: Path, tmp_path: Path
) -> None:
    ziel = snapshot(befuellte_db, tmp_path / "sicherungen")
    source = sqlite3.connect(ziel)
    source.execute("PRAGMA user_version = 999")
    source.commit()
    source.close()

    with pytest.raises(BackupError, match="nicht unterstützte Schema-Version"):
        restore(ziel, befuellte_db)

    retained = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    assert {item.statement for item in retained.export().assertions} == {
        "Wohnt in Hamburg.", "Wohnt in Leipzig."
    }
    assert not list(befuellte_db.parent.glob("*.vor-wiederherstellung-*.sqlite3"))


def test_beschaedigter_snapshot_wird_abgelehnt(tmp_path: Path) -> None:
    kaputt = tmp_path / "kaputt.sqlite3"
    kaputt.write_bytes(b"das ist keine datenbank")
    with pytest.raises(BackupError, match="nicht lesbar|beschädigt"):
        restore(kaputt, tmp_path / "ziel.sqlite3")


def test_fehlender_snapshot(tmp_path: Path) -> None:
    with pytest.raises(BackupError, match="Kein Snapshot"):
        restore(tmp_path / "gibtsnicht.sqlite3", tmp_path / "ziel.sqlite3")


# -- Export ----------------------------------------------------------------


def test_export_ohne_passphrase_ist_lesbar(befuellte_db: Path) -> None:
    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    payload = export_model(store.export().to_dict())

    wieder = json.loads(payload)
    assert wieder["schema_version"] == "0.1.0"
    assert len(wieder["assertions"]) == 2


def test_export_mit_passphrase_und_rueckweg(befuellte_db: Path) -> None:
    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    original = store.export().to_dict()

    payload = export_model(original, passphrase="ein gutes langes Passwort")
    # Der Klartext darf nirgends durchscheinen.
    assert "Leipzig" not in payload
    assert "Hamburg" not in payload

    zurueck = import_model(payload, passphrase="ein gutes langes Passwort")
    assert zurueck == original


def test_falsche_passphrase_wird_erkannt(befuellte_db: Path) -> None:
    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    payload = export_model(store.export().to_dict(), passphrase="richtig")
    with pytest.raises(BackupError, match="Prüfsumme"):
        import_model(payload, passphrase="falsch")


def test_veraenderter_export_wird_erkannt(befuellte_db: Path) -> None:
    """Ohne Authentifizierung liesse sich der Inhalt unbemerkt verändern."""
    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    payload = export_model(store.export().to_dict(), passphrase="geheim")

    document = json.loads(payload)
    data = bytearray(__import__("base64").b64decode(document["data"]))
    data[0] ^= 0xFF
    document["data"] = __import__("base64").b64encode(bytes(data)).decode()

    with pytest.raises(BackupError, match="Prüfsumme"):
        import_model(json.dumps(document), passphrase="geheim")


def test_verschluesselter_export_ohne_passphrase(befuellte_db: Path) -> None:
    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    payload = export_model(store.export().to_dict(), passphrase="geheim")
    with pytest.raises(BackupError, match="Passphrase erforderlich"):
        import_model(payload)


def test_export_bleibt_schemakonform(befuellte_db: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    store = SelfModelStore(SqliteBackend(befuellte_db), subject_id="test")
    wieder = import_model(export_model(store.export().to_dict(), passphrase="p"), passphrase="p")

    schema_path = Path(__file__).resolve().parents[2] / "schema" / "self-model.schema.json"
    jsonschema.Draft202012Validator(
        json.loads(schema_path.read_text(encoding="utf-8"))
    ).validate(wieder)


# -- Schlüsselbund ---------------------------------------------------------


def test_ohne_speicher_kein_absturz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Auf einem System ohne Schlüsselspeicher muss alles weiterlaufen."""
    monkeypatch.setattr(Keychain, "_detect", staticmethod(lambda: "none"))
    kc = Keychain()
    assert not kc.available
    assert kc.get("OPENAI_API_KEY") is None
    assert load_into_env(kc) == []


def test_umgebung_gewinnt_gegen_schluesselbund(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sonst liesse sich ein hinterlegter Schlüssel nicht übersteuern."""
    class Fake(Keychain):
        def __init__(self) -> None:
            self._service = "test"
            self._backend = "macos"

        def get(self, name: str) -> str | None:
            return "aus-dem-schluesselbund"

    monkeypatch.setenv("OPENAI_API_KEY", "aus-der-umgebung")
    try:
        load_into_env(Fake())
        assert os.environ["OPENAI_API_KEY"] == "aus-der-umgebung"
    finally:
        # `load_into_env` füllt **alle** bekannten Namen, nicht nur den
        # geprüften. Ohne dieses Aufräumen bleiben die übrigen für den Rest des
        # Laufs gesetzt, und eine spätere Testdatei sieht einen eingerichteten
        # Anbieter, den sie nie gesetzt hat — und scheitert an einer Stelle, die
        # nichts damit zu tun hat.
        #
        # Nicht über `monkeypatch.delenv`: Das merkt sich nichts, wenn der Name
        # vorher gar nicht gesetzt war, und stellt danach folglich auch nichts
        # her. Genau der Fall, der hier vorliegt.
        for name in KNOWN:
            if name != "OPENAI_API_KEY":
                os.environ.pop(name, None)


def test_migration_uebernimmt_nur_bekannte_schluessel(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "# Kommentar\n"
        'OPENAI_API_KEY="sk-test"\n'
        "IRGENDWAS_ANDERES=egal\n"
        "ANTHROPIC_API_KEY=\n",
        encoding="utf-8",
    )
    gespeichert: dict[str, str] = {}

    class Fake(Keychain):
        def __init__(self) -> None:
            self._service = "test"
            self._backend = "macos"

        def set(self, name: str, value: str) -> None:
            gespeichert[name] = value

    assert migrate_env_file(env, Fake()) == ["OPENAI_API_KEY"]
    assert gespeichert == {"OPENAI_API_KEY": "sk-test"}
    # Die Datei bleibt liegen — ungefragt Dateien des Nutzers zu verändern
    # wäre schlimmer als ein Schlüssel, der einen Tag zu lang dort steht.
    assert env.is_file()


def test_calendar_action_journal_survives_backup_and_restore(tmp_path):
    """A restored application must retain its external-action confirmations."""
    data = tmp_path / 'data'
    data.mkdir()
    path = data / 'calendar-actions.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE actions (id TEXT PRIMARY KEY, status TEXT, record TEXT)')
        db.execute('INSERT INTO actions VALUES (?, ?, ?)', ('draft-1', 'done', '{"provider_event_id":"event-1"}'))
    saved = snapshot_all(data, tmp_path / 'snapshots')
    assert 'calendar-actions.sqlite3' in {item['name'] for item in verify_snapshot_set(saved)}
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM actions')
    restore_all(saved, data)
    with sqlite3.connect(path) as db:
        assert db.execute('SELECT id, status FROM actions').fetchall() == [('draft-1', 'done')]
