"""Replay frozen selections, not inference; separately exercise the calendar route."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from icarus_memory.evidence_answer import EvidenceAnswer
from memory_probe_fixtures import build_fixture, business_clock
from probe_memory_pipeline import load_catalog

BASE='docs/evaluations/memory-quality/runtime/structured-evidence-20260919/qwen35-4b.json'
REPO=Path(__file__).resolve().parents[5]


def git(*args):
    return subprocess.run(['git',*args],cwd=REPO,check=True,capture_output=True).stdout


class NoInference:
    name=model='no-inference'
    is_local=True
    def complete(self,*args,**kwargs):
        raise AssertionError('Presentation replay must not call a model')


def replay():
    raw=git('show','HEAD:'+BASE)
    previous=json.loads(raw)
    cases={}
    for selector in ('development-v1','countercases-v1'):
        cases.update(load_catalog(selector)[0])
    report={'kind':'frozen-selection-presentation-replay','commit':git('rev-parse','HEAD').decode().strip(),
            'input_sha256':hashlib.sha256(raw).hexdigest(),'input_path':BASE,
            'fresh_model_calls':0,'semantic_qualification':False,'cases':[]}
    for old in previous['attempts']:
        case=cases[old['case_id']]
        contract=old['turn']['context']['answer_contract']
        status=contract['status']
        result={'case_id':old['case_id'],'question':old['question'],'before':old['turn']['reply'],
                'original_status':status,'missing_visible_fields':[]}
        if 'calendar_callback' in case:
            with tempfile.TemporaryDirectory(prefix='kingfisher-readable-calendar-') as temp:
                fixture=build_fixture(case,Path(temp),NoInference())
                try:
                    with business_clock(case):turn=fixture.agent.answer_memory(case['question'])
                    result.update(after=turn.reply,status=turn.context['answer_contract']['status'],
                                  mode='actual_agent_calendar',context=turn.context)
                finally:fixture.close()
        else:
            context=old['turn']['context']
            envelope=EvidenceAnswer(context['items'])
            by_id={row['assertion_id']:alias for alias,row in envelope.rows.items()}
            aliases=[by_id[identifier] for identifier in contract['selected_assertion_ids']]
            output=envelope.render_readable(status,aliases if status=='evidence' else [],reason=contract.get('reason'))
            for identifier in contract['selected_assertion_ids']:
                row=envelope.rows[by_id[identifier]];source=row['primary_evidence']
                quoted={'statement':row['statement'],'value':row['value'],
                        'source_ref':source['source_ref'] or source['episode_id']}
                for key,value in quoted.items():
                    if json.dumps(value,ensure_ascii=False) not in output:
                        result['missing_visible_fields'].append(identifier+':'+key)
                for key,value in [('occurred_at',source['occurred_at']),('recorded_at',source['recorded_at']),
                                  ('valid_from',row['valid_from']),('valid_until',row['valid_until'])]:
                    if value is not None and value not in output:
                        result['missing_visible_fields'].append(identifier+':'+key)
            result.update(after=output,status=status,mode='frozen_selection_renderer',context=context)
        result.update(before_characters=len(result['before']),after_characters=len(result['after']))
        report['cases'].append(result)
    return report


if __name__=='__main__':
    git('diff','--quiet');git('diff','--cached','--quiet')
    result=replay()
    with Path(sys.argv[1]).open('x',encoding='utf-8') as output:
        json.dump(result,output,ensure_ascii=False,indent=2)
    if len(result['cases'])!=16 or any(row['missing_visible_fields'] for row in result['cases']):
        raise SystemExit('Incomplete replay or missing visible original field')
    print('16 cases; original visible fields retained; zero model calls')
