"""Verdrahtung des Rückkanals für Fehler (`rueckmeldung.py`, `rueckmeldung_faelle.py`).

* `POST /api/v1/rueckmeldungen`: „Stimmt nicht?“ unter einer Antwort. Die Oberfläche schickt nur
  Gespräch, Nachricht, Art und den optionalen Text „Richtig wäre …“. Frage, Antwort, Satz- und
  Belegstruktur, Belege und Modellstand liest der Server selbst aus dem Gespräch: Was gemeldet wird,
  ist damit genau das, was gesagt wurde, und nicht, was der Browser behauptet.
* `GET /api/v1/rueckmeldungen`: die Meldungen mit Zählung, neueste zuerst.
* `PATCH /api/v1/rueckmeldungen/{id}/erledigt`: abhaken. Der Fall bleibt in der Exportdatei.
* `GET /api/v1/rueckmeldungen/faelle`: alle Meldungen als Datei im Fragenformat der Messlatte
  (Frage- und Antworttexte, nur für diesen Rechner).

Nichts davon ist außenwirksam, und nichts davon schreibt ins Gedächtnis, in Quellen, Akten oder
Vorschläge. Die Meldung ist eine Notiz des Nutzers.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from . import logbuch, rueckmeldung_faelle
from .model_roles import ROLLEN, rollen_von
from .rueckmeldung import ART_TEXTE, ARTEN, RueckmeldungFehler, Rueckmeldungen


class RueckmeldungIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    conversation_id: str = Field(min_length=1, max_length=200)
    message_id: str = Field(min_length=1, max_length=200)
    art: Literal['falsch', 'unvollstaendig', 'veraltet', 'zu_langsam', 'sonstiges']
    richtig: str = Field(default='', max_length=2000)


def belege_der_antwort(metadaten: dict[str, Any]) -> list[str]:
    """Die Kennungen der Episoden, auf die sich die Antwort stützte (Satzbelege, Quellenzeilen, Quellenbericht)."""
    kontext = (metadaten or {}).get('context') or {}
    kennungen: list[str] = []
    for beleg in (kontext.get('satzantwort') or {}).get('belege') or []:
        kennungen.append(beleg.get('episode_id'))
    for link in kontext.get('source_links') or []:
        kennungen.append(link.get('episode_id'))
    for ref in (kontext.get('source_answer') or {}).get('refs') or []:
        kennungen.append(ref.get('episode_id'))
    return sorted({k for k in kennungen if isinstance(k, str) and k})


def struktur_der_antwort(metadaten: dict[str, Any]) -> dict[str, Any]:
    """Satz- und Belegstruktur ohne Quellentext: Sätze mit Belegnummern, Belege mit Nummer, Kennung und Titel."""
    kontext = (metadaten or {}).get('context') or {}
    satz = kontext.get('satzantwort') or {}
    struktur: dict[str, Any] = {}
    if satz.get('saetze'):
        struktur['saetze'] = [{'text': s.get('text', ''), 'belege': list(s.get('belege') or [])} for s in satz['saetze']]
        struktur['belege'] = [{'nummer': b.get('nummer'), 'episode_id': b.get('episode_id'), 'titel': b.get('titel', '')}
                              for b in satz.get('belege') or []]
    status = (kontext.get('answer_contract') or {}).get('status')
    if status:
        struktur['status'] = status
    return struktur


def modellstand(app) -> dict[str, Any]:
    """Wer gerade antwortet: je Rolle Anbieter, Modell und ob lokal. Keine Schlüssel, keine Adressen."""
    stand: dict[str, Any] = {}
    try:
        rollen = rollen_von(app)
        for rolle in ROLLEN:
            anbieter = rollen.provider(rolle)
            wahl = rollen.wahlen.get(rolle)
            stand[rolle] = {'anbieter': getattr(anbieter, 'name', '') or '', 'modell': getattr(anbieter, 'model', '') or '',
                            'lokal': bool(getattr(anbieter, 'is_local', False)),
                            'eigene_wahl': bool(wahl and not wahl.ist_leer)}
    except Exception:  # noqa: BLE001 - der Modellstand ist Beiwerk und darf die Meldung nie verhindern
        return stand
    return stand


def register(app, guard, data_dir) -> None:
    app.state.rueckmeldungen = Rueckmeldungen(data_dir() / 'rueckmeldungen.sqlite3')   # nach einer Wiederherstellung neu geöffnet

    def ablage() -> Rueckmeldungen:
        return app.state.rueckmeldungen

    @app.post('/api/v1/rueckmeldungen', dependencies=guard, status_code=201)
    def melden(body: RueckmeldungIn) -> dict[str, Any]:
        """Hält fest, dass eine Antwort nicht stimmt. Ändert nichts außer dieser Notiz."""
        # Die Ansicht des Gesprächs, nicht der Rohspeicher: Quellenantworten stehen dort nur als Verweis und werden
        # erst beim Anzeigen zu Text. Gemeldet wird, was der Nutzer gelesen hat.
        nachrichten = app.state.gespraech_ansicht(body.conversation_id)['messages']
        stelle = next((i for i, m in enumerate(nachrichten) if m['id'] == body.message_id and m['role'] == 'assistant'), None)
        if stelle is None:
            raise HTTPException(status_code=404, detail='Diese Antwort gibt es nicht mehr.')
        antwort = nachrichten[stelle]
        # Die Frage ist die nächste Nutzernachricht davor; bei gleichem Zeitstempel (eingefrorene Uhr der Messlatte)
        # steht die Reihenfolge nicht fest, dann gilt die jüngste Nutzernachricht des Gesprächs.
        frage = next((m['content'] for m in reversed(nachrichten[:stelle]) if m['role'] == 'user'),
                     next((m['content'] for m in reversed(nachrichten) if m['role'] == 'user'), ''))
        try:
            meldung = ablage().melden(
                frage=frage, antwort=antwort['content'], art=body.art, richtig=body.richtig,
                nachricht_id=antwort['id'], gespraech_id=body.conversation_id,
                struktur=struktur_der_antwort(antwort.get('metadata')), belege=belege_der_antwort(antwort.get('metadata')),
                modell=modellstand(app))
        except RueckmeldungFehler as fehler:
            raise HTTPException(status_code=422, detail=str(fehler)) from None
        logbuch.vermerke('rueckmeldung', sorte=body.art)
        return {'meldung': meldung, **ablage().zaehlen()}

    @app.get('/api/v1/rueckmeldungen', dependencies=guard)
    def liste(status: Literal['offen', 'erledigt'] | None = Query(None)) -> dict[str, Any]:
        return {'meldungen': ablage().liste(status=status), 'zaehlung': ablage().zaehlen(),
                'arten': [{'id': art, 'text': ART_TEXTE[art]} for art in ARTEN]}

    @app.get('/api/v1/rueckmeldungen/faelle', dependencies=guard)
    def faelle() -> JSONResponse:
        """Alle Meldungen, auch erledigte, als Fälle im Fragenformat der Messlatte. Enthält Frage- und Antworttexte."""
        return JSONResponse(rueckmeldung_faelle.faelle(ablage().liste()),
                            headers={'Content-Disposition': 'attachment; filename="rueckmeldungen-faelle.json"',
                                     'Cache-Control': 'no-store'})

    @app.patch('/api/v1/rueckmeldungen/{kennung}/erledigt', dependencies=guard)
    def erledigt(kennung: str) -> dict[str, Any]:
        meldung = ablage().erledigt(kennung)
        if meldung is None:
            raise HTTPException(status_code=404, detail='Diese Meldung gibt es nicht.')
        return {'meldung': meldung, **ablage().zaehlen()}
