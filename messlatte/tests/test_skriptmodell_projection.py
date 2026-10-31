"""Der Fake interpretiert denselben verlustfreien Quelleingang wie ein echtes Modell."""
import copy
import json

import pytest

from skriptmodell import SkriptModell
from icarus_memory import absatzauswahl


def select(rows, words=('NICHT gesendet',)):
    model = SkriptModell({'Welche Angabe': list(words)})
    messages = [{'role': 'system', 'content': 'Wähle Originalstellen zur Frage aus.'},
                {'role': 'user', 'content': json.dumps({'question': 'Welche Angabe gilt?', 'sources': rows},
                                                      ensure_ascii=False)}]
    before = copy.deepcopy(messages)
    reply = model.complete_json(messages)
    assert messages == before
    return json.loads(reply.text)


@pytest.mark.parametrize('marker', [absatzauswahl.KURZER_VERWEIS, absatzauswahl.FUNDSTELLE])
def test_exact_self_marker_uses_complete_text_without_changing_original_rows(marker):
    rows = [{'id': 'S3', 'text': 'Die Unterlagen wurden NICHT gesendet.', 'context': marker}]
    before = copy.deepcopy(rows)
    assert select(rows) == {'status': 'source_reports', 'ids': ['S3']}
    assert rows == before


def test_actual_lossless_value_copies_resolve_before_matching_in_original_id_order():
    original = [{'id': f'S{i}', 'text': f'Einzelangabe {i}.',
                 'context': 'Die Unterlagen wurden NICHT gesendet. ' + 'Weiterer unveränderter Kontext. ' * 20}
                for i in (8, 2, 6)]
    packed = absatzauswahl.modell_zeilen(original)
    assert packed[1]['context'] == packed[2]['context'] == {'$copy': 'S8'}
    assert select(packed) == {'status': 'source_reports', 'ids': ['S8', 'S2', 'S6']}
    assert absatzauswahl.modell_zeilen_entpacken(packed) == original


def test_copied_self_marker_uses_current_rows_text_not_target_rows_text():
    rows = [{'id': 'S1', 'text': 'Die Unterlagen wurden gesendet.', 'context': absatzauswahl.KURZER_VERWEIS},
            {'id': 'S2', 'text': 'Die Unterlagen wurden NICHT gesendet.', 'context': {'$copy': 'S1'}}]
    assert select(rows) == {'status': 'source_reports', 'ids': ['S2']}


def test_only_explicit_markers_expand_without_replacing_distinct_context_or_searching_metadata():
    rows = [
        {'id': 'S1', 'text': 'Die Unterlagen wurden NICHT gesendet.', 'context': 'Die Unterlagen wurden gesendet.'},
        {'id': 'S2', 'text': 'Die Unterlagen wurden gesendet.', 'context': 'Die Unterlagen wurden NICHT gesendet.'},
        {'id': 'S3', 'text': 'Die Unterlagen wurden NICHT gesendet.',
         'context': absatzauswahl.FUNDSTELLE + '\nWeitere unveränderte Angaben.'},
        {'id': 'S4', 'title': 'NICHT gesendet', 'sender': 'NICHT gesendet', 'project': 'NICHT gesendet',
         'text': 'Anderes Thema.', 'context': 'Anderes Thema.'},
        {'id': 'S5', 'text': 'Die Unterlagen wurden NICHT gesendet.',
         'context': absatzauswahl.KURZER_VERWEIS + '\nAnderer Kontext.'},
    ]
    before = copy.deepcopy(rows)
    assert select(rows) == {'status': 'source_reports', 'ids': ['S2', 'S3']}
    assert rows == before


def test_actual_long_excerpt_and_added_case_context_resolve_only_referenced_snippet():
    parts = ['Von: Fachstelle <team@synthetic.example>',
             'Einleitung ohne Statusangabe. ' + 'Begleitende Information. ' * 18,
             'Die Unterlagen wurden NICHT gesendet. ' + 'Unveränderter Abschnitt der Fundstelle. ' * 10,
             'Andere organisatorische Hinweise. ' + 'Begleitende Information. ' * 20,
             'Freigabe fehlt weiterhin. ' + 'Unveränderte zusätzliche Bedingung. ' * 16,
             'Abschließende sonstige Angaben. ' + 'Begleitende Information. ' * 20]
    original = '\n\n'.join(parts)
    assert len(original) > absatzauswahl.GANZ_BIS
    ref = next(window for window in absatzauswahl.fenster(original)
               if 'NICHT gesendet' in original[window[0]:window[1]])
    excerpt = absatzauswahl.auszug(original, absatzauswahl.Suchwoerter.aus('Wurden die Unterlagen gesendet?'), ref=ref)
    start = original.index('Freigabe fehlt weiterhin.')
    excerpt = absatzauswahl.ergaenzen(original, excerpt, [(start, start + len(parts[4]), 'Freigabe fehlt weiterhin')])
    row = absatzauswahl.Zeile(id='S9', kind='fact', text=original[ref[0]:ref[1]], context=excerpt.text)
    row.volltext, row.auszug = original, excerpt
    projected = absatzauswahl.modell_zeilen([row])
    before = copy.deepcopy(projected)
    assert 'NICHT gesendet' not in projected[0]['context']
    assert absatzauswahl.FUNDSTELLE in projected[0]['context'] and absatzauswahl.KURZER_VERWEIS not in projected[0]['context']
    assert select(projected) == {'status': 'source_reports', 'ids': ['S9']}
    # Die Auflösung ersetzt nicht den ganzen Kontext: zusätzliche Bedingung,
    # Kopf, Trennstellen und Kürzungsvermerk bleiben als Daten vorhanden.
    for term in ('Freigabe fehlt weiterhin', 'Fachstelle', absatzauswahl.LUECKE, 'gekürzt'):
        assert select(projected, words=(term,)) == {'status': 'source_reports', 'ids': ['S9']}
    assert projected == before and row.volltext == original


@pytest.mark.parametrize('rows', [
    [{'id': 'S1', 'context': {'$copy': 'foreign'}}],
    [{'id': 'S1', 'context': {'$copy': 'S2'}}, {'id': 'S2', 'context': 'NICHT gesendet'}],
    [{'id': 'S1', 'context': {'$copy': 'S1'}}],
    [{'id': 'S1', 'context': 'NICHT gesendet'}, {'id': 'S2', 'context': {'$copy': 'S1'}},
     {'id': 'S3', 'context': {'$copy': 'S2'}}],
    [{'id': 'S1', 'text': 'NICHT gesendet'}, {'id': 'S2', 'context': {'$copy': 'S1'}}],
])
def test_invalid_or_foreign_references_fail_before_any_selection(rows):
    with pytest.raises(ValueError):
        select(rows)
