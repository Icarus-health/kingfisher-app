"""„Angenommen“ in der Akte: die Aussagen, die ein Mensch aus einer Antwort übernommen und bestätigt hat.

Bis hierher zeigte die Akte nur Zitate aus Quellen (`akten.py`: „nie Fakt und nie Quelle“). Eine bestätigte Aussage
(`claims.py`) kam in ihr nicht vor; dazu kam: Eine Quelle, die in bestätigtes Wissen einging, wird nirgends mehr roh
gezeigt. Wer einen Satz übernimmt (`uebernehmen.py`), sähe ihn also aus der Akte verschwinden. Dieser Abschnitt schließt
das: Er zeigt die angenommenen Aussagen der Sache, **immer als Aussage, nie als Zitat**, mit ihrem Beleg (Quelle und
wörtliche Textstelle).

**Überholt.** Eine Aussage bleibt nicht ewig wahr. Nennt eine jüngere, noch ungeprüfte Quelle derselben Akte denselben
Gegenstand mit einem anderen Datum (Frist) oder als neuere Änderung oder Statusmeldung (Stand), trägt die Aussage den
Hinweis „überholt“ mit der neueren Angabe, wörtlich, und verweist auf die Quelle. Dieselbe grobe Regel wie bei den
Quellen der Akte (`akten._fristen`, `akten._stand`, `gleicher_gegenstand`), ohne Modell und als Vermutung ausgewiesen:
Die Aussage wird dabei **nicht** widerrufen oder geändert. Was daraus wird, entscheidet der Mensch (Widerruf in der
Vorschlagskarte, neuer Vorschlag aus einer neuen Antwort).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import mappe
from .akten import FRIST_ARTEN, STAND_ARTEN, Abschnitt, _MerkeFrei, _abschnitte_lesen, gleicher_gegenstand, stamm_menge
from .fristen import fristen_in

MAX_AUSSAGEN = 50
ZITAT = 400


def _kurz(text: str, grenze: int = ZITAT) -> str:
    text = ' '.join(str(text or '').split())
    return text if len(text) <= grenze else text[:grenze - 1].rstrip() + '…'


def _zeit(episodes: Any, episode_ids: list[str]) -> datetime | None:
    """Der jüngste fachliche Zeitpunkt der Belege: Was danach kommt, ist jünger als die Aussage."""
    zeiten = episodes.reference_times(episode_ids) if episode_ids else []
    return max(zeiten) if zeiten else None


def ueberholt_durch(statement: str, zeit: datetime, abschnitte: list[Abschnitt]) -> Abschnitt | None:
    """Der jüngste Abschnitt, der die Aussage überholt, sonst None.

    Überholt heißt: jünger als jeder Beleg der Aussage, gleicher Gegenstand (`gleicher_gegenstand`) und entweder eine
    neuere Änderung oder Statusmeldung, oder ein anderes Datum als das der Aussage bei einer Frist-Art. Nennt die jüngere
    Quelle dasselbe Datum, bestätigt sie die Aussage.
    """
    daten = frozenset(f.datum for f in fristen_in(statement, zeit).fristen)
    eigene = Abschnitt({}, zeit, statement, stamm_menge(statement), daten)
    treffer = []
    for a in abschnitte:
        if a.zeit <= zeit or not gleicher_gegenstand(eigene, a):
            continue
        if daten and a.daten and daten & a.daten:
            continue   # dasselbe Datum noch einmal gesagt bestätigt die Aussage, überholt sie nicht
        anderes_datum = bool(daten and a.daten)
        if a.art in STAND_ARTEN or (a.art in FRIST_ARTEN and anderes_datum):
            treffer.append(a)
    return max(treffer, key=lambda a: (a.zeit, a.ref.get('episode_id', ''), a.ref.get('start', 0)), default=None)


def aussagen(akten: Any, sache: str, quellen_ids: list[str]) -> dict[str, Any]:
    """Die angenommenen Aussagen der Sache für die Anzeige der Akte: `{'eintraege': [...], 'gesamt': n}`.

    Je Eintrag: Text, Datum der Annahme, Belege (Quelle, Titel, wörtliche Stelle) und, wenn eine jüngere Quelle den
    Gegenstand anders nennt, `ueberholt` mit der neueren Angabe. Leer, wenn es keine gibt oder kein Wissensbestand da ist.
    """
    claims = getattr(akten, 'claims', None)
    if claims is None:
        return {'eintraege': [], 'gesamt': 0}
    nutzbar = [c for c in claims.by_subject(sache) if claims.is_usable(c)]
    if not nutzbar:
        return {'eintraege': [], 'gesamt': 0}
    # Nur ungeprüfte Quellen können überholen: Was selbst in Wissen einging, steht hier als Aussage.
    abschnitte, _ = _abschnitte_lesen(quellen_ids, akten.store, _MerkeFrei(claims))
    eintraege = []
    for claim in nutzbar[:MAX_AUSSAGEN]:
        belege = []
        ids = []
        for beleg in claim.evidence:
            try:
                episode = akten.episodes.get(beleg.episode_id)
            except Exception:  # noqa: BLE001 - ein nicht mehr lesbarer Beleg bleibt als Kennung stehen
                belege.append({'episode_id': beleg.episode_id, 'titel': '', 'zitat': _kurz(beleg.quote)})
                continue
            ids.append(episode.id)
            belege.append({'episode_id': episode.id, 'titel': episode.title[:200], 'zitat': _kurz(beleg.quote),
                           'datum': episode.reference_time().isoformat()})
        eintrag: dict[str, Any] = {'id': claim.id, 'text': claim.statement, 'angenommen': claim.created_at.isoformat(),
                                   'belege': belege, 'ueberholt': None}
        zeit = _zeit(akten.episodes, ids) or claim.created_at.astimezone(timezone.utc)
        neuer = ueberholt_durch(claim.statement, zeit, abschnitte)
        if neuer is not None:
            gelesen = mappe.lesen(akten.store, neuer.ref, _MerkeFrei(claims))
            eintrag['ueberholt'] = {'episode_id': neuer.ref['episode_id'],
                                    'titel': gelesen[0].title[:200] if gelesen else '',
                                    'datum': neuer.zeit.isoformat(), 'text': _kurz(neuer.text)}
        eintraege.append(eintrag)
    return {'eintraege': eintraege, 'gesamt': len(nutzbar)}
