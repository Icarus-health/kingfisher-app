"""Verdrahtung des Lint über alle Akten (`lint.py`): Hintergrundlauf, Anstoß, Befunde, Entscheidung.

* Im Hintergrund läuft der Lint nach dem Abgleich der Bezüge, im selben Faden wie dieser
  (`akten_routes.nachlauf_anmelden`), also nie parallel zu ihm und nie in einer Anfrage. Gedrosselt:
  höchstens alle `ABSTAND_S` Sekunden und nur, wenn sich seit dem letzten Lauf etwas geändert hat.
* `POST /api/v1/lint`: ein Lauf auf Anstoß (Prüfung, Diagnose, „Jetzt prüfen“).
* `GET  /api/v1/lint/befunde?status=offen`: die Befunde mit Namen der Sachen, Titeln der Belege und
  dem Stand ihrer Vorschläge, dazu `lint.zusammenfassung`.
* `PATCH /api/v1/lint/befunde/{id}`: „Erledigt“, „Ignorieren“ oder zurück auf offen. Offene Vorschläge
  des Befunds werden dabei abgelehnt: Nichts wird Wissen, was niemand gewählt hat.
* `POST /api/v1/lint/befunde/{id}/entscheiden`: bei Widersprüchen die Wahl „alt“ oder „neu“. Erst
  dieser Klick eines Menschen macht aus einem Vorschlag Wissen.

Wie bei einer Berichtigung (`/api/v1/memory/claims/{id}/correct`) steht die angenommene Aussage auf
einer eigenen Quelle „vom Nutzer entschieden“, nicht auf der Mail: Eine Quelle, die in bestätigtes
Wissen eingegangen ist, zeigt die Akte nicht mehr roh (`mappe.lesen`); die Mail mit der neuen Frist
bliebe sonst gerade dort unsichtbar, wo der Widerspruch aufgefallen ist. Der Vorschlag des Lint mit
der Mail als Beleg bleibt als Spur (Zustand „abgelöst“).
"""
from __future__ import annotations

import json
import hashlib
import threading
import time
from datetime import datetime
from typing import Any, Literal

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict

from .lint import MIT_VORSCHLAG, Befunde, Entwurf, Pruefer, vorschlagen, zusammenfassung

#: Mindestabstand zweier Läufe im Hintergrund (Sekunden).
ABSTAND_S = 600.0

_LINT_SPERRE = threading.Lock()


class StatusIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: Literal['offen', 'erledigt', 'abgewiesen']
    stand: str | None = None


class WahlIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    wahl: Literal['alt', 'neu']
    stand: str | None = None


