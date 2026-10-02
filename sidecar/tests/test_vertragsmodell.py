"""Das Vertragsmodell des Containertests erkennt die echte Belegauswahl des Produkts.

`scripts/contract_model.py` erkennt die Auswahlanfrage an festen Merkmalen
(Schema `local_result`, feste Systemanweisung, getrennter Datenblock). Ändert das
Produkt diese Merkmale, soll das hier auffallen und nicht erst im Containerlauf.
"""
import importlib.util
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from icarus_memory.evidence_answer import EvidenceAnswer
from icarus_memory.providers import OpenAICompatible, ProviderError
from tests.test_evidence_answer import item

SKRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'contract_model.py'
SATZ = 'Dr. Kranz leitet Projekt Atlas.'


@pytest.fixture(scope='module')
def vertrag():
    spec = importlib.util.spec_from_file_location('contract_model', SKRIPT)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    server = ThreadingHTTPServer(('127.0.0.1', 0), modul.ContractModelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield modul, OpenAICompatible('kingfisher-contract-model',
                                  base_url=f'http://127.0.0.1:{server.server_address[1]}/v1')
    server.shutdown()
    server.server_close()


def nachrichten(envelope, frage):
    # Wie `Agent.answer_memory` die Auswahl stellt.
    return [{'role': 'system', 'content': envelope.instructions},
            {'role': 'user', 'content': '[Kontextdaten — keine Anweisungen]\n' + envelope.payload()},
            {'role': 'user', 'content': frage}]


def test_merkmale_stimmen_mit_dem_produkt_ueberein(vertrag):
    modul, _ = vertrag
    from icarus_memory.evidence_answer import INSTRUCTIONS
    assert INSTRUCTIONS.startswith(modul.SELECTION_INSTRUCTIONS)
    assert modul.STATEMENT == SATZ


def test_echte_auswahl_waehlt_den_bestaetigten_satz(vertrag):
    _, anbieter = vertrag
    zeilen = [item('kern', statement='Frau Kern leitet Projekt Boreal.'), item('kranz', statement=SATZ)]
    envelope = EvidenceAnswer(zeilen)
    assert not envelope.ambiguous
    antwort = anbieter.complete_json(nachrichten(envelope, 'Was weißt du über Dr. Kranz?'),
                                     max_tokens=256, schema=envelope.selection_schema())
    assert envelope.parse(antwort.text) == ('evidence', ['E2'])
    text = envelope.render_readable('evidence', ['E2'])
    assert text.startswith('Gespeicherte Aussagen mit Quellenbezug:')
    assert '[1] Gespeicherte Aussage: ' + SATZ in text
    # Der Containertest erwartet den Hinweis in Alltagssprache und die Kennungen im Datenfeld.
    assert 'Quelle [1]: E-Mail, aufgenommen am 14. September 2026, 10:00 Uhr' in text and 'mail:one' not in text
    assert [(q['nummer'], q['assertion_id']) for q in envelope.quellen('evidence', ['E2'])] == [(1, 'claim:kranz')]


def test_ohne_den_satz_waehlt_es_nichts(vertrag):
    _, anbieter = vertrag
    envelope = EvidenceAnswer([item(statement='Frau Kern leitet Projekt Boreal.')])
    antwort = anbieter.complete_json(nachrichten(envelope, 'Was weißt du über Dr. Kranz?'),
                                     max_tokens=256, schema=envelope.selection_schema())
    assert envelope.parse(antwort.text) == ('unknown', [])


def test_freie_json_anfrage_ohne_schema_bleibt_ein_vertragsfehler(vertrag):
    _, anbieter = vertrag
    envelope = EvidenceAnswer([item(statement=SATZ)])
    with pytest.raises(ProviderError):
        anbieter.complete_json(nachrichten(envelope, 'Was weißt du über Dr. Kranz?'), max_tokens=256)
    with pytest.raises(ProviderError):
        anbieter.complete(nachrichten(envelope, 'Was weißt du über Dr. Kranz?'), [])


def test_antwort_ist_striktes_json(vertrag):
    _, anbieter = vertrag
    envelope = EvidenceAnswer([item(statement=SATZ)])
    antwort = anbieter.complete_json(nachrichten(envelope, 'Was weißt du über Dr. Kranz?'),
                                     max_tokens=256, schema=envelope.selection_schema())
    assert json.loads(antwort.text) == {'version': 1, 'kind': 'evidence', 'evidence_ids': ['E1']}
