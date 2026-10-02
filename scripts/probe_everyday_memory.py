#!/usr/bin/env python3
"""Frozen synthetic development probes. No personal configuration or external models.

Retrieval tests actual Agent.send provider payloads (no chat inference); meaning
exercises Agent.answer_memory with one installed local model. Neither is a human
holdout or extraction/production qualification. Results are exclusive checkpoints.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time

from icarus_memory.knowledge_search import RefreshingKnowledgeSearch
from icarus_memory.local_embeddings import LocalEmbedder
from icarus_memory.providers import OpenAICompatible
from memory_probe_fixtures import build_fixture, business_clock
from memory_probe_support import RecordingProvider, score_retrieval, validate_case
from probe_hybrid_memory import CaptureOnly
from probe_memory_pipeline import delivered_context

DOCUMENTS = [
 'Das Wartungsfenster für den Server beginnt am Donnerstag um 18 Uhr.',
 'Die Rechnung für die Dachreparatur wurde am 10. September bezahlt.',
 'Die Zugangskarte liegt im Schrank neben dem Empfang.',
 'Mira betreut die Lieferantenverträge für Projekt Linde.',
 'Die Anmeldung zum Workshop endet am 30. September.',
 'Das Auto muss im November zur Hauptuntersuchung.',
 'Die Veranstaltung in Dresden wurde auf Freitag verschoben.',
 'Die Lizenz für das Bild darf nur intern verwendet werden.',
 'Der Bericht ist als Entwurf gespeichert. Eine Freigabe liegt nicht vor.',
 'Die Lieferung verzögert sich wegen eines fehlenden Ersatzteils.',
]
QUESTIONS = [
 ('Wann ist die Wartung des Servers?', [1]), ('Wann können wir den Rechner nicht nutzen?', [1]),
 ('Ist die Rechnung bezahlt?', [2]), ('Sind die Kosten für das Dach beglichen?', [2]),
 ('Wo liegt die Zugangskarte?', [3]), ('Wo finde ich den Ausweis für den Zutritt?', [3]),
 ('Wer betreut die Lieferantenverträge?', [4]), ('Wer kümmert sich bei Linde um Vereinbarungen mit Zulieferern?', [4]),
 ('Wann endet die Workshopanmeldung?', [5]), ('Bis wann kann ich mich zum Seminar registrieren?', [5]),
 ('Wann ist die Hauptuntersuchung des Autos?', [6]), ('Wann ist der nächste TÜV fällig?', [6]),
 ('Wann ist die Veranstaltung in Dresden?', [7]), ('Auf welchen Wochentag wurde das Treffen in Sachsen verlegt?', [7]),
 ('Darf das Bild extern verwendet werden?', [8]), ('Welche Nutzungsrechte gelten für die Grafik?', [8]),
 ('Ist der Bericht freigegeben?', [9]), ('Kann der fertige Report veröffentlicht werden?', [9]),
 ('Warum verspätet sich die Lieferung?', [10]), ('Welcher Grund verhindert den rechtzeitigen Wareneingang?', [10]),
 ('Wie lautet die PIN meiner Bankkarte?', []), ('Welche Blutgruppe habe ich?', []),
]
STATES = [
 ('hypothesis', 'Falls wir den Atlasbericht versenden würden, könnte Mira ihn prüfen.'),
 ('request', 'Bitte versende den Atlasbericht. Ein Versand ist noch nicht bestätigt.'),
 ('decision', 'Wir haben entschieden, den Atlasbericht morgen zu versenden.'),
 ('completed', 'Mira schrieb: Ich habe den Atlasbericht am 19. September versendet.'),
 ('denied', 'Der Atlasbericht wurde ausdrücklich nicht versendet.'),
 ('unknown', 'Ob der Atlasbericht versendet wurde, ist unbekannt.'),
 ('quoted', 'Mira zitiert Jan: "Der Atlasbericht wurde versendet." Mira hat das nicht selbst geprüft.'),
 ('preference', 'Mira bevorzugt kurze Atlasberichte. Eine Vorliebe des Nutzers ist daraus nicht bekannt.'),
]


def case(identifier, question, documents, expected):
    return dict(id=identifier, scenario_id=identifier, split='development', fixture_mode='prepared_memory',
        clock_utc='2026-09-20T07:00:00Z', timezone='Europe/Berlin', question=question,
        sources=[dict(id=f'S{i}',text=text,source_type='document') for i,text in enumerate(documents,1)],
        entities=[dict(id=f'topic:record-{i}',kind='topic',label=f'Synthetic {i}') for i in range(1,len(documents)+1)],
        assertions=[dict(id=f'C{i}',subject_ref=f'topic:record-{i}',predicate='observed_note',value=text,source_id=f'S{i}') for i,text in enumerate(documents,1)],
        expected_source_ids=[f'S{i}' for i in expected], forbidden_source_ids=[],
        required=['Original wording, attribution and source are preserved; no action inferred.'],
        forbidden=['Unsupported execution claim or preference.'],severity='retrieval')


def cases(mode):
    if mode == 'retrieval':
        return [case(f'everyday-search-{i}',q,DOCUMENTS,ids) for i,(q,ids) in enumerate(QUESTIONS,1)]
    return [case('everyday-meaning-'+name,'Was wissen wir über den Atlasbericht?', [text],[1]) for name,text in STATES]


RETRIEVAL_ARMS = ('lexical', 'live_cold', 'live_warm')


def run(mode, output, model, lexical_only=False):
    if lexical_only and mode != 'retrieval':
        raise ValueError('--lexical-only only applies to --mode retrieval')
    subprocess.run(['git','diff','--quiet'],check=True)
    subprocess.run(['git','diff','--cached','--quiet'],check=True)
    arms=('lexical',) if lexical_only else RETRIEVAL_ARMS
    skipped_arms=tuple(a for a in RETRIEVAL_ARMS if a not in arms)
    needs_embedder=mode=='retrieval' and not lexical_only
    dataset=cases(mode)
    for c in dataset: validate_case(c)
    report=dict(mode=mode,semantic_qualification=False,extraction_evaluated=False,
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        dataset_sha256=hashlib.sha256(json.dumps(dataset,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
        cases=dataset,results=[],status='started',local_only=True)
    if mode=='retrieval':
        # Macht sichtbar, welche Varianten liefen und welche absichtlich ausblieben,
        # statt fehlende Ergebnisse stillschweigend als "nicht relevant" zu lesen.
        report.update(arms_selected=list(arms),arms_skipped=list(skipped_arms),embedding_initialized=False)
    start=time.monotonic()
    with Path(output).open('x') as stream, tempfile.TemporaryDirectory(prefix='kf-everyday-synthetic-') as tmp:
        def checkpoint():
            stream.seek(0); json.dump(report,stream,ensure_ascii=False,indent=2); stream.truncate(); stream.flush()
        checkpoint()
        embedder=None
        try:
            if needs_embedder: embedder=LocalEmbedder().__enter__();report['embedding_model_key']=embedder.model_key;report['embedding_initialized']=True
            for c in dataset:
                if time.monotonic()-start>900: raise TimeoutError('development run budget')
                provider=CaptureOnly() if mode=='retrieval' else OpenAICompatible(model=model,api_key='synthetic-local',base_url='http://127.0.0.1:11434/v1')
                recorder=RecordingProvider(provider)
                fixture=build_fixture(c,Path(tmp)/c['id'],recorder)
                try:
                    with business_clock(c):
                        if mode=='retrieval':
                            search=RefreshingKnowledgeSearch(embedder) if needs_embedder else None
                            for arm in arms:
                                rec=RecordingProvider(CaptureOnly());agent=fixture.agent.scoped(rec,frozenset())
                                agent._knowledge_search=None if arm=='lexical' else search
                                tick=time.monotonic();turn=agent.send(c['question']);elapsed=time.monotonic()-tick
                                delivery=delivered_context(fixture,turn,rec.calls)
                                actual=delivery['provider_source_ids']
                                report['results'].append(dict(case_id=c['id'],arm=arm,seconds=elapsed,actual_source_ids=actual,
                                    retrieval=score_retrieval(expected=set(c['expected_source_ids']),actual=set(actual),forbidden=set()),
                                    payload_mismatch_claim_ids=delivery['payload_mismatch_claim_ids'],metadata=turn.context.get('knowledge_retrieval')))
                                checkpoint()
                        else:
                            tick=time.monotonic();turn=fixture.agent.answer_memory(c['question'])
                            report['results'].append(dict(case_id=c['id'],seconds=time.monotonic()-tick,turn=turn.to_dict(),
                                provider_calls=recorder.calls,original=c['sources'][0]['text'],
                                original_preserved=c['sources'][0]['text'] in turn.reply,
                                side_effect_free=not(turn.used_tools or turn.approvals or turn.memory_candidate_drafts)))
                            checkpoint()
                finally: fixture.close()
                print(c['id'],flush=True)
            if embedder and embedder.identity()!=embedder.model_key: raise RuntimeError('weights changed')
            report['status']='completed'
        except (Exception,KeyboardInterrupt) as exc:
            report.update(status='failed',error_type=type(exc).__name__)
        finally:
            if embedder:embedder.__exit__()
            report['seconds']=time.monotonic()-start;checkpoint()
    return 0 if report['status']=='completed' else 1


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=['retrieval','meaning'],required=True)
    p.add_argument('--output',required=True);p.add_argument('--model',default='qwen3.5:4b')
    p.add_argument('--lexical-only',action='store_true',
        help='Nur --mode retrieval: nur die lexikalische Variante, ohne LocalEmbedder oder Ollama.')
    a=p.parse_args(argv)
    if a.lexical_only and a.mode!='retrieval': p.error('--lexical-only setzt --mode retrieval voraus')
    return run(a.mode,a.output,a.model,lexical_only=a.lexical_only)


if __name__=='__main__':
    raise SystemExit(main())
