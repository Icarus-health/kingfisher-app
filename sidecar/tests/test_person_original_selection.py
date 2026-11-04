"""Person answers use selectable original statements, not forbidden paraphrases."""
import pytest
import json
from jsonschema import Draft202012Validator

from icarus_memory import satzantwort as sa
from tests.test_original_sentence_selection import NOW, Selector, evidence
from tests.test_satzpruefung_modell import Pruefer, tor_mit
from tests.test_person_retrieval_repair import bestand, mail, einordnen, frage  # noqa: F401

CONTACT = 'Alex Winter an der Schule ist unter schule@example.invalid erreichbar.'
PARAPHRASE = 'Alex Winter ist an der Schule unter schule@example.invalid erreichbar.'


def answer_or_select(data):
    # Reproduce the actual Qwen response to free-text generation. The same
    # transport can instead select a server-issued statement without copying it.
    source = data['belege'][0]
    if 'originalsaetze' in source:
        return {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}
    return {'status': 'antwort', 'saetze': [{'text': PARAPHRASE, 'belege': [1]}]}


def test_contact_answer_survives_using_original_instead_of_reordered_paraphrase():
    result = sa.formulieren('Wo erreiche ich Alex Winter?',
        [evidence(CONTACT, personen=('Alex Winter',))], Selector(answer_or_select), jetzt=NOW,
        pruefung=tor_mit(Pruefer()))
    assert result.status == 'saetze', (result.grund, result.verworfen)
    assert [s.text for s in result.saetze] == [CONTACT]
    assert result.saetze[0].belege == (1,)
    assert not result.verworfen


@pytest.mark.parametrize('source, people', [
    ('Anna sendet die Druckdaten an Alex Sommer.', ('Anna', 'Alex Sommer')),
    ('Ich sende die Druckdaten an Anna.', ()),
    ('Der Auftraggeber liefert die Druckdaten.', ()),
])
def test_roles_and_pronouns_use_complete_original_without_changing_actor(source, people):
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    result = sa.formulieren('Wer liefert die Druckdaten?', [evidence(source, personen=people)],
                            provider, jetzt=NOW)
    assert result.status == 'saetze', result.grund
    assert result.saetze[0].text == source


def test_selected_contact_still_requires_the_second_judge():
    result = sa.formulieren('Wo erreiche ich Alex Winter?',
        [evidence(CONTACT, personen=('Alex Winter',))], Selector(answer_or_select), jetzt=NOW,
        pruefung=tor_mit(Pruefer(standard='{"urteil":"nein"}')))
    assert result.status == 'zitate'
    assert any('Prüfmodell: nicht gestützt' in s.gruende for s in result.verworfen)


def test_legacy_actor_inversion_is_not_repaired_or_accepted():
    result = sa.formulieren('Wer sendet die Druckdaten?',
        [evidence('Anna sendet die Druckdaten an Alex Sommer.', personen=('Anna', 'Alex Sommer'))],
        Selector({'status': 'antwort', 'saetze': [
            {'text': 'Alex Sommer sendet die Druckdaten an Anna.', 'belege': [1]}]}), jetzt=NOW)
    assert result.status == 'zitate'
    assert any('Personenbezug' in reason for s in result.verworfen for reason in s.gruende)


def test_names_in_metadata_do_not_force_unrelated_project_into_literal_mode():
    source = 'Die Abnahme in Alexburg ist am 19. Mai.'
    answer = 'Die Abnahme in Alexburg ist der 19. Mai.'
    result = sa.formulieren('Wann ist die Abnahme?', [evidence(source, personen=('Alex Sommer',))],
        Selector({'status': 'antwort', 'saetze': [{'text': answer, 'belege': [1]}]}), jetzt=NOW)
    assert result.status == 'saetze'
    assert result.saetze[0].text == answer


def test_partial_person_sentence_is_not_reconstructed_from_hidden_original():
    excerpt = 'unter schule@example.invalid erreichbar.'
    result = sa.formulieren('Wo erreiche ich Alex Winter?',
        [evidence(excerpt, personen=('Alex Winter',), pruef_text=CONTACT, gekuerzt=True)],
        Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}), jetzt=NOW)
    assert result.status == 'zitate'
    assert not result.saetze


