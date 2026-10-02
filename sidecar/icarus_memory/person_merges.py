"""Explicit, reversible person groups; original identities and evidence stay intact.

Only the graph projection is grouped. Claims retain their original subject and
validity; this decision never promotes observed source text to confirmed fact.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from .entities import EntityError, EntityRegistry, _label

TABLES = {'person_merges': {'id', 'label', 'members', 'created_at', 'undone_at'}}


def install_schema(connection):
    connection.execute('''CREATE TABLE person_merges (
        id TEXT PRIMARY KEY, label TEXT NOT NULL, members TEXT NOT NULL,
        created_at TEXT NOT NULL, undone_at TEXT
    )''')


def preview(raw, member_ids: list[str], label: str) -> dict[str, Any]:
    label = _label(label)
    if not 2 <= len(member_ids) <= 20 or len(set(member_ids)) != len(member_ids):
        raise EntityError('Bitte zwei bis zwanzig unterschiedliche Personen auswählen.')
    by_id = {node.id: node for node in raw.nodes}
    members = []
    for member_id in sorted(member_ids):
        node = by_id.get(member_id)
        if (node is None or node.kind != 'person'
                or node.attributes.get('identity_resolution') == 'confirmed_group'
                or node.attributes.get('quality_category') in ('automated', 'review')):
            raise EntityError('Eine ausgewählte Person ist nicht mehr verfügbar oder noch ungeklärt.')
        members.append(node.to_dict())
    ids = set(member_ids)
    edges = sorted((edge.to_dict() for edge in raw.edges
                    if edge.source in ids or edge.target in ids), key=lambda edge: edge['id'])
    # Only stable identity/source fields: unrelated incoming mail and generated
    # timestamps must not invalidate an otherwise unchanged preview.
    material = {'label': label, 'members': [
        {key: member[key] for key in ('id', 'kind', 'label')} for member in members], 'edges': edges}
    token = hashlib.sha256(json.dumps(material, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'member_ids': sorted(member_ids), 'label': label, 'members': members,
            'evidence_count': len({ref for edge in edges for ref in edge['evidence_refs']}),
            'preview_token': token}


class PersonMerges(EntityRegistry):
    """Uses the knowledge store's connection and lock, including cross-process locking."""

    def list(self):
        with self._transaction(immediate=False):
            rows = self._connection.execute(
                'SELECT id, label, members, created_at, undone_at FROM person_merges ORDER BY created_at, id'
            ).fetchall()
        return [{'id': row[0], 'label': row[1], 'members': json.loads(row[2]),
                 'created_at': row[3], 'undone_at': row[4]} for row in rows]

    def confirm(self, proposed, *, confirmed: bool):
        if confirmed is not True:
            raise EntityError('Bitte die Zusammenführung ausdrücklich bestätigen.')
        members = proposed['members']
        ids = {member['id'] for member in members}
        if not 2 <= len(ids) <= 20 or len(ids) != len(members):
            raise EntityError('Ungültige Personenauswahl.')
        label = _label(proposed['label'])
        record = {'id': f'merge:{uuid.uuid4().hex}', 'label': label,
                  'members': members, 'created_at': datetime.now(timezone.utc).isoformat(), 'undone_at': None}
        with self._transaction():
            active = self._connection.execute('SELECT members FROM person_merges WHERE undone_at IS NULL').fetchall()
            if any(ids.intersection(member['id'] for member in json.loads(row[0])) for row in active):
                raise EntityError('Eine Person gehört bereits zu einer Zusammenführung. Bitte zuerst diese aufheben.')
            self._connection.execute(
                'INSERT INTO person_merges(id,label,members,created_at) VALUES (?,?,?,?)',
                (record['id'], label, json.dumps(members, ensure_ascii=False), record['created_at']))
        return record

    def mitglieder_ersetzen(self, merge_id: str, members: list[dict[str, Any]]) -> None:
        """Schreibt die Mitgliederliste einer aktiven Zusammenführung neu (Übertragung alter Kennungen).

        Nur für `person_merge_altkennung`: Sie behält die alten Kennungen am Mitglied
        (`alt_ids`) und ändert weder Beschriftung der Gruppe noch Quellen. Eine
        aufgehobene Zusammenführung wird nicht angefasst.
        """
        with self._transaction():
            self._connection.execute('UPDATE person_merges SET members=? WHERE id=? AND undone_at IS NULL',
                                     (json.dumps(members, ensure_ascii=False), merge_id))

    def undo(self, merge_id: str, *, confirmed: bool):
        if confirmed is not True:
            raise EntityError('Bitte das Aufheben ausdrücklich bestätigen.')
        with self._transaction():
            cursor = self._connection.execute(
                'UPDATE person_merges SET undone_at=? WHERE id=? AND undone_at IS NULL',
                (datetime.now(timezone.utc).isoformat(), merge_id))
            if cursor.rowcount != 1:
                raise EntityError('Diese Zusammenführung besteht nicht mehr. Bitte neu laden.')
        return {'undone': True}


