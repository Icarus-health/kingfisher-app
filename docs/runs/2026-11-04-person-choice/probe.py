"""Bounded synthetic namesake probe of the actual working-memory answer path."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO / 'sidecar'), str(REPO / 'scripts')]
from icarus_memory import MemoryBackend, SelfModelStore, working_memory_answers
from icarus_memory.agent import Agent
from icarus_memory.audit import AuditLog
from icarus_memory.claims import ClaimStore
from icarus_memory.episodes import EpisodeStore, EpisodeKind
from icarus_memory.model import Provenance, SourceType
from icarus_memory.policy import Policy
from icarus_memory.satzpruefung_modell import tor
from icarus_memory.working_memory_store import WorkingMemoryStore
from icarus_memory.local_model_guard import verify_local_model
from probe_intake_precision import _mac_resource_check
from probe_mail_intake_quality import NativeProbe, resources, stop_reason

MODEL = 'kingfisher-qwen3.5:9b-8k'
OUT = Path(sys.argv[1])
CASES = [
    ('ambiguous', 'Wo erreiche ich Alex Winter?', 'meaning_choice', []),
    ('negative', 'Wo erreiche ich Alex Winter, aber nicht aus dem Einkauf?', 'meaning_choice', []),
    ('disputed', 'Welche Belege zeigen, dass Alex Winter im Einkauf arbeitet?', 'meaning_choice', []),
    ('contact', 'Wo erreiche ich Alex Winter aus dem Einkauf?', 'working_reports', ['purchasing']),
    ('deadline', 'Bis wann soll Alex Winter aus dem Einkauf den Angebotsvergleich liefern?', 'working_reports', ['purchasing']),
    ('explicit', 'Bis wann soll Alex Winter (winter@beta.example) den Stundenplan liefern?', 'working_reports', ['school']),
]
SOURCES = [
    ('purchasing', 'winter@alpha.example', 'Kontakt Einkauf',
     'Alex Winter aus dem Einkauf ist unter einkauf@example.invalid erreichbar. '
     'Alex Winter hat zugesagt, den Angebotsvergleich bis zum 6. November 2026 an Sören zu liefern.'),
    ('school', 'winter@beta.example', 'Kontakt Schule',
     'Alex Winter an der Schule ist unter schule@example.invalid erreichbar. '
     'Alex Winter hat zugesagt, den Stundenplan bis zum 13. November 2026 an Sören zu liefern.'),
]
report = dict(suite='person-answer-local-v1', synthetic_only=True, model=MODEL,
              status='started', live_model_verified=False, model_calls=[], rows=[], resources=[],
              cloud_calls=0, import_resumed=False, ingestion='deterministic; not intake evaluation',
              semantic_search='off; BGE verified separately', sentence_verifier='same model',
              cases=CASES, sources=SOURCES, mac_interaction='not tested',
              dataset_sha256=hashlib.sha256(json.dumps([CASES, SOURCES], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
              code_sha256={p: hashlib.sha256((REPO/p).read_bytes()).hexdigest() for p in [
                  'sidecar/icarus_memory/personenfrage.py', 'sidecar/icarus_memory/agent.py']})
with OUT.open('x') as f:
    json.dump(report, f)
os.chmod(OUT, 0o600)

def save():
    tmp = OUT.with_suffix('.tmp')
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    os.chmod(tmp, 0o600)
    tmp.replace(OUT)

start = time.monotonic()
def guard():
    _mac_resource_check(MODEL)
    memory = resources()
    report['resources'].append(memory)
    why = stop_reason(time.monotonic()-start, memory, 240)
    if why:
        raise RuntimeError(why)

class BoundedNative(NativeProbe):
    def _call(self, *args, **kwargs):
        guard()
        try:
            return super()._call(*args, **kwargs)
        finally:
            guard()

try:
    guard()
    provider = BoundedNative(MODEL, report, save, limit=20)
    identity = verify_local_model(provider.base, expected_num_ctx=8192)
    report['local_model_digest'] = identity.digest
    with tempfile.TemporaryDirectory(prefix='kf-person-answer-') as directory:
        os.environ['ICARUS_DATA_DIR'] = directory
        episodes = EpisodeStore(Path(directory)/'episodes.sqlite3')
        claims = ClaimStore(Path(directory)/'claims.sqlite3')
        audit = AuditLog(Path(directory)/'audit.sqlite3')
        try:
            memory = WorkingMemoryStore(episodes)
            aliases = {}
            before = {}
            for alias, email, title, body in SOURCES:
                episode, _ = episodes.record(EpisodeKind.MESSAGE, title, body,
                    Provenance(SourceType.EMAIL, 'synthetic:' + alias),
                    participants=[f'Alex Winter <{email}>'])
                aliases[episode.id] = alias
                snapshot = memory.pending(episode_ids=[episode.id])[0]
                assert memory.commit(snapshot, [{'start':0, 'end':len(body), 'kind':'fact'}], model='synthetic:deterministic')
                before[episode.id] = episodes.get(episode.id).to_dict()
            saved = None
            for qid, question, status, expected in CASES:
                guard()
                report['question_id'] = qid
                provider.prior_calls = {}
                agent = Agent(SelfModelStore(MemoryBackend(), 'synthetic'), Policy(), audit, {},
                              provider=provider, episodes=episodes, knowledge=claims)
                agent._frage_anbieter = lambda: provider
                agent._working_memory_search = None
                agent._saetze = True
                agent._pruefung = lambda: tor('an', provider)
                tick, calls = time.monotonic(), len(report['model_calls'])
                turn = agent.answer_memory(question)
                context = turn.context
                actual = context.get('answer_contract', {}).get('status')
                answer = context.get('working_answer', {})
                selected = sorted({aliases.get(r['episode_id'], 'unmapped') for r in answer.get('refs', [])})
                displayed = sorted({aliases.get(r['episode_id'], 'unmapped') for r in context.get('source_links', [])})
                choices = sorted({aliases.get(i, 'unmapped') for option in context.get('meaning_choice', {}).get('options', []) for i in option.get('ids', [])})
                new = report['model_calls'][calls:]
                checks = {'status': actual == status, 'selected_sources': selected == expected,
                          'displayed_sources': displayed == expected,
                          'calls_successful': all(c['status']=='completed' for c in new),
                          'clarifies_before_model': not new and choices == ['purchasing', 'school'] if status=='meaning_choice' else bool(new)}
                report['rows'].append(dict(id=qid, question=question, expected_status=status,
                    status=actual, expected_sources=expected, selected=selected, displayed=displayed,
                    choices=choices, checks=checks, passed=all(checks.values()), reply=turn.reply,
                    working_answer=answer, calls=len(new), seconds=round(time.monotonic()-tick,3)))
                if saved is None and answer.get('refs'):
                    saved = answer
                print(json.dumps({k:report['rows'][-1][k] for k in ['id','status','passed','calls','seconds']}, ensure_ascii=False), flush=True)
                save()
            report['originals_unchanged'] = all(episodes.get(i).to_dict()==value for i,value in before.items())
            if saved:
                for identifier in {r['episode_id'] for r in saved['refs']}:
                    episodes.ignore(identifier)
                text, links, status = working_memory_answers.render(saved, episodes, claims)
                report['withdrawal'] = {'status':status,'pass':status=='working_unavailable' and not links}
            report['live_model_verified'] = verify_local_model(provider.base, expected_num_ctx=8192)==identity and bool(report['model_calls'])
            report['status'] = 'passed' if (all(r['passed'] for r in report['rows']) and len(report['rows'])==len(CASES)
                and report['originals_unchanged'] and report.get('withdrawal',{}).get('pass') and report['live_model_verified']) else 'failed'
        finally:
            audit.close(); claims.close(); episodes.close()
except Exception as exc:
    report.update(status='failed', error=type(exc).__name__ + ': ' + str(exc))
finally:
    report['seconds'] = round(time.monotonic()-start,3)
    report['prose_review'] = 'pending; source/status checks alone are not full answer acceptance'
    save()
print(json.dumps({k:report.get(k) for k in ['status','seconds','live_model_verified','error']}, ensure_ascii=False))
sys.exit(0 if report['status']=='passed' else 1)
