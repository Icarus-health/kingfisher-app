"""Read-only SelfModel parent assessment; opaque episode/source refs are out of scope.

Snapshots are optimistic, not a cross-store transaction. Callers revalidate before
and after provider use. Parent text is never added to persisted lineage metadata.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from .currency import judge
from .model import Kind, Sensitivity, SourceType, Status

VERSION = 1
MAX_NODES = 128
_RANK = {Sensitivity.NORMAL: 0, Sensitivity.SENSITIVE: 1, Sensitivity.SPECIAL_CATEGORY: 2}


def digest(value):
    document = json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(document.encode()).hexdigest()


def eligible(assertion, at):
    return (assertion.status in {Status.ACTIVE, Status.DISPUTED}
            and (assertion.valid_from is None or assertion.valid_from <= at)
            and (assertion.expires_at is None or at < assertion.expires_at))


def effective(assertion, at):
    if assertion.expires_at is not None and at >= assertion.expires_at:
        return 'expired'
    if assertion.valid_from is not None and at < assertion.valid_from:
        return 'future'
    return assertion.status.value


@dataclass(frozen=True)
class Assessment:
    root: object
    basis: dict
    signature: str
    fingerprint: str


class FrozenBuild:
    """One clock and at most128 distinct captured nodes across all candidate roots."""
    def __init__(self, store, *, at, max_sensitivity, node_limit=MAX_NODES, support_build=None):
        self.support_build = support_build
        self.store = store
        self.at = at
        self.ceiling = _RANK[max_sensitivity]
        self.limit = min(node_limit, MAX_NODES)
        self.nodes = {}
        self.fingerprints = {}
        self.graphs = {}

    def capture(self, identifier, supplied=None):
        if not isinstance(identifier, str) or not identifier:
            return None
        if identifier in self.nodes:
            return self.nodes[identifier]
        if len(self.nodes) >= self.limit:
            return None
        self.nodes[identifier] = None  # missing nodes consume distinct-node budget
        original = supplied if supplied is not None else self.store.get(identifier)
        if original is None:
            return None
        try:
            value = deepcopy(original)
            if (value.id != identifier or not isinstance(value.kind, Kind)
                    or not isinstance(value.status, Status) or value.sensitivity not in _RANK
                    or not isinstance(value.provenance.source_type, SourceType)
                    or not isinstance(value.derived_from, list)
                    or not isinstance(value.supersedes, list)
                    or any(not isinstance(i, str) or not i for i in value.derived_from + value.supersedes)
                    or len(value.derived_from) > self.limit
                    or len(set(value.derived_from)) != len(value.derived_from)):
                return None
            fingerprint = digest(value.to_dict())
            effective(value, self.at)
            judge(value, self.at)
        except (ValueError, TypeError, AttributeError, KeyError):
            return None
        self.nodes[identifier] = value
        self.fingerprints[identifier] = fingerprint
        return value

    def _walk(self, root):
        if root.id in self.graphs:
            return self.graphs[root.id]
        visiting, done = set(), set()
        stack = [(root.id, False)]
        while stack:
            identifier, closing = stack.pop()
            if closing:
                visiting.remove(identifier)
                done.add(identifier)
                continue
            if identifier in done:
                continue
            if identifier in visiting:
                return None
            node = self.capture(identifier)
            if node is None or node.status is Status.REDACTED or _RANK[node.sensitivity] > self.ceiling:
                return None
            visiting.add(identifier)
            stack.append((identifier, True))
            stack.extend((parent, False) for parent in reversed(node.derived_from))
        self.graphs[root.id] = done
        return done

    @staticmethod
    def _finish(child, parent):
        data = child.structured
        return (child.kind is Kind.STATE and isinstance(data, dict)
                and data.get('goal_outcome') in ('achieved', 'stopped')
                and data.get('goal_id') == parent.id and parent.kind is Kind.GOAL
                and parent.id in child.supersedes and parent.id in child.derived_from
                and parent.superseded_by == child.id)

    def _lifecycle(self, child, parent):
        if self._finish(child, parent):
            return True
        if child.kind is not Kind.GOAL or parent.id not in child.supersedes or parent.superseded_by != child.id:
            return False
        data = parent.structured
        original = self.nodes.get(data.get('goal_id')) if isinstance(data, dict) and isinstance(data.get('goal_id'), str) else None
        return original is not None and self._finish(parent, original)

    def assess(self, assertion):
        root = self.capture(getattr(assertion, 'id', None), assertion)
        if root is None or not eligible(root, self.at):
            return None
        graph = self._walk(root)
        if graph is None:
            return None
        changed = ambiguous = False
        supports = []
        for identifier in sorted(graph):
            node = self.nodes[identifier]
            if self.support_build is None:
                # Fehlende Auflösung beweist bei Ableitungen keine Quellenfreiheit.
                if node.episode_support or node.provenance.source_type is SourceType.INFERENCE:
                    return None
                continue
            support = self.support_build.assess(node)
            if not support.complete_private:
                return None
            changed |= not support.usable
            if support.recognized != 'none':
                supports.append([identifier, support.signature])
        edges = []
        lifecycle_root = False
        for identifier in sorted(graph):
            child = self.nodes[identifier]
            for parent_id in sorted(child.derived_from):
                parent = self.nodes[parent_id]
                lifecycle = self._lifecycle(child, parent)
                if identifier == root.id and lifecycle:
                    lifecycle_root = True
                interpretation = ('lifecycle' if lifecycle else
                                  'decision' if child.kind is Kind.DECISION else
                                  'inference' if child.provenance.source_type is SourceType.INFERENCE else 'ambiguous')
                state = effective(parent, self.at)
                changed |= state != 'active' and not (lifecycle and state == 'superseded')
                ambiguous |= interpretation == 'ambiguous'
                edges.append([identifier, parent_id, interpretation])
        if ((changed or ambiguous) and root.kind is not Kind.DECISION and not lifecycle_root
                and root.provenance.source_type is SourceType.INFERENCE):
            return None
        reason = ('changed_and_ambiguous' if changed and ambiguous else
                  'changed' if changed else 'ambiguous' if ambiguous else None)
        basis = {'version': VERSION, 'state': 'review' if reason else 'supported' if root.derived_from else 'none',
                 'reason': reason}
        nodes = [[i, self.fingerprints[i], effective(self.nodes[i], self.at),
                  judge(self.nodes[i], self.at).value, self.nodes[i].sensitivity.value] for i in sorted(graph)]
        signature = digest({'version': VERSION, 'root': root.id, 'nodes': nodes, 'edges': edges, 'basis': basis, 'supports': supports})
        return Assessment(root, basis, signature, self.fingerprints[root.id])
