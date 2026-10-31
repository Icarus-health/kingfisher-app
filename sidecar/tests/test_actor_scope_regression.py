"""Actor proof is limited to known people, leaving project checks to existing gates."""
import pytest

from icarus_memory.satzantwort import AntwortBeleg, pruefe_satz
from icarus_memory.satzpruefung import Satz
from tests.test_satzantwort import DIENSTAG


@pytest.mark.parametrize('source, answer', [
    ('Die Werkstatt liefert Ersatzteile an den Verein.',
     'Der Verein liefert Ersatzteile an die Werkstatt.'),
    ('Die Vor-Ort-Abnahme in Werkhalle Epsilon wird vom 12. Mai um 09:00 Uhr '
     'auf den 19. Mai um 14:30 Uhr verschoben. Der alte Termin ist ersetzt.',
     'Die Abnahme in Werkhalle Epsilon wurde auf den 19. Mai um 14:30 Uhr verschoben.'),
])
def test_project_or_common_noun_does_not_invoke_person_actor_guard(source, answer):
    # Generic relation inversion remains the second judge's responsibility.
    beleg = AntwortBeleg(1, {}, 'fact', 'e1', '', '', source, DIENSTAG)
    result = pruefe_satz(Satz(answer, ('1',)), {'1': beleg}, DIENSTAG)
    assert result.bestanden, result.gruende


@pytest.mark.parametrize('actor', ['Alex Sommer', 'Alex', 'alex sommer', 'aLeX'])
def test_known_person_full_or_first_name_is_case_insensitive_actor_trigger(actor):
    from icarus_memory.satzpruefung import rollenbindung
    source = 'Bitte sende die Druckdaten an Anna.'
    assert not rollenbindung(actor + ' sendet die Druckdaten an Anna.', [source],
                             sichtbar=[source], personen=('Alex Sommer', 'Anna'))


def test_named_actor_inversion_still_rejected_with_known_source_people():
    source = 'Anna sendet die Druckdaten an Alex Sommer.'
    beleg = AntwortBeleg(1, {}, 'fact', 'e1', '', '', source, DIENSTAG,
                         personen=('Anna', 'Alex Sommer'))
    assert pruefe_satz(Satz(source, ('1',)), {'1': beleg}, DIENSTAG).bestanden
    result = pruefe_satz(Satz('Alex Sommer sendet die Druckdaten an Anna.', ('1',)), {'1': beleg}, DIENSTAG)
    assert not result.bestanden
    assert any('Personenbezug' in reason for reason in result.gruende)


def test_known_name_substring_does_not_convert_a_project_into_an_actor():
    source = 'Die Abnahme in Alexburg ist am 19. Mai.'
    beleg = AntwortBeleg(1, {}, 'fact', 'e1', '', '', source, DIENSTAG, personen=('Alex Sommer',))
    sentence = 'Die Abnahme in Alexburg ist der 19. Mai.'
    assert pruefe_satz(Satz(sentence, ('1',)), {'1': beleg}, DIENSTAG).bestanden


def test_surname_alone_does_not_turn_summer_season_into_a_person():
    from icarus_memory.satzpruefung import rollenbindung
    source = 'Die Abnahme ist im Sommer geplant.'
    assert rollenbindung('Im Sommer ist die Abnahme geplant.', [source], sichtbar=[source],
                         personen=('Alex Sommer',))
