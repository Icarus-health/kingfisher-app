"""Synthetic audit reproduction; fake vectors isolate coverage, not model quality."""
import json
import tempfile
from pathlib import Path

from tests.test_context import _knowledge_agent
from icarus_memory.knowledge_search import RefreshingKnowledgeSearch, HybridKnowledgeSearch


with tempfile.TemporaryDirectory(prefix='kingfisher-audit-retrieval-') as directory:
    agent, _, episodes, accept = _knowledge_agent(Path(directory))
    created = [accept(f'Archivobjekt Nummer {index} mit Einzelmerkmal{index}.')[0]
               for index in range(130)]
    ids, total = agent._knowledge.semantic_inventory(512)
    target = agent._knowledge.get(ids[-1])

    class SyntheticEmbedder:
        is_local = True
        model_key = 'audit-synthetic-coverage-only-v1'

        def embed(self, texts):
            return [[1.0, 0.0] if text == 'Finanzierungsentscheidung?'
                    or target.statement in text else [0.0, 1.0] for text in texts]

    embedder = SyntheticEmbedder()
    live = RefreshingKnowledgeSearch(embedder, limit=512)
    found, metadata = live.search_context('Finanzierungsentscheidung?', agent._knowledge,
                                          episodes.support_snapshot)
    explicit = HybridKnowledgeSearch.prepare(agent._knowledge, episodes.support_snapshot,
                                               [target.id], embedder)
    selected, _ = explicit.search_context('Finanzierungsentscheidung?', agent._knowledge,
                                           episodes.support_snapshot)
    exact, _ = agent._knowledge.search_context(target.statement.split()[-1])
    result = {'synthetic_only': True, 'real_model_quality_tested': False,
              'total_active_claims': total, 'configured_inventory_limit': 512,
              'cached_claims': live.cached_count, 'coverage': metadata['semantic_coverage'],
              'live_target_found': target.id in {row.id for row in found},
              'explicit_snapshot_target_found': target.id in {row.id for row in selected},
              'exact_lexical_target_found': target.id in {row.id for row in exact}}
    assert result == {'synthetic_only': True, 'real_model_quality_tested': False,
                      'total_active_claims': 130, 'configured_inventory_limit': 512,
                      'cached_claims': 128, 'coverage': 'partial',
                      'live_target_found': False, 'explicit_snapshot_target_found': True,
                      'exact_lexical_target_found': True}
    print(json.dumps(result, indent=2))