def project(raw, records):
    from .graph import GraphNode
    active = [record for record in records if not record['undone_at']]
    if not active:
        return raw
    by_id = {node.id: node for node in raw.nodes}
    mapping = {}
    groups = []
    for record in active:
        # A withdrawn source cannot be resurrected from the historical snapshot.
        present = [member for member in record['members'] if member['id'] in by_id]
        # Was nicht mehr zuzuordnen ist, verschwindet nicht still: Die Gruppe nennt es.
        lost = [{'id': member['id'], 'label': member.get('label', ''),
                 'alt_ids': member.get('alt_ids', []), 'reason': 'Nicht mehr zuordenbar'}
                for member in record['members'] if member['id'] not in by_id]
        if not present and not any(member.get('nicht_zuordenbar') for member in record['members']):
            continue
        mapping.update({member['id']: record['id'] for member in present})
        groups.append(GraphNode(record['id'], 'person', record['label'], {
            'identity_resolution': 'confirmed_group', 'merge_id': record['id'],
            'quality_category': 'person', 'quality_reason': '',
            'duplicate_ids': [], 'duplicate_reason': '',
            'member_ids': [member['id'] for member in present],
            'unassigned_members': lost,
        }))
    from .people_quality import annotate_people
    from .graph import _stable
    combined = {}
    untouched = []
    internal = {}
    for edge in raw.edges:
        source, target = mapping.get(edge.source, edge.source), mapping.get(edge.target, edge.target)
        if source == edge.source and target == edge.target:
            untouched.append(edge)
            continue
        if source == target:
            internal.setdefault(source, []).append(edge.to_dict())
            continue
        # Different validity states must never be promoted by aggregation.
        key = (source, target, edge.relation, edge.scope, edge.state)
        existing = combined.get(key)
        refs = tuple(sorted(set(edge.evidence_refs) | set(existing.evidence_refs if existing else ())))
        originals = (existing.original_edges if existing else ()) + (edge.to_dict(),)
        combined[key] = replace(edge, id=_stable('edge', json.dumps([*key, *refs])),
                                source=source, target=target, evidence_refs=refs,
                                confidence=min(edge.confidence, existing.confidence) if existing else edge.confidence,
                                original_edges=originals)
    groups = [replace(node, attributes={**node.attributes,
              'internal_relations': internal.get(node.id, [])}) for node in groups]
    nodes = annotate_people([node for node in raw.nodes if node.id not in mapping]) + groups
    return replace(raw, nodes=sorted(nodes, key=lambda node: (node.kind, node.label.casefold(), node.id)),
                   edges=sorted(untouched + list(combined.values()),
                                key=lambda edge: (edge.relation, edge.source, edge.target, edge.scope or '', edge.state)))
