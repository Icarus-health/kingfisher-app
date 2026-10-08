"""Kandidaten für eine Frage: Wortsuche im Arbeitsgedächtnis und Volltextindex, vereint.

Zwei Quellen mit verschiedenen Stärken:

* Die Wortsuche des Arbeitsgedächtnisses (``WorkingMemoryStore.search``) kennt
  eingeordnete Abschnitte und ordnet nach Zahl der getroffenen Wörter und
  Aktualität. Sie kennt keine Seltenheit: Ein häufiges Wort zählt wie ein
  seltenes, und bei großem Bestand verdrängen neue Alltagsmails die Treffer.
* Der Volltextindex (``source_index``) findet Wortteile und ordnet nach BM25,
  also nach Seltenheit. Er kennt nur ganze Quellen, keine Abschnitte.

Beide Listen werden über die Quelle (Episode) mit Rangfusion (RRF) vereint. Aus
jeder Quelle kommen höchstens ``MAX_PRO_QUELLE`` Abschnitte; sonst belegten die
Abschnitte einer einzigen Mail den ganzen Platz (gemessen: im Mittel nur 8 von
12 Plätzen gingen an verschiedene Quellen). Die Anzeige zeigt ohnehin den ganzen
Text der Quelle, und jede Zeile des Auswahlkontexts trägt ihn mit. Eine Quelle, die der Index
findet, aber das Arbeitsgedächtnis nicht kennt (noch nicht eingeordnet, zu groß),
kann kein Beleg werden: Sie wird gezählt und im Ergebnis ausgewiesen.

Dieses Modul entscheidet nur die Reihenfolge und den Zuschnitt. Ob eine Quelle
verwendbar ist, prüfen weiterhin ``source_index.suchen`` (Zustand beim Lesen)
und ``WorkingMemoryStore.resolve`` (Beleg, Aktualität) für jeden Abschnitt.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field

from . import source_index

# Gemessen auf 10.000 und 50.000 Rauschquellen (docs/28-suchindex.md): 30 liegt
# zwischen dem Standardwert 60 und der Spitzenwertung 10 und war auf beiden Größen gleich gut.
RRF_K = 30
GEWICHT = (1.0, 1.0)  # Wortsuche, Volltextindex
#: Gewicht der dritten Liste: die bevorzugten Quellen aus den Akten der genannten Sachen (E2, `akten_kontext`).
GEWICHT_OBEN = 1.0
MAX_PRO_QUELLE = 1
POOL = 64  # so viele Quellen je Liste gehen in die Fusion


@dataclass(frozen=True)
class Kandidaten:
    """Abschnitte in Rangfolge, ob mehr passten als geliefert, und die Zählung dazu."""
    refs: list = field(default_factory=list)
    begrenzt: bool = False
    zaehlung: dict = field(default_factory=dict)

    def als_suche(self) -> dict:
        """Dieselbe Form wie ``WorkingMemoryStore.search``."""
        return {"refs": self.refs, "truncated": self.begrenzt}


def rangfusion(listen, k: int | None = None, gewichte=None) -> list:
    """Reciprocal Rank Fusion: Elemente aus mehreren Rangfolgen in eine.

    Ein Element weit vorn in einer Liste schlägt eines mittelmäßig in beiden
    nicht automatisch, aber ein Element in beiden Listen gewinnt gegen eines in
    nur einer, wenn die Ränge ähnlich sind. Bei Gleichstand gilt die Reihenfolge
    des ersten Auftretens (deterministisch).
    """
    k = RRF_K if k is None else k
    punkte: dict = {}
    for nummer, liste in enumerate(listen):
        gewicht = 1.0 if gewichte is None else gewichte[nummer]
        for rang, element in enumerate(liste):
            punkte[element] = punkte.get(element, 0.0) + gewicht / (k + rang + 1)
    return sorted(punkte, key=lambda element: -punkte[element])


def _nach_quelle(refs) -> dict:
    ergebnis: dict = {}
    for ref in refs:
        ergebnis.setdefault(ref["episode_id"], []).append(ref)
    return ergebnis


def _index_signatur(connection, gefunden):
    """Begrenzter Suchbestand mit Quellenversionen, ohne Originaltexte zu lesen."""
    ids = gefunden.episoden
    rows = connection.execute(
        'SELECT e.id,e.metadata_digest,e.support_generation,e.state,s.fingerprint,s.status,s.analysis_version '
        'FROM episodes e LEFT JOIN working_memory_sources s ON s.episode_id=e.id '
        'WHERE e.id IN (' + ','.join('?' for _ in ids) + ') ORDER BY e.id', ids).fetchall() if ids else []
    payload = [gefunden.gesamt, gefunden.begrenzt, gefunden.nicht_indexiert, [list(row) for row in rows]]
    return hashlib.sha256(json.dumps(payload, separators=(',', ':')).encode()).hexdigest()


def zusammenfuehren(store, frage: str, *, limit: int, episode_ids=None, oben=()) -> Kandidaten:
    """Abschnitte zur Frage aus Wortsuche und Volltextindex, höchstens ``limit``.

    ``episode_ids`` begrenzt beide Quellen auf denselben Bereich. Fällt der Index
    aus (Datenbankfehler), gilt allein die Wortsuche; das steht in der Zählung.

    ``oben`` sind die bevorzugten Abschnitte aus den Akten der in der Frage genannten
    Sachen (Verweise in Rangfolge, siehe ``akten_kontext``). Sie bilden eine dritte
    Liste der Rangfusion, nicht einen Vorspann: Eine Quelle, die auch die Suche von unten
    findet, rückt vor; eine, die nur die Akte nennt, konkurriert mit den Treffern. Für
    die Quelle gilt der Abschnitt der Wortsuche, sonst der der Akte, sonst der beste
    für die Suchwörter.
    """
    # Je Quelle nur so viele Verweise, wie aus ihr in den Kontext kommen: Eine lange Quelle mit vielen Abschnitten
    # (`abschnitte.py`) verdrängte sonst mit ihren Treffern die kurzen aus dem Pool.
    wort = store.search(frage, limit=min(POOL, 64), episode_ids=episode_ids, je_quelle=MAX_PRO_QUELLE)
    je_quelle = _nach_quelle(wort["refs"])
    wort_reihenfolge = list(je_quelle)
    oben_je_quelle = _nach_quelle(
        [ref for ref in oben if episode_ids is None or ref["episode_id"] in set(episode_ids)])
    oben_reihenfolge = list(oben_je_quelle)
    zaehlung = {"wortsuche_quellen": len(wort_reihenfolge), "oben_quellen": len(oben_reihenfolge), "wortsuche_begrenzt": bool(wort.get("truncated")),
                "index": "ok", "index_treffer": 0, "index_begrenzt": False, "index_woerter": [],
                "ohne_einordnung": 0, "index_nicht_erfasst": 0}
    index_reihenfolge: list = []
    suchwoerter: tuple = ()
    try:
        with store.episodes._lock:
            gefunden = source_index.suchen(store.episodes._conn, frage, limit=POOL, episode_ids=episode_ids)
            zaehlung['index_signatur'] = _index_signatur(store.episodes._conn, gefunden)
    except sqlite3.Error:
        gefunden = None
        zaehlung["index"] = "nicht verfügbar"
    if gefunden is not None:
        index_reihenfolge = list(gefunden.episoden)
        suchwoerter = (*gefunden.woerter, *gefunden.zusatz)
        zaehlung.update(index_treffer=gefunden.gesamt, index_begrenzt=gefunden.begrenzt,
                        index_woerter=list(suchwoerter), index_nicht_erfasst=gefunden.nicht_indexiert)
    index_luecke = zaehlung['index'] != 'ok' or zaehlung['index_nicht_erfasst'] > 0
    if index_luecke:
        # Ohne vollständigen Index lässt sich die Relevanz neuer Quellen nicht sicher eingrenzen.
        # Nur in diesem Rückfall den vorhandenen corpusweiten Metadaten-Fingerabdruck verwenden.
        zaehlung['index_inventory'] = store.semantic_signature()

    reihenfolge = rangfusion([wort_reihenfolge, index_reihenfolge, oben_reihenfolge],
                             gewichte=(*GEWICHT, GEWICHT_OBEN))
    refs: list = []
    quellen = 0
    uebrig = False
    for episode_id in reihenfolge:
        if len(refs) >= limit:
            uebrig = True  # weitere Quellen wären dran gewesen
            break
        abschnitte = je_quelle.get(episode_id, [])[:MAX_PRO_QUELLE]
        if not abschnitte and episode_id in oben_je_quelle:
            abschnitte = oben_je_quelle[episode_id][:MAX_PRO_QUELLE]
            zaehlung["nur_von_oben"] = zaehlung.get("nur_von_oben", 0) + 1
        if not abschnitte:
            ref = store.best_reference(episode_id, suchwoerter)
            if ref is None:
                if store.source_state(episode_id) not in {'dismissed', 'excluded'}:
                    zaehlung["ohne_einordnung"] += 1
                continue
            abschnitte = [ref]
        if len(abschnitte) > limit - len(refs):
            abschnitte = abschnitte[:limit - len(refs)]
            uebrig = True
        refs.extend(abschnitte)
        quellen += 1
    zaehlung["quellen_geliefert"] = quellen
    begrenzt = bool(uebrig or zaehlung["wortsuche_begrenzt"] or zaehlung["index_begrenzt"]
                    or zaehlung['ohne_einordnung'] or index_luecke)
    return Kandidaten(refs, begrenzt, zaehlung)
