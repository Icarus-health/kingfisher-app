"""Stufe „Antwort“: die Frage über den echten Antwortpfad stellen.

Gefragt wird wie im Betrieb: Gespräch anlegen, Nachricht mit `answer_mode: auto`
an `POST /api/v1/conversations/{id}/messages`. Der Server entscheidet selbst, ob
er als Gedächtnisfrage (Bedeutungsfrage, Arbeitsstand, Kalender) oder im freien
Chat mit Werkzeugen antwortet. Gelesen werden Antworttext, Status
(`answer_contract.status`), Belege (`working_answer.refs`, `source_links`) und
angebotene Auswahl (`clarification_choices`), so wie `scripts/probe_cos_workweek.py`
es tut.

Jede Frage bekommt ein **neues Gespräch**: Eine Antwort darf nicht vom Verlauf der
vorigen abhängen. Die erste Anfrage wird als `kalt` gekennzeichnet (Modell wird
geladen, Zwischenspeicher sind leer); ihre Zeit fließt nicht in die warmen Zeiten.
"""
from __future__ import annotations

import time

from . import zeiten as antwortzeit
from .daten import Frage
from .ergebnisse import AntwortErgebnis


def _welt(episode_ids, rueck: dict) -> tuple:
    gesehen, ergebnis = set(), []
    for episode_id in episode_ids:
        welt_id = rueck.get(episode_id)
        if welt_id is not None and welt_id not in gesehen:
            gesehen.add(welt_id)
            ergebnis.append(welt_id)
    return tuple(ergebnis)


def antwort_nachricht(antwort: dict) -> dict:
    """Die Assistentennachricht einer Antwort der Konversations-API.

    Nicht blind die letzte: Bei gleichem Zeitstempel (unter der eingefrorenen Uhr
    der Messlatte) ist die Reihenfolge von Frage und Antwort nicht garantiert.
    """
    nachrichten = antwort.get('messages') or []
    gefunden = next((m for m in reversed(nachrichten) if m.get('role') == 'assistant'), None)
    if gefunden is None:
        raise ValueError('Die Antwort enthält keine Assistentennachricht.')
    return gefunden


def lese_nachricht(nachricht: dict, rueck: dict) -> dict:
    """Text, Status, Belege (Welt-IDs, None ohne Ausweis), Auswahl und Zeiten einer Assistentennachricht."""
    kontext = (nachricht.get('metadata') or {}).get('context') or {}
    status = (kontext.get('answer_contract') or {}).get('status', '')
    arbeitsstand = kontext.get('working_answer')
    belege = None
    satz = kontext.get('satzantwort')
    if isinstance(satz, dict):
        # Eine Antwort in Sätzen belegt nur, worauf ihre Sätze sich stützen, nicht alles, was das Modell sah.
        belege = _welt((b.get('episode_id') for b in satz.get('belege', []) if isinstance(b, dict)), rueck)
    elif isinstance(arbeitsstand, dict):
        belege = _welt((r.get('episode_id') for r in arbeitsstand.get('refs', []) if isinstance(r, dict)), rueck)
    elif kontext.get('source_links'):
        belege = _welt((l.get('episode_id') for l in kontext['source_links'] if isinstance(l, dict)), rueck)
    auswahl = tuple(str(c.get('label', '')) for c in kontext.get('clarification_choices') or [] if isinstance(c, dict))
    return {'text': nachricht.get('content', ''), 'status': status, 'belege': belege, 'auswahl': auswahl,
            'zeiten': antwortzeit.lese(kontext.get('zeiten')), **_verworfen(arbeitsstand)}


def _verworfen(arbeitsstand) -> dict:
    """Verworfene Sätze je Tor aus der gespeicherten Satzantwort, auch wenn am Ende der Zitatmodus gilt."""
    roh = arbeitsstand.get('satzantwort') if isinstance(arbeitsstand, dict) else None
    if not isinstance(roh, dict):
        return {}
    pruefung = roh.get('pruefung') if isinstance(roh.get('pruefung'), dict) else {}
    gesamt = roh.get('verworfen', 0) if type(roh.get('verworfen', 0)) is int else 0
    am_tor = pruefung.get('verworfen', 0) if type(pruefung.get('verworfen', 0)) is int else 0
    return {'verworfen_satzpruefung': max(gesamt - am_tor, 0), 'verworfen_pruefmodell': am_tor,
            'pruefung': str(pruefung.get('zustand', 'kein_modell'))}


def antworten(instanz, frage: Frage, rueck: dict, *, kalt: bool = False) -> AntwortErgebnis:
    """Eine Frage an den echten Antwortpfad. Fehler werden zum Ergebnis, nie zur Ausnahme."""
    start = time.perf_counter()
    try:
        gespraech = instanz.anfrage('POST', '/api/v1/conversations', {})['conversation']['id']
        antwort = instanz.anfrage('POST', f'/api/v1/conversations/{gespraech}/messages',
                                  {'message': frage.frage, 'answer_mode': 'auto'})
        nachricht = antwort_nachricht(antwort)
    except Exception as fehler:  # noqa: BLE001
        return AntwortErgebnis(frage_id=frage.id, kalt=kalt, dauer_s=round(time.perf_counter() - start, 3),
                               fehler=f'{type(fehler).__name__}: {fehler}')
    gelesen = lese_nachricht(nachricht, rueck)
    return AntwortErgebnis(frage_id=frage.id, dauer_s=round(time.perf_counter() - start, 3), kalt=kalt, **gelesen)