def _quellenstand(app, eintrag: dict[str, Any]) -> str:
    """Bind a displayed choice to both its finding and current source bodies."""
    ids = {b['episode_id'] for b in eintrag['belege']}
    if app.state.episodes.usable_ids(ids) != ids:
        raise HTTPException(status_code=409, detail='Eine Quelle wurde zurückgezogen oder ersetzt. Bitte neu laden.')
    sources = []
    for id in sorted(ids):
        snapshot = app.state.episodes.support_snapshot(id)
        if snapshot is None or not snapshot.current():
            raise HTTPException(status_code=409, detail='Eine Quellengrundlage hat sich geändert. Bitte neu laden.')
        sources.append((id, snapshot.support_fingerprint()))
    return hashlib.sha256(json.dumps([eintrag, sources], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def ablage(app) -> Befunde:
    return app.state.lint_befunde


def _stand(app) -> tuple:
    """Was sich ändern muss, damit ein neuer Lauf etwas Neues finden kann (Speicher, Wissen, Projekte).

    Gemessen nach dem Lauf: Was der Lauf selbst schreibt (Zwischenspeicher der Akten), zählt nicht als Änderung.
    """
    from .akten_routes import bausteine
    bezuege, _ = bausteine(app)
    claims = getattr(app.state, 'claims', None)
    return (bezuege.aenderungsstand(), getattr(claims, 'revision', 0), id(app.state.episodes))


def faellig(app) -> bool:
    """Billig: Mindestabstand vorbei und seit dem letzten Lauf etwas geändert."""
    letzter = getattr(app.state, 'lint_letzter', None)
    abstand = getattr(app.state, 'lint_abstand_s', ABSTAND_S)
    if letzter is not None and time.monotonic() - letzter[0] < abstand:
        return False
    return letzter is None or letzter[1] != _stand(app)


def ausfuehren(app, *, jetzt: datetime | None = None) -> dict[str, Any]:
    """Ein Lauf: prüfen, Befunde abgleichen, fehlende Vorschläge anlegen, entschiedene Vorschläge nachziehen.

    Läuft schon einer, kommt `{'laeuft': True}` zurück, statt zu warten.
    """
    if not _LINT_SPERRE.acquire(blocking=False):
        return {'laeuft': True}
    try:
        from .akten_routes import bausteine
        from .lage_routes import lagen_von
        bezuege, akten = bausteine(app)
        ergebnis = Pruefer(app.state.episodes, bezuege, akten, claims=getattr(app.state, 'claims', None),
                           workspace=getattr(app.state, 'workspace', None), lagen=lagen_von(app), jetzt=jetzt).pruefen()
        abgleich = ablage(app).abgleichen(ergebnis.befunde, dauer_s=ergebnis.dauer_s, sachen=ergebnis.sachen)
        neue_vorschlaege = 0
        service = getattr(app.state, 'knowledge_service', None)
        if service is not None:
            with app.state.conversation_lock:
                neue_vorschlaege = vorschlagen(ablage(app), service, app.state.episodes)
        nachgezogen = vorschlaege_nachziehen(app)
        app.state.lint_letzter = (time.monotonic(), _stand(app))
        return {'laeuft': False, 'befunde': len(ergebnis.befunde), 'neu': abgleich['neu'],
                'entfallen': abgleich['entfallen'], 'vorschlaege': neue_vorschlaege, 'nachgezogen': nachgezogen,
                'sachen': ergebnis.sachen, 'dauer_s': ergebnis.dauer_s, 'nicht_geprueft': ergebnis.nicht_geprueft}
    finally:
        _LINT_SPERRE.release()


def vorschlaege_nachziehen(app) -> int:
    """Wurde ein Vorschlag eines offenen Befunds anderswo entschieden, ist der Befund erledigt."""
    from .proposals import ProposalError, ProposalState
    zahl = 0
    for eintrag in ablage(app).liste(status='offen'):
        zustaende = []
        for v in eintrag['vorschlaege']:
            try:
                zustaende.append(app.state.proposals.get(v['id']).state)
            except ProposalError:
                zustaende.append(None)
        if zustaende and all(z is not ProposalState.PENDING for z in zustaende):
            ablage(app).status_setzen(eintrag['id'], 'erledigt', entschieden='vorschlag')
            zahl += 1
    return zahl


def _offene_ablehnen(app, eintrag: dict[str, Any]) -> None:
    from .proposals import ProposalError, ProposalState
    for v in eintrag['vorschlaege']:
        try:
            if app.state.proposals.get(v['id']).state is ProposalState.PENDING:
                app.state.knowledge_service.reject(v['id'])
        except ProposalError:
            continue


def _annehmen(app, vorschlag_id: str, entwurf: Entwurf, befund: dict[str, Any]) -> Any:
    """Die Wahl des Nutzers wird Wissen: auf einer Quelle „vom Nutzer entschieden“, nie still."""
    from .episodes import EpisodeKind
    from .model import Provenance, SourceType
    from .proposals import Evidence
    inhalt = {'entscheidung': 'lint', 'befund': befund['id'], 'art': befund['art'], 'wahl': entwurf.wahl,
              'aussage': entwurf.statement, 'subject_ref': entwurf.subject_ref, 'predicate': entwurf.predicate,
              'value': entwurf.value, 'quelle': entwurf.episode_id, 'zitat': entwurf.zitat}
    episode, _ = app.state.episodes.record(
        EpisodeKind.MESSAGE, 'Entscheidung zu einem Widerspruch',
        json.dumps(inhalt, ensure_ascii=False, sort_keys=True),
        Provenance(source_type=SourceType.USER_STATED, captured_at=datetime.now().astimezone()),
        tags=['knowledge:lint'])
    # Der Vorschlag des Lint (Beleg: die Mail) ist damit entschieden; die Annahme steht auf der Entscheidung.
    app.state.proposals.supersede(vorschlag_id)
    neu, _ = app.state.knowledge_service.propose(
        subject_ref=entwurf.subject_ref, predicate=entwurf.predicate, value=entwurf.value,
        statement=entwurf.statement, rationale=entwurf.rationale, scope_ref=entwurf.scope_ref,
        evidence=[Evidence(episode.id, episode.body, episode.digest)], proposed_by='user:lint')
    return app.state.knowledge_service.accept(neu.id, supersedes=list(entwurf.ersetzt))


def entscheiden(app, kennung: str, wahl: str, stand: str | None = None) -> dict[str, Any]:
    """Die Wahl „alt“ oder „neu“ zu einem Widerspruch. Ein Klick, dann ist der Befund erledigt."""
    from .claims import ClaimError
    from .proposals import ProposalError, ProposalState
    eintrag = ablage(app).get(kennung)
    if eintrag is None:
        raise HTTPException(status_code=404, detail='Diesen Befund gibt es nicht mehr.')
    if eintrag['art'] not in MIT_VORSCHLAG or not eintrag['vorschlaege']:
        raise HTTPException(status_code=409, detail='Zu diesem Befund gibt es nichts zu wählen.')
    if eintrag['status'] != 'offen':
        raise HTTPException(status_code=409, detail='Dieser Befund ist schon entschieden.')
    entwuerfe = {e['wahl']: Entwurf.aus(e) for e in eintrag['entwuerfe']}
    vorschlaege = {v['wahl']: v['id'] for v in eintrag['vorschlaege']}
    aussage = None
    try:
        with app.state.conversation_lock:
            # Fetch again under the same lock as source withdrawal/knowledge decisions.
            aktuell = ablage(app).get(kennung)
            if aktuell != eintrag or aktuell['status'] != 'offen':
                raise HTTPException(status_code=409, detail='Der Befund hat sich geändert. Bitte neu laden.')
            aktuell_stand = _quellenstand(app, aktuell)
            if stand is not None and stand != aktuell_stand:
                raise HTTPException(status_code=409, detail='Der angezeigte Stand hat sich geändert. Bitte neu laden.')
            for claim_id in {id for entwurf in entwuerfe.values() for id in entwurf.ersetzt}:
                from .knowledge_render import KnowledgeInputBuild
                if KnowledgeInputBuild(app.state.claims, app.state.episodes.support_snapshot).capture(claim_id) is None:
                    raise HTTPException(status_code=409, detail='Eine bisherige Aussage oder ihre Grundlage ist nicht mehr aktuell. Bitte neu laden.')
                claim = app.state.claims.get(claim_id)
                if not app.state.claims.is_usable(claim):
                    raise HTTPException(status_code=409, detail='Die bisherige Aussage hat sich geändert. Bitte neu laden.')
                ids = {item.episode_id for item in claim.evidence}
                if app.state.episodes.usable_ids(ids) != ids:
                    raise HTTPException(status_code=409, detail='Die bisherige Quelle ist nicht mehr aktuell. Bitte neu laden.')
                for evidence in claim.evidence:
                    app.state.knowledge_service._validate(evidence)
            for vorschlag_id in vorschlaege.values():
                proposal = app.state.proposals.get(vorschlag_id)
                if proposal.state is not ProposalState.PENDING:
                    raise HTTPException(status_code=409, detail='Der Vorschlag wurde inzwischen anders entschieden. '
                                                                'Bitte die Liste neu laden.')
                for evidence in proposal.evidence:
                    app.state.knowledge_service._validate(evidence)
            if wahl in vorschlaege:
                aussage = _annehmen(app, vorschlaege[wahl], entwuerfe[wahl], eintrag)
            for andere, vorschlag_id in vorschlaege.items():
                if andere != wahl and app.state.proposals.get(vorschlag_id).state is ProposalState.PENDING:
                    app.state.knowledge_service.reject(vorschlag_id)
            befund = ablage(app).status_setzen(kennung, 'erledigt', entschieden=wahl)
    except (ClaimError, ProposalError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    app.state.audit.record('lint_entscheiden', 'write_local', 'confirm', 'approved',
                           {'befund': kennung, 'wahl': wahl}, detail='Widerspruch per Klick entschieden.')
    return {'befund': befund, 'aussage': aussage.to_dict() if aussage is not None else None,
            'zusammenfassung': zusammenfassung(app)}


def _anreichern(app, eintraege: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Namen der Sachen und Titel der Belege aus dem Original; Befunde mit entzogener Quelle fehlen."""
    from .akten_routes import bausteine
    from .bezuege import ART_TEXT, zerlegen
    from .proposals import ProposalError
    bezuege, _ = bausteine(app)
    ids = {b['episode_id'] for e in eintraege for b in e['belege']}
    geltend = app.state.episodes.usable_ids(ids)
    sachen = sorted({s for e in eintraege for s in e['sachen'] if zerlegen(s)})
    namen = bezuege.beschriftungen(sachen) if sachen else {}
    titel: dict[str, dict[str, Any]] = {}
    ergebnis = []
    for eintrag in eintraege:
        if any(b['episode_id'] not in geltend for b in eintrag['belege']):
            continue
        try:
            eintrag['stand'] = _quellenstand(app, eintrag)
        except HTTPException:
            continue
        for b in eintrag['belege']:
            if b['episode_id'] not in titel:
                episode = app.state.episodes.get(b['episode_id'])
                titel[b['episode_id']] = {'titel': episode.title[:160],
                                         'datum': episode.occurred_at.isoformat() if episode.occurred_at else None,
                                         'recorded_at': episode.recorded_at.isoformat(), 'digest': episode.digest}
            b.update(titel[b['episode_id']])
            episode = app.state.episodes.get(b['episode_id'])
            start, ende = b.get('start', -1), b.get('ende', -1)
            b['zitat'] = episode.body[start:ende] if 0 <= start < ende <= len(episode.body) else ''
            if not b['zitat']:
                b['zitat'] = next((e['zitat'] for e in eintrag.get('entwuerfe', [])
                                   if e['episode_id'] == b['episode_id'] and e['zitat'] in episode.body), '')
        eintrag['sachen'] = [{'sache': s, 'name': namen.get(s, s), 'art_text': ART_TEXT.get((zerlegen(s) or ('', ''))[0], '')}
                             for s in eintrag['sachen'] if zerlegen(s)]
        vorschlaege = []
        for v in eintrag['vorschlaege']:
            try:
                p = app.state.proposals.get(v['id'])
            except ProposalError:
                continue
            vorschlaege.append({'wahl': v['wahl'], 'id': p.id, 'zustand': p.state.value, 'aussage': p.statement,
                                'wert': p.value})
        eintrag['vorschlaege'] = vorschlaege
        eintrag.pop('entwuerfe', None)
        ergebnis.append(eintrag)
    return ergebnis


def register(app, guard, data_dir) -> None:
    app.state.lint_befunde = Befunde(data_dir() / 'lint.sqlite3')   # nach einer Wiederherstellung neu geöffnet
    # Der erste Lauf im Hintergrund frühestens nach dem Mindestabstand: Beim Start ist anderes dringender.
    app.state.lint_letzter = (time.monotonic(), None)
    from .akten_routes import nachlauf_anmelden

    def im_hintergrund() -> None:
        ausfuehren(app)

    nachlauf_anmelden(app, lambda: faellig(app), im_hintergrund)

    @app.post('/api/v1/lint', dependencies=guard)
    def lint_anstossen() -> dict[str, Any]:
        """Prüft alle Akten jetzt. Legt Befunde und Vorschläge an, schreibt nie einen Fakt."""
        from .akten_routes import nachfuehren
        nachfuehren(app, warten=True)
        lauf = ausfuehren(app)
        return {'lauf': lauf, 'zusammenfassung': zusammenfassung(app)}

    @app.get('/api/v1/lint/befunde', dependencies=guard)
    def lint_befunde(status: Literal['offen', 'erledigt', 'abgewiesen'] | None = Query('offen')) -> dict[str, Any]:
        with app.state.conversation_lock:
            vorschlaege_nachziehen(app)
            return {'befunde': _anreichern(app, ablage(app).liste(status=status)),
                    'zusammenfassung': zusammenfassung(app), 'laeuft': _LINT_SPERRE.locked()}

    @app.patch('/api/v1/lint/befunde/{kennung}', dependencies=guard)
    def lint_status(kennung: str, body: StatusIn) -> dict[str, Any]:
        """„Erledigt“, „Ignorieren“ (abgewiesen) oder zurück auf offen. Nie ein Fakt."""
        with app.state.conversation_lock:
            eintrag = ablage(app).get(kennung)
            if eintrag is None:
                raise HTTPException(status_code=404, detail='Diesen Befund gibt es nicht mehr.')
            if body.status != 'offen' or body.stand is not None:
                stand = _quellenstand(app, eintrag)
                if body.stand is not None and body.stand != stand:
                    raise HTTPException(status_code=409, detail='Der Befund wurde inzwischen geändert. Bitte neu laden.')
            if body.status != 'offen':
                _offene_ablehnen(app, eintrag)
            else:
                # Reopening only schedules fresh proposals in the next check.
                ablage(app).vorschlaege_setzen(kennung, [])
            befund = ablage(app).status_setzen(kennung, body.status)
        return {'befund': befund, 'zusammenfassung': zusammenfassung(app)}

    @app.post('/api/v1/lint/befunde/{kennung}/entscheiden', dependencies=guard)
    def lint_entscheiden(kennung: str, body: WahlIn) -> dict[str, Any]:
        return entscheiden(app, kennung, body.wahl, body.stand)
