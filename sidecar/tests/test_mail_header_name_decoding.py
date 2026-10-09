"""RFC-2047-Namen werden nur an bekannten Mailkopf-Grenzen dekodiert.

Die synthetischen Datensätze prüfen eine reine Leseprojektion: Quelldaten und
adressbasierte Identität bleiben erhalten; gleich aussehender Text in Notizen
und Nachrichtentext wird weiterhin wörtlich behandelt.
"""
from datetime import datetime, timezone
from email.utils import formataddr
from base64 import b64encode

import pytest

from icarus_memory import bezuege, identitaet, kontakte, personen
from icarus_memory.episodes import EpisodeKind, EpisodeStore
from icarus_memory.model import Provenance, SourceType

NOW = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
BODY = "Synthetischer Mailinhalt bleibt unverändert."
NAME = "Müller, Jan"
ADDRESS = "jan@z.example"
ENCODED_NAME = "=?utf-8?q?M=C3=BCller=2C_Jan?="
ENCODED_PARTICIPANT = f"{ENCODED_NAME} <{ADDRESS}>"


@pytest.fixture
def episodes(tmp_path):
    return EpisodeStore(tmp_path / "episodes.sqlite3")


def _legacy_email(episodes, address=ADDRESS, *, name=ENCODED_NAME, body=BODY):
    """Eine ältere Mail mit rohem MIME-Anzeigenamen in beiden Metadatenfeldern."""
    participant = f"{name} <{address}>"
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE,
        "Synthetic message",
        body,
        Provenance(SourceType.EMAIL, "synthetic:mail", NOW),
        occurred_at=NOW,
        participants=[participant],
        contacts=[{"name": name, "adresse": address, "rolle": "von", "ich": False}],
        at=NOW,
    )
    return episode


def test_formataddr_unicode_roundtrip_through_known_header_parser():
    wire_header = formataddr((NAME, ADDRESS))
    parsed = kontakte.kontakt(wire_header, "von")

    assert parsed == {"name": NAME, "adresse": ADDRESS, "rolle": "von", "ich": False}


def test_header_parser_decodes_multiple_q_and_b_encoded_words():
    wire_header = "=?utf-8?q?M=C3=BCller?= =?utf-8?b?IEphbg==?= <jan@z.example>"

    parsed = kontakte.kontakt(wire_header, "cc")

    assert parsed["name"] == "Müller Jan"
    assert parsed["adresse"] == "jan@z.example"


def test_legacy_structured_email_contacts_decode_in_projection_without_rewriting_source(episodes):
    episode = _legacy_email(episodes)
    before = episodes.get(episode.id).to_dict()
    generation_before = episodes.support_snapshot(episode.id).generation

    [mention] = identitaet.nennungen(episode)
    [person] = personen.alle(episodes=episodes, jetzt=NOW)
    # Beide Projektionen bleiben an dieselbe Mailadresse gebunden.
    assert mention.name == NAME
    assert person.id == f"a:{ADDRESS}"
    assert person.adressen == [ADDRESS]
    assert NAME in person.namen and person.name == NAME
    assert bezuege.Bezuege(episodes).beschriftung(f"person:a:{ADDRESS}") == NAME

    after = episodes.get(episode.id).to_dict()
    assert after == before
    assert after["body"] == BODY
    assert after["participants"] == [ENCODED_PARTICIPANT]
    assert after["contacts"][0]["name"] == ENCODED_NAME
    assert episodes.support_snapshot(episode.id).generation == generation_before


def test_equal_decoded_name_at_different_addresses_stays_two_people(episodes):
    first = _legacy_email(episodes, "jan@one.example", body=BODY + " one")
    second = _legacy_email(episodes, "jan@two.example", body=BODY + " two")

    people = personen.alle(episodes=episodes, jetzt=NOW)

    assert {person.id for person in people} == {"a:jan@one.example", "a:jan@two.example"}
    assert all(person.name == NAME and NAME in person.namen for person in people)
    assert first.id != second.id


def test_decoded_name_does_not_turn_generic_mailbox_into_a_person(episodes):
    episode = _legacy_email(episodes, "info@service.example")

    assert identitaet.nennungen(episode)[0].name == NAME
    assert personen.alle(episodes=episodes, jetzt=NOW) == []
    assert episodes.get(episode.id).contacts[0]["adresse"] == "info@service.example"


def test_non_email_name_and_body_entity_keep_literal_rfc2047_text(episodes):
    note, _ = episodes.record(
        EpisodeKind.DOCUMENT,
        "Synthetic note",
        ENCODED_NAME,
        Provenance(SourceType.DOCUMENT, "synthetic:note", NOW),
        occurred_at=NOW,
        participants=[ENCODED_NAME],
        at=NOW,
    )

    [mention] = identitaet.nennungen(note)
    entity = {"kind": "person", "name": ENCODED_NAME, "start": 0, "end": len(ENCODED_NAME), "role": "mentioned"}
    links = bezuege.berechnen(note, {"entities": [entity], "categories": []},
                              bezuege.Register.bauen([note]))

    assert kontakte.anzeigename(ENCODED_NAME) == ENCODED_NAME
    assert mention.name == ENCODED_NAME
    assert any(link.grundlage == "modell" and link.sache == "person:n:" + ENCODED_NAME.casefold()
               for link in links)
    assert episodes.get(note.id).body == ENCODED_NAME


