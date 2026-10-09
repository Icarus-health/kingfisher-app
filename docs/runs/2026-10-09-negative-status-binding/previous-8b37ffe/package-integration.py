import copy, json, sys, types
from datetime import datetime, timezone
from pathlib import Path

from icarus_memory.model import Provenance, SourceType
from icarus_memory.episodes import EpisodeKind
from icarus_memory import working_memory_answers as answers
from icarus_memory.providers import Reply
from icarus_memory.episodes import EpisodeStore
from icarus_memory.claims import ClaimStore
from icarus_memory.working_memory_store import WorkingMemoryStore

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
INVOICE = 'Die Rechnung R-719 wurde bezahlt.'
DELIVERY = 'Die Lieferung Z-204 wurde vorbereitet.'
WRONG = 'Die Lieferung Z-204 wurde bezahlt.'

class ScriptedProvider:
    is_local = True
    name = model = 'synthetic-status-binding'
    def __init__(self, answer):
        self.answer = answer
        self.answer_payloads = []
    def complete_json(self, messages, **kwargs):
        payload = json.loads(messages[-1]['content'])
        if 'sources' in payload:
            return Reply(text=json.dumps({'status': 'source_reports', 'ids': [s['id'] for s in payload['sources']]}))
        self.answer_payloads.append(payload)
        if isinstance(self.answer, str):
            # Invoice's numbered evidence ref is selected by its original source text.
            match = next((b['nr'] for b in payload.get('belege', []) if INVOICE in b.get('text', '')),
                         payload.get('belege', [{}])[0].get('nr', 1))
            value = {'status': 'antwort', 'saetze': [{'text': self.answer, 'belege': [b['nr'] for b in payload.get('belege', [])]}]}
        else:
            value = self.answer
        return Reply(text=json.dumps(value, ensure_ascii=False))

def seed(ep, body, title, ref):
    e, _ = ep.record(EpisodeKind.DOCUMENT, title, body,
                     Provenance(SourceType.DOCUMENT, source_ref='synthetic:' + ref), at=NOW)
    assert WorkingMemoryStore(ep).commit(ep.support_snapshot(e.id),
        [{'start': 0, 'end': len(body), 'kind': 'status'}], model='synthetic')
    return e

def main():
    db = Path('/tmp/kingfisher-status-integration-image-20261009')
    db.mkdir(exist_ok=True)
    ep = EpisodeStore(db / 'episodes.sqlite3')
    claims = ClaimStore(db / 'claims.sqlite3')
    inv = seed(ep, INVOICE, 'Rechnung R-719', 'invoice-r719')
    delivery = seed(ep, DELIVERY, 'Lieferung Z-204', 'delivery-z204')
    wrong_query = 'Wurde die Lieferung Z-204 bezahlt?'
    provider = ScriptedProvider(WRONG)
    saved = answers.prepare(wrong_query, ep, claims, provider, saetze=True, semantic_search=None)
    print('observed_prepare', json.dumps({'status': saved['status'], 'sentence_status': saved['satzantwort']['status']}), flush=True)
    assert saved['status'] == 'reports' and saved['satzantwort']['status'] == 'zitate'
    assert len(saved['refs']) == 2
    text, links, status = answers.render(saved, ep, claims)
    assert status == 'working_reports' and WRONG not in text
    assert INVOICE in text and DELIVERY in text
    print('prepare_wrong_status', json.dumps({'answer_status': saved['status'], 'sentence_status': saved['satzantwort']['status'],
          'basis_count': len(saved['basis']), 'selected_source_count': len(saved['refs']), 'model_answer_count': len(provider.answer_payloads),
          'render_status': status, 'wrong_fact_displayed': WRONG in text, 'original_quotes_displayed': [INVOICE in text, DELIVERY in text]}, ensure_ascii=False))
    claims.close(); ep.close()
    ep = EpisodeStore(db / 'episodes.sqlite3'); claims = ClaimStore(db / 'claims.sqlite3')
    text2, links2, status2 = answers.render(saved, ep, claims)
    assert status2 == 'working_reports' and WRONG not in text2 and INVOICE in text2 and DELIVERY in text2
    print('reopen_wrong_status', json.dumps({'render_status': status2, 'wrong_fact_displayed': WRONG in text2,
          'original_quotes_displayed': [INVOICE in text2, DELIVERY in text2], 'source_links': len(links2)}, ensure_ascii=False))

    # Build a genuine valid persisted sentence snapshot, then alter only its free sentence fields.
    good_query = wrong_query
    good_provider = ScriptedProvider(INVOICE)
    good = answers.prepare(good_query, ep, claims, good_provider, saetze=True, semantic_search=None)
    assert good['status'] == 'reports' and good['satzantwort']['status'] == 'saetze'
    legacy = copy.deepcopy(good)
    legacy_sentence = legacy['satzantwort']['saetze'][0]
    legacy_sentence['roh'] = WRONG
    legacy_sentence['text'] = WRONG
    legacy_render, legacy_links, legacy_status = answers.render(legacy, ep, claims)
    assert legacy_status == 'working_reports' and WRONG not in legacy_render and INVOICE in legacy_render
    print('legacy_snapshot_recheck', json.dumps({'seed_sentence_status': good['satzantwort']['status'],
          'stored_sentence_mutated': legacy['satzantwort']['saetze'][0]['text'], 'render_status': legacy_status,
          'wrong_fact_displayed': WRONG in legacy_render, 'original_invoice_quote_displayed': INVOICE in legacy_render,
          'source_links': len(legacy_links)}, ensure_ascii=False))

    # Reopen before revalidating the legacy snapshot, then withdraw its supporting source.
    claims.close(); ep.close()
    ep = EpisodeStore(db / 'episodes.sqlite3'); claims = ClaimStore(db / 'claims.sqlite3')
    legacy_reopened, links3, status3 = answers.render(legacy, ep, claims)
    assert status3 == 'working_reports' and WRONG not in legacy_reopened and INVOICE in legacy_reopened
    print('legacy_reopen_recheck', json.dumps({'render_status': status3, 'wrong_fact_displayed': WRONG in legacy_reopened,
          'original_invoice_quote_displayed': INVOICE in legacy_reopened}, ensure_ascii=False))
    ep.ignore(inv.id)
    after_withdrawal, links4, status4 = answers.render(legacy, ep, claims)
    raw = ep.get(inv.id).body
    assert status4 == 'working_unavailable' and links4 == [] and WRONG not in after_withdrawal and raw == INVOICE
    print('withdrawal', json.dumps({'render_status': status4, 'source_links': len(links4),
          'wrong_fact_displayed': WRONG in after_withdrawal, 'raw_invoice_source_preserved': raw == INVOICE,
          'raw_source': raw}, ensure_ascii=False))
    claims.close(); ep.close()

if __name__ == '__main__': main()