@pytest.mark.parametrize('address', [
    'alex.winter@schule.example.invalid',
    'https://schule.example.invalid/kontakt?person=alex',
    'www.schule.example.invalid/kontakt',
])
def test_contact_punctuation_is_not_a_sentence_boundary(address):
    from icarus_memory import satzpruefung as sp
    first = f'Alex Winter ist unter {address} erreichbar.'
    second = 'Die Schule ist geschlossen.'
    body = first + ' ' + second
    parts = sp.originalabschnitt_stellen(body)
    assert [p[2] for p in parts] == [first, second]
    assert all(body[start:end] == text for start, end, text in parts)
    # A chopped email prefix cannot count as a complete personal statement.
    fragment = first.split('.')[0] + '.'
    assert not sp.rollenbindung(fragment, [body], sichtbar=[body], personen=('Alex Winter',))


def test_terminal_url_does_not_swallow_following_sentence_or_its_quote_boundary():
    from icarus_memory import satzpruefung as sp
    first = 'Alex ist unter https://schule.example.invalid erreichbar.'
    second = 'Die neue Adresse ist https://neu.example.invalid.'
    third = 'Sie gilt ab November.'
    assert sp.originalabschnitte(' '.join((first, second, third))) == (first, second, third)


@pytest.mark.parametrize('requires_clarification', [False, True])
def test_namesake_choice_answers_selected_contact_and_withdrawal_invalidates_it(bestand, requires_clarification):
    from icarus_memory import working_memory_answers as wma
    from tests.test_satzantwort import Skript
    app, _ = bestand
    purchasing = mail(app, 'Alex Winter', 'winter@alpha.example', title='Kontakt Einkauf',
        text='Alex Winter aus dem Einkauf ist unter einkauf@example.invalid erreichbar.')
    school = mail(app, 'Alex Winter', 'winter@beta.example', title='Kontakt Schule', text=CONTACT)
    einordnen(app)
    def selected_answer(data):
        if requires_clarification and data.get('nutzerwahl') != {
                'begriff': 'Alex Winter', 'art': 'absender',
                'auswahl': 'Mails von Alex Winter (winter@beta.example)'}:
            return {'status': 'nichts_vorliegend', 'originalstellen': []}
        return answer_or_select(data)
    app.state.agent._provider = Skript(selected_answer)
    app.state.agent._saetze = True
    app.state.agent._pruefung = lambda: tor_mit(Pruefer())
    pending = frage(app, 'Wo erreiche ich Alex Winter, aber nicht aus dem Einkauf?')
    choice = pending.context['meaning_choice']
    index = next(i for i, option in enumerate(choice['options']) if option['ids'] == [school.id])
    turn = app.state.agent.answer_meaning_choice(choice, index)
    answer = turn.context['working_answer']
    assert answer['satzantwort']['status'] == 'saetze', answer['satzantwort']
    assert CONTACT in turn.reply
    assert 'einkauf@example.invalid' not in turn.reply
    assert {r['episode_id'] for r in answer['refs']} == {school.id}
    text, links, _ = wma.render(answer, app.state.episodes, app.state.claims)
    assert CONTACT in text and purchasing.id not in {r['episode_id'] for r in links}
    app.state.episodes.ignore(school.id)
    text, links, status = wma.render(answer, app.state.episodes, app.state.claims)
    assert status == 'working_unavailable' and not links and CONTACT not in text


def test_automatic_person_match_is_not_reported_as_a_user_confirmation(bestand):
    from tests.test_satzantwort import Skript
    app, _ = bestand
    mail(app, 'Alex Winter', 'winter@alpha.example', title='Kontakt Einkauf',
         text='Alex Winter aus dem Einkauf ist unter einkauf@example.invalid erreichbar.')
    mail(app, 'Alex Winter', 'winter@beta.example', title='Kontakt Schule', text=CONTACT)
    einordnen(app)
    provider = Skript(answer_or_select, auswahl=lambda data: [
        row['id'] for row in data['sources'] if row['id'].startswith('S') and not row.get('andere_person')])
    app.state.agent._provider = provider
    app.state.agent._saetze = True
    turn = frage(app, 'Wo erreiche ich Alex Winter aus dem Einkauf?')
    assert turn.context['working_answer']['satzantwort']['status'] == 'saetze'
    assert provider.satzanfragen and all('nutzerwahl' not in p for p in provider.satzanfragen)


