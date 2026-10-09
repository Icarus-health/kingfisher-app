"""Synthetic tests for refreshing mail-name identity projections safely."""
from dataclasses import replace
from datetime import timedelta

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType
from icarus_memory.akten import Akten
from icarus_memory.bezuege import Bezuege, Register
from icarus_memory.identitaet import Nennung, Verzeichnis
from icarus_memory.lint import Befunde, Pruefer
from icarus_memory.memory_categories import Categories
from tests.test_bezuege import JETZT, Modell, stelle, welt  # noqa: F401 - shared fixture/helpers

NAME = "Müller, Jan"
ADDRESS = "jan@gmail.com"
ENCODED_NAME = "=?utf-8?q?M=C3=BCller=2C_Jan?="
PARTICIPANT = f"{ENCODED_NAME} <{ADDRESS}>"


def _mail(episodes, index, *, days_old=500, name=ENCODED_NAME, address=ADDRESS):
    return episodes.record(
        EpisodeKind.MESSAGE,
        f"Synthetic legacy mail {index}",
        f"Synthetic unchanged body {index}.",
        Provenance(SourceType.EMAIL, f"synthetic:legacy:{index}", JETZT - timedelta(days=days_old)),
        occurred_at=JETZT - timedelta(days=days_old),
        participants=[f"{name} <{address}>"],
        contacts=[{"name": name, "adresse": address, "rolle": "von", "ich": False}],
        at=JETZT,
    )[0]


def _snapshot(episodes, episode):
    stored = episodes.get(episode.id)
    support = episodes.support_snapshot(episode.id)
    return stored.to_dict(), stored.digest, support.generation


def test_register_token_rebuilds_old_name_link_without_touching_user_or_source_state(welt):
    episodes, _, bezuege = welt
    _mail(episodes, 1)
    body = f"{NAME} meldet sich zur Abstimmung."
    note, _ = episodes.record(
        EpisodeKind.DOCUMENT,
        "Synthetic mention",
        body,
        Provenance(SourceType.DOCUMENT, "synthetic:note", JETZT),
        at=JETZT,
    )
    Categories(episodes).run(
        Modell(lambda request: {
            "categories": [],
            "entities": [stelle(request["blocks"][0]["text"], NAME)],
        }),
        limit=20,
    )
    assert bezuege.aktualisieren()["offen"] == 0

    new_register = bezuege.register()
    legacy_directory = Verzeichnis()
    # Before header decoding, this address contributed the raw encoded name.
    legacy_directory.aufnehmen(Nennung(ENCODED_NAME, ADDRESS, "von", False))
    old_register = Register(verzeichnis=legacy_directory)
    old_register.token = old_register._digest()
    assert old_register.token != new_register.token
    old_link = old_register.person(NAME)[0]
    new_link = f"person:a:{ADDRESS}"
    assert old_link.startswith("person:n:") and new_register.person(NAME)[0] == new_link

    # Seed the persisted projection as the old process would have left it.
    with episodes.transaction():
        changed = episodes._conn.execute(
            "UPDATE sach_bezuege SET sache = ? WHERE episode_id = ? AND sache = ? AND grundlage = 'modell'",
            (old_link, note.id, new_link),
        ).rowcount
        assert changed == 1
        episodes._conn.execute(
            "UPDATE sach_quellen SET register = ? WHERE episode_id = ?",
            (old_register.token, note.id),
        )

    confirmed = "person:a:confirmed@example.org"
    dismissed = "person:a:dismissed@example.org"
    bezuege.nutzer_setzen(note.id, confirmed, "zu")
    bezuege.nutzer_setzen(note.id, dismissed, "nicht")
    user_rows_before = [tuple(row) for row in episodes._conn.execute(
        "SELECT episode_id, sache, art, aktion, fingerprint, updated_at "
        "FROM sach_nutzer WHERE episode_id = ? ORDER BY sache", (note.id,)
    )]
    source_before = _snapshot(episodes, note)

    assert bezuege.offene_zaehlen(new_register.token) == 1
    result = bezuege.aktualisieren()

    assert result == {"berechnet": 1, "entfernt": 0, "offen": 0}
    links = bezuege.bezuege_der_quelle(note.id)["bezuege"]
    assert any(link["sache"] == new_link and "modell" in link["grundlagen"] for link in links)
    assert not any(link["sache"] == old_link for link in links)
    user_rows_after = [tuple(row) for row in episodes._conn.execute(
        "SELECT episode_id, sache, art, aktion, fingerprint, updated_at "
        "FROM sach_nutzer WHERE episode_id = ? ORDER BY sache", (note.id,)
    )]
    assert user_rows_after == user_rows_before
    assert _snapshot(episodes, note) == source_before


@pytest.mark.parametrize("decision", ["erledigt", "abgewiesen"])
def test_lint_refresh_updates_ruhend_label_and_preserves_decision_and_sources(welt, tmp_path, decision):
    episodes, workspace, bezuege = welt
    sources = [_mail(episodes, index) for index in range(3)]
    assert bezuege.aktualisieren()["offen"] == 0
    source_state = {episode.id: _snapshot(episodes, episode) for episode in sources}
    manual_ref = "person:a:confirmed@example.org"
    bezuege.nutzer_setzen(sources[0].id, manual_ref, "zu")
    user_rows_before = [tuple(row) for row in episodes._conn.execute(
        "SELECT episode_id, sache, art, aktion, fingerprint, updated_at "
        "FROM sach_nutzer ORDER BY episode_id, sache"
    )]

    akten = Akten(episodes, bezuege)
    current = Pruefer(episodes, bezuege, akten, workspace=workspace, jetzt=JETZT).pruefen().befunde
    [ruhend] = [finding for finding in current if finding.unterart == "ruhend"]
    assert NAME in ruhend.text and ENCODED_NAME not in ruhend.text
    stale = replace(ruhend, text=ruhend.text.replace(NAME, PARTICIPANT))
    assert stale.schluessel == ruhend.schluessel

    ablage = Befunde(tmp_path / "lint.sqlite3")
    assert ablage.abgleichen([stale], am=100.0)["neu"] == 1
    ablage.status_setzen(ruhend.schluessel, decision)

    # This is the same projection-first ordering used by POST /api/v1/lint.
    assert bezuege.aktualisieren()["offen"] == 0
    refreshed = Pruefer(episodes, bezuege, akten, workspace=workspace, jetzt=JETZT).pruefen().befunde
    [fresh_ruhend] = [finding for finding in refreshed if finding.unterart == "ruhend"]
    assert fresh_ruhend.schluessel == ruhend.schluessel
    ablage.abgleichen([fresh_ruhend], am=200.0)

    saved = ablage.get(ruhend.schluessel)
    assert saved["status"] == decision
    assert NAME in saved["text"] and ENCODED_NAME not in saved["text"]
    assert [tuple(row) for row in episodes._conn.execute(
        "SELECT episode_id, sache, art, aktion, fingerprint, updated_at "
        "FROM sach_nutzer ORDER BY episode_id, sache"
    )] == user_rows_before
    assert {episode.id: _snapshot(episodes, episode) for episode in sources} == source_state
    ablage.close()