def test_unicode_recipient_roundtrips_through_mail_and_participant_paths():
    kontakte_aus_mail = kontakte.fuer_mail(
        "Absender <sender@z.example>",
        [{"name": NAME, "adresse": ADDRESS, "rolle": "an"}],
    )

    [absender, empfaenger] = kontakte_aus_mail
    [absender_text, empfaenger_text] = kontakte.teilnehmer_texte(kontakte_aus_mail)

    assert absender["adresse"] == "sender@z.example"
    assert empfaenger == {"name": NAME, "adresse": ADDRESS, "rolle": "an", "ich": False}
    assert absender_text == "Absender <sender@z.example>"
    assert empfaenger_text == formataddr((NAME, ADDRESS))
    assert kontakte.kontakt(empfaenger_text, "an") == empfaenger


def test_bulk_labels_decode_email_projection_but_default_participant_queries_stay_raw(episodes):
    erste = _legacy_email(episodes, "jan@one.example", body=BODY + " eins")
    zweite = _legacy_email(episodes, "jan@two.example", body=BODY + " zwei")
    store = bezuege.Bezuege(episodes)

    roh = episodes.participants_for_addresses(["jan@one.example", "jan@two.example"])
    einzeln_roh = episodes.participants_for_address("jan@one.example")
    beschriftungen = store.beschriftungen(["person:a:jan@one.example", "person:a:jan@two.example"])

    assert roh["jan@one.example"]["namen"] == {f"{ENCODED_NAME} <jan@one.example>": 1}
    assert roh["jan@two.example"]["namen"] == {f"{ENCODED_NAME} <jan@two.example>": 1}
    assert any(ENCODED_NAME in eintrag["name"] for eintrag in einzeln_roh)
    assert beschriftungen == {"person:a:jan@one.example": NAME, "person:a:jan@two.example": NAME}
    assert erste.id != zweite.id


def test_participant_only_legacy_email_decodes_for_identity_and_labels(episodes):
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE,
        "Synthetische Mail nur mit Teilnehmern",
        BODY + " nur Teilnehmer",
        Provenance(SourceType.EMAIL, "synthetic:participant-only", NOW),
        occurred_at=NOW,
        participants=[ENCODED_PARTICIPANT],
        at=NOW,
    )

    [mention] = identitaet.nennungen(episode)
    [roher_teilnehmer] = episodes.participants_for_address(ADDRESS)

    assert mention.name == NAME
    assert mention.adresse == ADDRESS
    assert roher_teilnehmer["name"] == ENCODED_PARTICIPANT
    assert bezuege.Bezuege(episodes).beschriftung(f"person:a:{ADDRESS}") == NAME


def test_non_email_structured_contacts_keep_rfc2047_text(episodes):
    note, _ = episodes.record(
        EpisodeKind.DOCUMENT,
        "Synthetischer Kontakt ohne Mailquelle",
        BODY + " Kontakt",
        Provenance(SourceType.DOCUMENT, "synthetic:contact", NOW),
        occurred_at=NOW,
        contacts=[{"name": ENCODED_NAME, "adresse": ADDRESS, "rolle": "beteiligt", "ich": False}],
        at=NOW,
    )

    [mention] = identitaet.nennungen(note)

    assert mention.name == ENCODED_NAME
    assert mention.adresse == ADDRESS


@pytest.mark.parametrize("roher_name", [
    "=?x-unknown?Q?M=FCller?=",
    "=?utf-8?b?/w==?=",
    "=?utf-8?q?Name=0AInjected?=",
])
def test_defekte_oder_steuernde_headernamen_bleiben_sicher_roh(roher_name):
    parsed = kontakte.kontakt(f"{roher_name} <{ADDRESS}>", "an")

    assert parsed["name"] == roher_name
    assert parsed["adresse"] == ADDRESS


@pytest.mark.parametrize("zeichen", ["\u202e", "\u2066", "\u2069", "\u200b", "\u0085"])
def test_unsichtbare_unicode_steuerzeichen_werden_nicht_als_name_dekodiert(zeichen):
    roh = "=?utf-8?b?" + b64encode(("Alice" + zeichen + "Spoof").encode()).decode("ascii") + "?="
    parsed = kontakte.kontakt(f"{roh} <{ADDRESS}>", "von")
    assert parsed["name"] == roh
    assert parsed["adresse"] == ADDRESS


@pytest.mark.parametrize("zeichen", ["\u202e", "\u2066", "\u2069", "\u200b", "\u0085"])
def test_unverschluesselte_steuernde_kopfnamen_bleiben_ohne_anzeigenamen(zeichen):
    parsed = kontakte.kontakt("Alice" + zeichen + f"Spoof <{ADDRESS}>", "von")
    assert parsed["name"] == ""
    assert parsed["adresse"] == ADDRESS


def test_encoded_at_in_display_name_cannot_change_address_or_identity(episodes):
    schadhafter_name = "=?utf-8?q?evil=40other.example?="
    echte_adresse = "jan@real.example"
    parsed = kontakte.kontakt(f"{schadhafter_name} <{echte_adresse}>", "von")
    episode, _ = episodes.record(
        EpisodeKind.MESSAGE,
        "Synthetische Mail mit kodiertem At-Zeichen",
        BODY + " codiert",
        Provenance(SourceType.EMAIL, "synthetic:encoded-at", NOW),
        occurred_at=NOW,
        contacts=[{"name": schadhafter_name, "adresse": echte_adresse, "rolle": "von", "ich": False}],
        at=NOW,
    )

    [mention] = identitaet.nennungen(episode)
    register = bezuege.Register.bauen([episode])

    assert parsed["adresse"] == echte_adresse
    assert parsed["name"] == ""
    assert mention.adresse == echte_adresse
    assert mention.name == ""
    assert register.verzeichnis.adressen() == [echte_adresse]