def test_namesake_annotation_keeps_its_expressible_safe_answer_contract():
    from icarus_memory.kennzeichnung import ANDERE_PERSON, Kennzeichen
    source = 'Alex Winter bittet um Feedback.'
    def choose_or_frame(data):
        if 'originalsaetze' in data['belege'][0]:
            return {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}
        return {'status': 'antwort', 'saetze': [
            {'text': 'Ein anderer Alex Winter bittet um Feedback.', 'belege': [1]}]}
    result = sa.formulieren('Was meldet der andere Alex Winter?', [evidence(source,
        personen=('Alex Winter',), kennzeichen=(Kennzeichen(ANDERE_PERSON, 'b@example.invalid',
            'Alex Winter', 'a@example.invalid'),))], Selector(choose_or_frame), jetzt=NOW)
    assert result.status == 'saetze', (result.grund, result.verworfen)
    assert result.saetze[0].text == 'Ein anderer Alex Winter bittet um Feedback.'


def test_unrelated_long_personal_sentence_does_not_block_a_short_answer():
    short = 'Der Bericht liegt im Tresor.'
    long = 'Wir dokumentieren ' + ', '.join('den Abschnitt ' + str(i) for i in range(30)) + '.'
    seen = []
    def choose_or_answer(data):
        seen.append(data)
        if 'originalsaetze' in data['belege'][0]:
            return {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]}
        return {'status': 'antwort', 'saetze': [{'text': short, 'belege': [1]}]}
    result = sa.formulieren('Wo liegt der Bericht?', [evidence(short + '\n\n' + long)],
                            Selector(choose_or_answer), jetzt=NOW)
    assert result.status == 'saetze', result.grund
    assert [s.text for s in result.saetze] == [short]
    # Do not make the answer possible by silently removing the other original.
    assert long in str(seen)


@pytest.mark.parametrize('legacy', [False, True])
def test_selecting_an_oversized_personal_statement_does_not_bypass_output_limit(legacy):
    long = 'Wir dokumentieren ' + ', '.join('den Abschnitt ' + str(i) for i in range(30)) + '.'
    assert len(long) > sa.MAX_SATZ_ZEICHEN
    output = ({'status': 'antwort', 'saetze': [{'text': long, 'belege': [1]}]} if legacy
              else {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    result = sa.formulieren('Was dokumentieren wir?', [evidence(long)], Selector(output), jetzt=NOW)
    assert result.status == 'zitate' and not result.saetze


def test_selection_schema_only_allows_actual_source_statement_pairs():
    from icarus_memory.providers import Reply
    deadline = 'Alex Winter liefert den Stundenplan bis zum 13. November 2026.'
    class SchemaBoundModel:
        is_local = True
        name = model = 'synthetic-schema-bound'
        def complete_json(self, messages, *, schema, **kwargs):
            # The real model emitted nonexistent (2,2) despite only source 1
            # being offered. A constrained decoder must not allow that pair.
            validator = Draft202012Validator(schema)
            wrong = {'status': 'antwort', 'originalstellen': [{'beleg': 2, 'satz': 2}]}
            correct = {'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 2}]}
            return Reply(text=json.dumps(wrong if validator.is_valid(wrong) else correct))
    result = sa.formulieren('Bis wann liefert Alex den Stundenplan?',
        [evidence(CONTACT + ' ' + deadline, personen=('Alex Winter',))], SchemaBoundModel(), jetzt=NOW)
    assert result.status == 'saetze', result.grund
    assert result.saetze[0].text == deadline


def test_bound_schema_cannot_cross_statement_number_between_sources():
    from dataclasses import replace
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    first = evidence(CONTACT, personen=('Alex Winter',))
    second = replace(first, nummer=2, episode_id='source-2',
        text='Anna liefert den Bericht. Anna liefert den Anhang.', personen=('Anna',))
    sa.formulieren('Was liefert Anna?', [first, second], provider, jetzt=NOW)
    validator = Draft202012Validator(provider.messages[0][1]['schema'])
    for source, sentence, allowed in [(1, 1, True), (1, 2, False), (2, 2, True), (3, 1, False)]:
        assert validator.is_valid({'status': 'antwort', 'originalstellen': [
            {'beleg': source, 'satz': sentence}]}) is allowed
