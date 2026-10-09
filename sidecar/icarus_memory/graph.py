"""Das vernetzte Gedächtnis als belegte, neu berechenbare Ansicht.

Der Graph ist bewusst **keine** weitere Ablage. Episoden bleiben Rohmaterial,
Projekte und Aufgaben bleiben die Arbeitsebene und bestätigte Aussagen bleiben
im Selbstmodell. Dieses Modul verbindet ihre stabilen Kennungen zu Knoten und
Kanten. Wird eine Quelle korrigiert, wird die Ansicht beim nächsten Aufruf aus
dem aktuellen Bestand neu aufgebaut.

Wichtigste Grenze: Eine Mail oder ein Gespräch ist ein Beleg dafür, dass etwas
gesagt wurde, nicht dafür, dass sein Inhalt wahr ist. Deshalb heißen die Kanten
zu Episoden ``participated_in`` und nie etwa ``works_for`` oder ``lives_in``.
Solche fachlichen Beziehungen dürfen erst durch eine bestätigte, strukturierte
Aussage entstehen.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from . import entscheidungen, identitaet, personen
from .episodes import Episode, EpisodeState
from .model import Assertion, now
from .people_quality import annotate_people, ist_sammelpostfach, lokalteil


def _stable(prefix: str, value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{digest}"


def person_id(name: str) -> str:
    """Legacy-Namensprojektion; keine bestätigte Identitätsauflösung."""
    return _stable("person", personen.schluessel(name))


def person_id_fuer(schluessel: str) -> str:
    """Kennung eines Personenknotens aus seinem Anker (`a:<adresse>` oder `n:<name>`).

    Ein Name ohne Adresse behält die Kennung der früheren Namensprojektion; so
    bleiben Zusammenführungen, die auf ihr beruhen, gültig.
    """
    return _stable("person", schluessel if schluessel.startswith("a:") else schluessel[2:])


def topic_id(label: str) -> str:
    return _stable("topic", label.strip().casefold())


@dataclass(frozen=True)
class GraphNode:
    id: str
    kind: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "attributes": dict(self.attributes),
        }


@dataclass(frozen=True)
class GraphEdge:
    id: str
    source: str
    target: str
    relation: str
    evidence_refs: tuple[str, ...]
    scope: str | None = None
    confidence: float = 1.0
    state: str = "observed"
    original_edges: tuple[dict[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "scope": self.scope,
            "confidence": self.confidence,
            "state": self.state,
            "evidence_refs": list(self.evidence_refs),
            **({"original_edges": list(self.original_edges)} if self.original_edges else {}),
        }


@dataclass
class KnowledgeGraph:
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.astimezone().isoformat(),
            "authority": "projection",
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


_DIRECTORY_KINDS = {"person", "project", "topic", "decision"}


def entity_directory(knowledge_graph: KnowledgeGraph) -> list[dict[str, Any]]:
    """Liefert ein deterministisches Entitätsverzeichnis aus dem Graphen.

    Die Ansicht führt keinen eigenen Bestand: Namen, Verbindungen und Quellen
    kommen ausschließlich aus Knoten und Kanten des gerade berechneten
    Graphen. Damit kann eine spätere Profiloberfläche auf stabile Referenzen
    verlinken, ohne einen zweiten, potenziell widersprüchlichen Speicher
    einzuführen.
    """
    nodes = {node.id: node for node in knowledge_graph.nodes}
    connected: dict[str, list[GraphEdge]] = {node_id: [] for node_id in nodes}
    for edge in knowledge_graph.edges:
        connected.setdefault(edge.source, []).append(edge)
        connected.setdefault(edge.target, []).append(edge)

    entries: list[dict[str, Any]] = []
    for node in knowledge_graph.nodes:
        if node.kind not in _DIRECTORY_KINDS:
            continue
        sources: dict[str, dict[str, Any]] = {}

        def add_source(candidate: GraphNode) -> None:
            source_type = candidate.attributes.get("source_type")
            if not isinstance(source_type, str) or not source_type:
                return
            source_ref = candidate.attributes.get("source_ref")
            occurred_at = candidate.attributes.get("occurred_at")
            key = "|".join((candidate.id, source_type, str(source_ref or "")))
            sources.setdefault(
                key,
                {
                    "node_id": candidate.id,
                    "source_type": source_type,
                    "source_ref": source_ref if isinstance(source_ref, str) else None,
                    "occurred_at": occurred_at if isinstance(occurred_at, str) else None,
                },
            )

        add_source(node)
        for edge in connected.get(node.id, []):
            for evidence_ref in edge.evidence_refs:
                evidence_node = nodes.get(evidence_ref)
                if evidence_node is not None:
                    add_source(evidence_node)

        relations = connected.get(node.id, [])
        entries.append(
            {
                "id": node.id,
                "kind": node.kind,
                "label": node.label,
                "attributes": dict(node.attributes),
                "connection_count": len(relations),
                "sources": sorted(
                    sources.values(),
                    key=lambda item: (
                        item["occurred_at"] is None,
                        item["occurred_at"] or "",
                        item["node_id"],
                    ),
                    reverse=True,
                ),
            }
        )
    return sorted(entries, key=lambda item: (item["kind"], item["label"].casefold(), item["id"]))


class _Builder:
    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: dict[tuple[str, str, str, str | None], GraphEdge] = {}

    def node(self, node: GraphNode) -> None:
        self.nodes.setdefault(node.id, node)

    def edge(
        self,
        source: str,
        target: str,
        relation: str,
        evidence_ref: str,
        *,
        scope: str | None = None,
        confidence: float = 1.0,
        state: str = "observed",
    ) -> None:
        key = (source, target, relation, scope)
        existing = self.edges.get(key)
        refs = set(existing.evidence_refs if existing else ())
        refs.add(evidence_ref)
        refs_tuple = tuple(sorted(refs))
        edge_key = "|".join((source, target, relation, scope or "", *refs_tuple))
        self.edges[key] = GraphEdge(
            id=_stable("edge", edge_key),
            source=source,
            target=target,
            relation=relation,
            evidence_refs=refs_tuple,
            scope=scope,
            confidence=min(existing.confidence, confidence) if existing else confidence,
            state=existing.state if existing and existing.state == state else state,
        )


def _episode_node(episode: Episode) -> GraphNode:
    return GraphNode(
        id=f"episode:{episode.id}",
        kind="episode",
        label=episode.title,
        attributes={
            "episode_kind": episode.kind.value,
            "state": episode.state.value,
            "occurred_at": episode.occurred_at.astimezone().isoformat() if episode.occurred_at else None,
            "recorded_at": episode.recorded_at.astimezone().isoformat(),
            "source_type": episode.provenance.source_type.value,
            "source_ref": episode.provenance.source_ref,
            "digest": episode.digest,
        },
    )


def _assertion_node(assertion: Assertion) -> GraphNode:
    kind = "decision" if assertion.kind.value == "decision" else "assertion"
    return GraphNode(
        id=f"assertion:{assertion.id}",
        kind=kind,
        label=assertion.statement,
        attributes={
            "assertion_kind": assertion.kind.value,
            "status": assertion.status.value,
            "confidence": assertion.confidence,
            "source_type": assertion.provenance.source_type.value,
            "source_ref": assertion.provenance.source_ref,
        },
    )


def _person_node(nennung: "identitaet.Nennung", verzeichnis: "identitaet.Verzeichnis") -> GraphNode:
    """Der Personenknoten zu einer Nennung: über die Adresse, sonst über den Namen."""
    aufloesung = verzeichnis.aufloesen(nennung)
    kennung = person_id_fuer(aufloesung.schluessel)
    if aufloesung.schluessel.startswith("a:"):
        adresse = aufloesung.schluessel[2:]
        namen = verzeichnis.namen(adresse)
        # Service-Anzeigenamen bleiben lesbar, bilden aber keinen menschlichen Namensalias.
        anzeige = namen[0] if namen else (nennung.name if ist_sammelpostfach(lokalteil(adresse)) else "")
        return GraphNode(kennung, "person", identitaet.beschriftung(adresse, anzeige), {
            "identity_resolution": "address",
            "addresses": [adresse],
            "names": namen,
        })
    art = "name_open" if aufloesung.offen else "name_only"
    return GraphNode(kennung, "person", nennung.name.strip(), {
        "identity_resolution": art,
        "addresses": [],
        "names": [nennung.name.strip()],
        "candidates": list(aufloesung.offen),
    })


def build(
    *,
    episodes: Any,
    workspace: Any,
    tasks: Any,
    store: Any,
    knowledge: Any = None,
    at: datetime | None = None,
    group_people: bool = True,
    eigene: Iterable[str] = (),
) -> KnowledgeGraph:
    """Baut den Graphen ohne Schreibzugriff auf Quellen, Claims und Aufgaben.

    Personen entstehen über ihre Adresse (`identitaet.py`), nicht über den
    Namenstext. `eigene` sind die Adressen des Nutzers; sie sind keine Knoten.
    Einzige Ausnahme vom Nur-Lesen: Mit `knowledge` werden alte Personenzusammenführungen
    auf die heutigen Kennungen übertragen (einmalig, idempotent, umkehrbar).
    """
    builder = _Builder()
    eigene = list(eigene)
    verzeichnis = identitaet.Verzeichnis.aus(
        (e for e in episodes.each_episode() if e.state is not EpisodeState.IGNORED), eigene)
    projects = {p.id: p for p in workspace.projects(include_closed=True)}

    for project in projects.values():
        project_node = GraphNode(
            id=f"project:{project.id}",
            kind="project",
            label=project.name,
            attributes={
                "status": project.status.value,
                "area": project.area,
                "priority": project.priority.value,
            },
        )
        builder.node(project_node)
        for tag in project.tags:
            topic = GraphNode(topic_id(tag), "topic", tag)
            builder.node(topic)
            builder.edge(
                project_node.id,
                topic.id,
                "has_topic",
                f"project:{project.id}",
                scope=project.id,
            )

    # Der ganze Bestand, nicht die neuesten N: eine feste Grenze ließe ältere
    # Quellen still aus dem Graphen fallen.
    for episode in episodes.each_episode():
        if episode.state is EpisodeState.IGNORED:
            continue
        episode_node = _episode_node(episode)
        builder.node(episode_node)
        project_node_id = f"project:{episode.project_id}" if episode.project_id else None
        if project_node_id and episode.project_id in projects:
            builder.edge(
                episode_node.id,
                project_node_id,
                "belongs_to",
                f"episode:{episode.id}",
                scope=episode.project_id,
            )

        people: list[str] = []
        for nennung in identitaet.nennungen(episode, eigene):
            if nennung.ich:
                continue
            node = _person_node(nennung, verzeichnis)
            pid = node.id
            people.append(pid)
            builder.node(node)
            builder.edge(
                pid,
                episode_node.id,
                "participated_in",
                f"episode:{episode.id}",
                scope=episode.project_id,
            )
            if project_node_id and episode.project_id in projects:
                builder.edge(
                    pid,
                    project_node_id,
                    "involved_in",
                    f"episode:{episode.id}",
                    scope=episode.project_id,
                )

        for tag in episode.tags:
            topic = GraphNode(topic_id(tag), "topic", tag)
            builder.node(topic)
            builder.edge(
                episode_node.id,
                topic.id,
                "about",
                f"episode:{episode.id}",
                scope=episode.project_id,
            )
            for pid in people:
                builder.edge(
                    pid,
                    topic.id,
                    "mentioned_in_context",
                    f"episode:{episode.id}",
                    scope=episode.project_id,
                )

    for note in workspace.notes(limit=-1):
        node = GraphNode(
            f"note:{note.id}",
            "document",
            note.title,
            {
                "document_kind": note.kind.value,
                "revision": note.revision,
                "source_type": note.provenance.source_type.value,
                "source_ref": note.provenance.source_ref,
            },
        )
        builder.node(node)
        if note.project_id and note.project_id in projects:
            builder.edge(
                node.id,
                f"project:{note.project_id}",
                "belongs_to",
                f"note:{note.id}",
                scope=note.project_id,
            )
        for tag in note.tags:
            topic = GraphNode(topic_id(tag), "topic", tag)
            builder.node(topic)
            builder.edge(node.id, topic.id, "about", f"note:{note.id}", scope=note.project_id)

    for task in tasks.all_tasks(limit=5000):
        node = GraphNode(
            f"task:{task.id}",
            "task",
            task.title,
            {"status": task.status.value, "due": task.to_dict()["due"]},
        )
        builder.node(node)
        if task.project_id and task.project_id in projects:
            builder.edge(
                node.id,
                f"project:{task.project_id}",
                "belongs_to",
                f"task:{task.id}",
                scope=task.project_id,
            )
        if task.wartet_auf:
            # Wie jede Namensnennung: nur bei genau einem Träger des Namens
            # dessen Knoten, sonst offen (siehe `identitaet.py`).
            node_person = _person_node(identitaet.Nennung(task.wartet_auf.strip(), ""), verzeichnis)
            pid = node_person.id
            builder.node(node_person)
            builder.edge(
                node.id,
                pid,
                "waiting_on",
                f"task:{task.id}",
                scope=task.project_id,
            )

    assertions: Iterable[Assertion] = store.alles()
    assertion_items = list(assertions)
    assertion_ids = {a.id for a in assertion_items}
    claim_ids = {f"claim:{item.id}" for item in knowledge.all_claims(include_inactive=True)} if knowledge is not None else set()
    for assertion in assertion_items:
        builder.node(_assertion_node(assertion))
    for decision in entscheidungen.alle(store, knowledge=knowledge):
        source = f"assertion:{decision.id}"
        project_id = (decision.aussage.structured or {}).get("project_id")
        if project_id in projects:
            builder.edge(source, f"project:{project_id}", "belongs_to", source, scope=project_id)
        for basis in decision.grundlage:
            if basis.id in assertion_ids or basis.id in claim_ids:
                edge_state = (
                    "confirmed" if basis.status.value == "active" else basis.status.value
                )
                builder.edge(
                    source,
                    basis.id if basis.id.startswith("claim:") else f"assertion:{basis.id}",
                    "based_on",
                    source,
                    state=edge_state,
                )

    if knowledge is not None:
        registry = {item["id"]: item for item in knowledge.entities.list()}
        for entity in registry.values():
            builder.node(GraphNode(entity["id"], entity["kind"], entity["label"],
                                   {"identity_resolution": "explicit_registry"}))
        usable_ids = {item.id for item in knowledge.all_claims(include_inactive=False, at=at)}
        for claim in knowledge.all_claims(include_inactive=True, limit=5000):
            subject_kind = (
                "person" if claim.subject_ref.startswith("person:")
                else "project" if claim.subject_ref.startswith("project:")
                else "entity"
            )
            builder.node(
                GraphNode(
                    claim.subject_ref,
                    subject_kind,
                    registry.get(claim.subject_ref, {}).get("label", claim.subject_ref),
                    {"identity_resolution": "explicit_registry" if claim.subject_ref in registry else "legacy_reference"},
                )
            )
            claim_node = GraphNode(
                f"claim:{claim.id}",
                "claim",
                claim.statement,
                {
                    "predicate": claim.predicate,
                    "value": claim.value,
                    "status": claim.status.value,
                    "confidence": claim.confidence,
                    "scope_ref": claim.scope_ref,
                    "target_ref": claim.target_ref,
                    "valid_from": claim.valid_from.isoformat() if claim.valid_from else None,
                    "valid_until": claim.valid_until.isoformat() if claim.valid_until else None,
                    "usable": claim.id in usable_ids,
                    "depends_on": list(claim.depends_on),
                },
            )
            builder.node(claim_node)
            # Fachliche Direktkanten zeigen ausschließlich derzeit nutzbares
            # Wissen. Historie bleibt an den belegten Claim-Knoten sichtbar.
            if claim.target_ref and claim.id in usable_ids:
                target = registry.get(claim.target_ref)
                builder.node(GraphNode(claim.target_ref,
                                       target["kind"] if target else "entity",
                                       target["label"] if target else claim.value))
                builder.edge(claim.subject_ref, claim.target_ref, claim.predicate,
                             f"claim:{claim.id}", scope=claim.scope_ref,
                             confidence=claim.confidence if claim.confidence is not None else 1.0,
                             state="active")
            for evidence in claim.evidence:
                builder.edge(
                    claim.subject_ref,
                    claim_node.id,
                    claim.predicate,
                    f"episode:{evidence.episode_id}",
                    scope=claim.scope_ref,
                    confidence=claim.confidence if claim.confidence is not None else 1.0,
                    state=claim.status.value,
                )

    result = KnowledgeGraph(
        nodes=annotate_people(sorted(builder.nodes.values(), key=lambda n: (n.kind, n.label.casefold(), n.id))),
        edges=sorted(
            builder.edges.values(),
            key=lambda e: (e.relation, e.source, e.target, e.scope or ""),
        ),
        generated_at=at or now(),
    )

    if knowledge is not None:
        # Zusammenführungen aus der Zeit vor den Adress-Kennungen finden ihre Mitglieder wieder
        # (schreibt nur in die Zusammenführungen; siehe `person_merge_altkennung`).
        from .person_merge_altkennung import nachziehen
        nachziehen(knowledge.person_merges, episodes, tasks=tasks, eigene=eigene, verzeichnis=verzeichnis,
                   bekannt={node.id for node in result.nodes if node.kind == "person"})
    if knowledge is not None and group_people:
        from .person_merges import project
        return project(result, knowledge.person_merges.list())
    return result


def person_profile(
    name: str,
    *,
    episodes: Any,
    workspace: Any,
    tasks: Any,
    store: Any,
    knowledge: Any = None,
    at: datetime | None = None,
    eigene: Iterable[str] = (),
) -> dict[str, Any] | None:
    """CRM-artige Sicht, ausschließlich aus belegten Beziehungen.

    `name` ist eine Adresse, ein Name oder „Name <adresse>“. Trägt ein Name
    mehrere Menschen, ist keiner der richtige: `personen.Mehrdeutig` mit allen
    Kandidaten, statt zwei Menschen in einem Profil zu mischen.
    """
    moment = at or now()
    gefunden = personen.finden_mit_quellen(
        name,
        episodes=episodes,
        tasks=tasks,
        store=store,
        workspace=workspace,
        jetzt=moment,
        eigene=eigene,
    )
    if not gefunden:
        return None
    if len(gefunden) > 1:
        raise personen.Mehrdeutig(name, [person for person, _ in gefunden])
    person, quellen = gefunden[0]

    related = [episodes.get(episode_id) for episode_id in dict.fromkeys(quellen)]
    related = [episode for episode in related if episode.state is not EpisodeState.IGNORED]
    # Neueste zuerst, wie zuvor.
    related.sort(key=lambda episode: episode.occurred_at or episode.recorded_at, reverse=True)
    projects_by_id = {p.id: p for p in workspace.projects(include_closed=True)}
    contexts: dict[str, dict[str, Any]] = {}
    for episode in related:
        if episode.project_id and episode.project_id in projects_by_id:
            project = projects_by_id[episode.project_id]
            entry = contexts.setdefault(
                project.id,
                {
                    "project": project.to_dict(),
                    "evidence_refs": [],
                    "last_interaction": None,
                },
            )
            entry["evidence_refs"].append(f"episode:{episode.id}")
            stamp = episode.occurred_at.astimezone().isoformat() if episode.occurred_at else None
            if stamp is not None and (entry["last_interaction"] is None or stamp > entry["last_interaction"]):
                entry["last_interaction"] = stamp

    interactions = [
        {
            "id": episode.id,
            "kind": episode.kind.value,
            "title": episode.title,
            "occurred_at": episode.occurred_at.astimezone().isoformat() if episode.occurred_at else None,
            "recorded_at": episode.recorded_at.astimezone().isoformat(),
            "project_id": episode.project_id,
            "source_type": episode.provenance.source_type.value,
            "source_ref": episode.provenance.source_ref,
            "digest": episode.digest,
        }
        for episode in related
    ]
    kennung = person_id_fuer(person.id)
    active_claims, claim_history = _profile_claims(knowledge, kennung)
    return {
        "id": kennung,
        "authority": "projection",
        "person": person.to_dict(),
        "contexts": sorted(contexts.values(), key=lambda c: c["project"]["name"].casefold()),
        "interactions": interactions,
        # `claims` ist bewusst nur der aktuelle, ausdrücklich bestätigte
        # Stand. Ersetzte Aussagen bleiben daneben als Historie sichtbar,
        # damit eine Korrektur weder wie eine Löschung noch wie eine zweite
        # gleichwertige Wahrheit wirkt.
        "claims": active_claims,
        "claim_history": claim_history,
    }


def project_profile(
    project_id: str,
    *,
    episodes: Any,
    workspace: Any,
    tasks: Any,
    knowledge: Any = None,
    eigene: Iterable[str] = (),
) -> dict[str, Any]:
    """Projektakte aus Projekt, Quellen, Beteiligten, Aufgaben und Notizen."""
    project = workspace.project(project_id)
    related = [episode for episode in episodes.by_project(project_id, limit=-1)
               if episode.state is not EpisodeState.IGNORED]
    eigene = list(eigene)
    # Das Verzeichnis über den ganzen Bestand braucht nur, wer Namen ohne
    # Adresse einordnen muss; Adressen tragen sich selbst.
    braucht_verzeichnis = any(not n.adresse and not n.ich
                              for e in related for n in identitaet.nennungen(e, eigene))
    verzeichnis = identitaet.Verzeichnis.aus(
        (e for e in episodes.each_episode() if e.state is not EpisodeState.IGNORED) if braucht_verzeichnis
        else related, eigene)
    people: dict[str, dict[str, Any]] = {}
    for episode in related:
        for nennung in identitaet.nennungen(episode, eigene):
            if nennung.ich:
                continue
            knoten = _person_node(nennung, verzeichnis)
            pid = knoten.id
            entry = people.setdefault(
                pid,
                {"id": pid, "name": knoten.label, "evidence_refs": [], "last_interaction": None,
                 "identity_resolution": knoten.attributes["identity_resolution"]},
            )
            if f"episode:{episode.id}" in entry["evidence_refs"]:
                continue
            entry["evidence_refs"].append(f"episode:{episode.id}")
            stamp = episode.occurred_at.astimezone().isoformat() if episode.occurred_at else None
            if stamp is not None and (entry["last_interaction"] is None or stamp > entry["last_interaction"]):
                entry["last_interaction"] = stamp

    active_claims, claim_history = _profile_claims(knowledge, f"project:{project_id}")
    # Bestätigte Verbindungen ergänzen die Quellenkontakte anhand ihrer IDs.
    # Weder Namen abgleichen noch aus einer Erwähnung eine Mitgliedschaft machen.
    if knowledge is not None:
        for claim in active_claims:
            for ref in {claim.get("subject_ref"), claim.get("target_ref")} - {None}:
                entity = knowledge.entities.get(ref)
                if entity is None or entity["kind"] != "person":
                    continue
                entry = people.setdefault(f"registry:{ref}", {
                    "id": ref, "name": entity["label"], "evidence_refs": [],
                    "last_interaction": None, "identity_resolution": "explicit_registry",
                })
                for evidence in claim["evidence"]:
                    evidence_ref = f"episode:{evidence['episode_id']}"
                    if evidence_ref not in entry["evidence_refs"]:
                        entry["evidence_refs"].append(evidence_ref)
    return {
        "id": f"project:{project.id}",
        "authority": "projection",
        "project": project.to_dict(),
        "people": sorted(people.values(), key=lambda p: p["name"].casefold()),
        "episodes": [
            {
                "id": episode.id,
                "kind": episode.kind.value,
                "title": episode.title,
                "occurred_at": episode.occurred_at.astimezone().isoformat() if episode.occurred_at else None,
                "recorded_at": episode.recorded_at.astimezone().isoformat(),
                "source_type": episode.provenance.source_type.value,
                "source_ref": episode.provenance.source_ref,
                "digest": episode.digest,
            }
            for episode in related
        ],
        "tasks": [task.to_dict() for task in tasks.by_project(project_id, include_closed=True)],
        "notes": [note.to_dict() for note in workspace.notes(project_id=project_id, limit=-1)],
        "claims": active_claims,
        "claim_history": claim_history,
    }


def _profile_claims(knowledge: Any, subject_ref: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Trennt aktuellen Wissensstand von ersetzter Historie.

    Die Claim-Ablage ist append-only. Profile dürfen diese Eigenschaft nicht
    verstecken, aber der aktuelle Arbeitskontext darf auch nicht von
    überholten Aussagen überlagert werden. Der Store ist die führende Quelle
    für den Status; diese Projektion ordnet nur für die Lesesicht.
    """
    if knowledge is None:
        return [], []
    all_claims = knowledge.by_reference(subject_ref, include_inactive=True)
    active_ids = {claim.id for claim in knowledge.by_reference(subject_ref)}
    active = [claim.to_dict() for claim in all_claims if claim.id in active_ids]
    history = [claim.to_dict() for claim in all_claims if claim.id not in active_ids]
    return active, history


__all__ = [
    "entity_directory",
    "GraphEdge",
    "GraphNode",
    "KnowledgeGraph",
    "build",
    "person_id",
    "person_profile",
    "project_profile",
    "topic_id",
]
