"""Person choice in the real mail/working-memory answer path, without inference."""
import pytest

from .test_person_retrieval_repair import bestand, mail, einordnen, frage


def contacts(app):
    purchasing = mail(app, 'Alex Winter', 'winter@alpha.example', title='Kontakt Einkauf',
        text='Alex Winter im Einkauf ist unter einkauf@example.invalid erreichbar.')
    school = mail(app, 'Alex Winter', 'winter@beta.example', title='Kontakt Schule',
        text='Alex Winter an der Schule ist unter schule@example.invalid erreichbar.')
    einordnen(app)
    return purchasing, school


@pytest.mark.parametrize('question', [
    'Wo erreiche ich Alex Winter?',
    'Wo erreiche ich Alex Winter, aber nicht aus dem Einkauf?',
    'Wer behauptet, Alex Winter im Einkauf sei erreichbar?',
    'Welche Belege gibt es dafür, Alex Winter im Einkauf zu verorten?',
    'Welche Belege zeigen, dass Alex Winter im Einkauf arbeitet?',
    'Wer weiß, ob Alex Winter im Einkauf arbeitet?',
    'Wo erreiche ich Alex Winter aus dem Einkauf bzw. aus der Schule?',
    'Wo erreiche ich Alex Winter, aber nicht winter@alpha.example?',
    'Wo erreiche ich Alex Winter aus dem Einkauf, falls er dort überhaupt arbeitet?',
    'Wie kann Alex Winter im Einkauf arbeiten, wenn er dort gar nicht angestellt ist?',
    'Wie kann Alex Winter im Einkauf arbeiten?',
    'Wo erreiche ich Alex Winter aus dem Einkauf – oder aus der Schule?',
    'Wo erreiche ich Alex Winter aus dem Einkauf / aus der Schule?',
    'Wo erreiche ich Alex Winter <winter@alpha.example> / <winter@beta.example>?',
    'Wo erreiche ich Alex Winter aus dem Einkauf? Diese Zuordnung ist unbestätigt.',
    'Wo erreiche ich Alex Winter aus dem Einkauf? Gemeint ist ausdrücklich die Person aus der Schule.',
    'Wo erreiche ich Alex Winter aus dem Einkauf respektive aus der Schule?',
    'Welche Aufgaben hat Alex Winter aus dem Einkauf noch nicht erledigt? Die Zuordnung ist unklar.',
])
def test_disputed_or_negative_qualifier_does_not_silently_choose_person(bestand, question):
    app, provider = bestand
    first, second = contacts(app)
    turn = frage(app, question)
    assert turn.context['answer_contract']['status'] == 'meaning_choice'
    assert {tuple(o['ids']) for o in turn.context['meaning_choice']['options']} == {(first.id,), (second.id,)}
    assert provider.calls == []


@pytest.mark.parametrize('question', [
    'Wo erreiche ich Alex Winter aus dem Einkauf?',
    'Welche Aufgaben hat Alex Winter aus dem Einkauf noch nicht erledigt?',
    'Welche Aufgabe hat Alex Winter aus dem Einkauf nicht zugesagt?',
    'Was hat Alex Winter <winter@alpha.example> nicht zugesagt?',
    'Wo erreiche ich Alex Winter winter@alpha.example?',
    'Hat Alex Winter (winter@alpha.example) die Aufgabe erledigt?',
    'Hat Alex Winter aus dem Einkauf die Aufgabe erledigt?',
    'Erzähl mir etwas über Alex Winter (winter@alpha.example).',
    'Bis wann soll Alex Winter aus dem Einkauf den Angebotsvergleich liefern?',
    'Bis wann soll Alex Winter (winter@alpha.example) den Angebotsvergleich liefern?',
])
def test_positive_identity_qualifier_can_coexist_with_negated_task(bestand, question):
    app, provider = bestand
    first, second = contacts(app)
    turn = frage(app, question)
    assert turn.context['answer_contract']['status'] == 'working_reports'
    answer = turn.context['working_answer']
    assert first.id in answer['person_scope']
    assert second.id not in answer['person_scope']
    rows = provider.calls[-1]['sources']
    other = next((row for row in rows if row['text'].startswith('Alex Winter an der Schule')), None)
    assert other is None or other.get('andere_person')


def test_saved_negative_person_choice_is_invalidated(bestand, monkeypatch):
    from icarus_memory import personenfrage, working_memory_answers
    app, _ = bestand
    contacts(app)
    with monkeypatch.context() as legacy:
        legacy.setattr(personenfrage, 'unterscheidet', lambda text, mention, episodes:
            next(k for k in mention.kandidaten if k.adresse == 'winter@alpha.example'))
        answer = frage(app, 'Wo erreiche ich Alex Winter, aber nicht aus dem Einkauf?').context['working_answer']
        assert working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
    assert not working_memory_answers._fresh(answer, app.state.episodes, app.state.claims)
