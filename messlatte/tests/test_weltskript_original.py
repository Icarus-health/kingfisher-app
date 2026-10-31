"""WeltSkript liest Original-IDs; ein Vollzitat darf keine Satzfreigabe vortäuschen."""
import copy
import json
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from icarus_memory import satzantwort as sa
from messlatte.antwort import antwort_nachricht
from messlatte.aufnahme import aufnehmen
from messlatte.daten import Adresse, Erwartet, Frage, Mail, Skript
from messlatte.instanz import instanz_starten
from messlatte.skript import WeltSkript

RULE = ('Wenn die Freigabe schriftlich vorliegt, darf die Prüfung beginnen. '
        'Die Freigabe liegt noch nicht vor.')
FALSE = 'Die Prüfung darf ohne schriftliche Freigabe beginnen.'
QUESTION = Frage('regel-1', 'Welche Regel gilt für die Prüfung?', 'regel', 'normal',
    Erwartet('antworten', ((RULE,),)), skript=Skript(('Prüfung',), RULE, FALSE))


def request(belege, *, original=True, question=QUESTION.frage):
    return [{'role': 'system', 'content': sa.ORIGINAL_ANWEISUNG if original else sa.ANWEISUNG},
            {'role': 'user', 'content': json.dumps({'anliegen': question, 'belege': belege}, ensure_ascii=False)}]


def test_original_eingang_ohne_text_liefert_nur_tatsaechlich_angebotene_ganze_ids():
    data = [{'nr': 7, 'quelle': 'Prüfung', 'originalsaetze': [{'nr': 12, 'text': RULE}]},
            {'nr': 9, 'quelle': 'Anderes Thema', 'originalsaetze': [{'nr': 3, 'text': 'Eine andere Originaleinheit.'}]}]
    messages = request(data)
    before = copy.deepcopy(messages)
    reply = WeltSkript('sorgfaeltig', [QUESTION]).complete_json(messages, schema=sa.ORIGINAL_SCHEMA)
    assert json.loads(reply.text) == {'status': 'antwort', 'originalstellen': [{'beleg': 7, 'satz': 12}]}
    assert messages == before and RULE not in reply.text and FALSE not in reply.text


@pytest.mark.parametrize('original', [False, True])
@pytest.mark.parametrize('case,status', [('unknown', 'unklar'), ('judge', 'unklar'), ('empty', 'nichts_vorliegend')])
def test_leere_ausgaben_halten_das_angebotene_schema_ein(original, case, status):
    data = [] if case == 'empty' else [{'nr': 2, 'quelle': 'Prüfung',
        **({'originalsaetze': [{'nr': 4, 'text': RULE}]} if original else {'text': RULE})}]
    model = WeltSkript('pruefung' if case == 'judge' else 'sorgfaeltig', [QUESTION])
    reply = model.complete_json(request(data, original=original, question='Unbekannte Frage?' if case == 'unknown' else QUESTION.frage),
                                schema=sa.ORIGINAL_SCHEMA if original else sa.SCHEMA)
    assert json.loads(reply.text) == {'status': status, 'originalstellen' if original else 'saetze': []}


def test_originalauswahl_bleibt_auf_schema_limit_und_angebotene_ids_begrenzt():
    data = [{'nr': 8, 'quelle': 'Prüfung', 'originalsaetze':
             [{'nr': nr, 'text': f'Vollständige Originaleinheit {nr}.'} for nr in range(10, 18)]}]
    reply = WeltSkript('sorgfaeltig', [QUESTION]).complete_json(request(data), schema=sa.ORIGINAL_SCHEMA)
    assert json.loads(reply.text) == {'status': 'antwort', 'originalstellen':
        [{'beleg': 8, 'satz': nr} for nr in range(10, 10 + sa.MAX_SAETZE)]}


def test_unaufmerksam_behaelt_legacy_fehlkandidaten_auch_im_originalmodus():
    data = [{'nr': 7, 'quelle': 'Prüfung', 'originalsaetze': [{'nr': 12, 'text': RULE}]}]
    reply = WeltSkript('unaufmerksam', [QUESTION]).complete_json(request(data), schema=sa.ORIGINAL_SCHEMA)
    assert json.loads(reply.text) == {'status': 'antwort', 'saetze':
        [{'text': RULE, 'belege': [7]}, {'text': FALSE, 'belege': [7]}]}


def test_normaler_textmodus_behaelt_seinen_bisherigen_vertrag():
    reply = WeltSkript('sorgfaeltig', [QUESTION]).complete_json(
        request([{'nr': 2, 'quelle': 'Prüfung', 'text': RULE}], original=False), schema=sa.SCHEMA)
    assert json.loads(reply.text) == {'status': 'antwort', 'saetze': [{'text': RULE, 'belege': [2]}]}


@pytest.mark.parametrize('art,accepted', [('sorgfaeltig', True), ('unaufmerksam', False)])
def test_echter_produktpfad_prueft_satzstruktur_statt_nur_vollzitat(art, accepted):
    clock = datetime(2026, 11, 1, 8, tzinfo=timezone.utc)
    source = Mail(id='regel-1', zeit=clock, szenario='synthetic-protocol',
        von=Adresse('Fachstelle', 'team@protocol.example'), an=(Adresse('Test', 'test@protocol.example'),),
        betreff='Regel zur Prüfung', text=RULE)
    provider, judge = WeltSkript(art, [QUESTION]), WeltSkript('pruefung', [QUESTION])
    with patch('icarus_memory.secrets.Keychain._detect', return_value='none'):
        with instanz_starten(stichtag=clock, zeitzone='Europe/Berlin', provider=provider,
                             pruef_provider=judge, eigene=('test@protocol.example',)) as app:
            app.app.state.scheduler.stop()
            result = aufnehmen(app, [source], clock, modell=provider)
            cid = app.anfrage('POST', '/api/v1/conversations', {})['conversation']['id']
            response = app.anfrage('POST', f'/api/v1/conversations/{cid}/messages',
                                   {'message': QUESTION.frage, 'answer_mode': 'auto'})
            message = antwort_nachricht(response)
            context = message['metadata']['context']
            saved = context['working_answer']['satzantwort']
            if accepted:
                assert saved['status'] == 'saetze' and saved['verworfen'] == 0
                assert context['satzantwort']['saetze'] and saved['saetze'][0]['roh'] == RULE
                assert judge.pruefanfragen == 1
            else:
                assert saved['status'] == 'zitate' and saved['verworfen'] >= 1
                assert 'satzantwort' not in context and FALSE not in message['content']
            assert app.episodes.get(result.episoden['regel-1']).body.strip() == RULE
