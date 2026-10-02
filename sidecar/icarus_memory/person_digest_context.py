"""Bounded, exact-identity context for a derived AI person overview."""
import hashlib
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from . import graph
from .identitaet import eigene_adressen
from .episodes import EpisodeError, EpisodeKind, EpisodeState
from .source_snapshot import quote_matches

MAX_SOURCES = 12
MAX_SOURCE_CHARS = 1400


def _evidence_available(app, claim):
    from .knowledge_context import evidence_chain_available
    return evidence_chain_available(claim, app.state.claims, app.state.episodes, mode="historical")


def collect(app, person_ref):
    raw = graph.build(episodes=app.state.episodes, workspace=app.state.workspace,
                      tasks=app.state.tasks, store=app.state.store, knowledge=app.state.claims,
                      group_people=False, eigene=eigene_adressen(getattr(app.state, "settings", None)))
    nodes = {node.id: node for node in raw.nodes}
    # Wer an welcher Quelle beteiligt ist, sagt der Graph selbst (Adressanker,
    # ohne die eigenen Adressen), nicht ein zweites Mal der Namenstext.
    beteiligte: dict[str, set[str]] = {}
    for edge in raw.edges:
        if edge.relation == 'participated_in' and edge.target.startswith('episode:'):
            beteiligte.setdefault(edge.target.removeprefix('episode:'), set()).add(edge.source)
    group = next((item for item in app.state.claims.person_merges.list()
                  if item['id'] == person_ref and not item['undone_at']), None)
    ids = {member['id'] for member in group['members']} if group else {person_ref}
    people = [nodes[ref] for ref in sorted(ids) if ref in nodes and nodes[ref].kind == 'person']
    if not people or (not group and (person_ref not in nodes or nodes[person_ref].kind != 'person')):
        raise HTTPException(404, 'Dieses Personenprofil ist nicht mehr verfügbar.')
    ids = {node.id for node in people}
    label = group['label'] if group else people[0].label
    claims = {claim.id: claim for ref in ids for claim in app.state.claims.by_reference(ref, include_inactive=True)}
    usable = {claim.id for claim in claims.values() if app.state.claims.is_usable(claim)}
    # Old source wording behind a corrected/retracted claim is not reintroduced
    # as an apparently fresh observation. The explicit history remains labelled.
    historical_evidence = {e.episode_id for claim in claims.values() if claim.id not in usable for e in claim.evidence}
    episode_ids = {ref.removeprefix('episode:') for edge in raw.edges
                   if edge.source in ids or edge.target in ids
                   for ref in edge.evidence_refs if ref.startswith('episode:')}
    sources = []
    skipped_shared = 0
    for episode_id in sorted(episode_ids - historical_evidence):
        try:
            episode = app.state.episodes.get(episode_id)
        except Exception:
            continue
        if episode.state is EpisodeState.IGNORED or episode.kind is EpisodeKind.SUMMARY:
            continue
        if not episode.body.strip():
            continue
        participant_ids = beteiligte.get(episode.id, set())
        if not participant_ids or not participant_ids.issubset(ids):
            skipped_shared += 1
            continue
        sources.append({'ref': f'episode:{episode.id}', 'title': episode.title,
                        'status': 'observed',
                        'occurred_at': episode.occurred_at.isoformat() if episode.occurred_at else None,
                        'recorded_at': episode.recorded_at.isoformat(),
                        'text': episode.body, 'episode_ids': [episode.id], 'digest': episode.digest})
    for claim in claims.values():
        if not _evidence_available(app, claim):
            # Die Kettenprüfung kann einen Entzug nach der Rohquellensammlung
            # erkennen. Auch schon gesammelte Fassungen dürfen dann nicht ins Modell.
            unavailable_refs = {evidence.episode_id for evidence in claim.evidence}
            sources = [source for source in sources if unavailable_refs.isdisjoint(source['episode_ids'])]
            continue
        # Wie beim Wissenskontext bezeichnet das erste Original den Primärbeleg.
        # Die spätere Annahme einer Aussage datiert dessen Ereignis nicht neu.
        evidence = claim.evidence[0]
        try:
            primary = app.state.episodes.get(evidence.episode_id)
            primary_available = (primary.state is not EpisodeState.IGNORED
                and primary.kind is not EpisodeKind.SUMMARY and primary.digest == evidence.digest
                and quote_matches(evidence.quote, primary.body))
        except EpisodeError:
            primary_available = False
        if not primary_available:
            # Der neue Metadatenabruf darf weder einen 500er auslösen noch eine
            # inzwischen entzogene Quelle aus dem früheren Rohquellenlauf behalten.
            sources = [source for source in sources if evidence.episode_id not in source['episode_ids']]
            continue
        sources.append({'ref': f'claim:{claim.id}', 'title': 'Bestätigte Aussage' if claim.id in usable else 'Früherer oder nicht gültiger Stand',
                        'status': 'confirmed' if claim.id in usable else 'historical',
                        'occurred_at': primary.occurred_at.isoformat() if primary.occurred_at else None,
                        'recorded_at': primary.recorded_at.isoformat(),
                        'claim_created_at': claim.created_at.isoformat(), 'text': claim.statement,
                        'episode_ids': [e.episode_id for e in claim.evidence],
                        'claim_status': claim.status.value, 'valid_until': str(claim.valid_until),
                        'subject_ref': claim.subject_ref, 'target_ref': claim.target_ref})
    # Aufnahmezeit ist nur ein Sortierschlüssel, niemals ein Ereignisdatum.
    sources.sort(key=lambda source: (datetime.fromisoformat(source['occurred_at'] or source['recorded_at']).timestamp(), source['ref']), reverse=True)
    # Fingerprint all in-scope material, even beyond the prompt budget. A later
    # correction, exclusion, merge undo, or new source invalidates old output.
    signature = {'person_ref': person_ref, 'label': label,
                 # Je Mitglied alle Adressen und Namen: Der Überblick soll wissen, wer gemeint ist.
                 'members': [{'id': p.id, 'label': p.label, 'addresses': list(p.attributes.get('addresses') or []),
                              'names': list(p.attributes.get('names') or [])} for p in people],
                 'sources': sources}
    fingerprint = hashlib.sha256(json.dumps(signature, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    selected = sources[:MAX_SOURCES]
    prompt_sources = [{**source, 'source_id': f'S{index+1}',
                       'text': source['text'][:MAX_SOURCE_CHARS],
                       'truncated': len(source['text']) > MAX_SOURCE_CHARS}
                      for index, source in enumerate(selected)]
    return {'as_of': datetime.now(timezone.utc).date().isoformat(), 'person': label, 'members': signature['members'], 'sources': prompt_sources,
            'fingerprint': fingerprint, 'source_count': len(selected), 'total_source_count': len(sources) + skipped_shared,
            'truncated': bool(skipped_shared) or len(sources) > len(selected) or any(s['truncated'] for s in prompt_sources)}
