"""Der Stand jedes Postfachs in einem Satz, aus einer Quelle für alle Stellen (Fremdprobe 2, Befund 17).

Vorher sagten drei Stellen Verschiedenes über dasselbe leere Postfach: Heute dauerhaft „Deine Mails werden gelesen:
bisher 0 gefunden“, „Für Techniker“ „Privat: noch nicht abgerufen“ und „Noch kein erfolgreicher automatischer Abruf
bestätigt.“ Der Grund: Das Einlesen (`mail_intake.py`) führt seinen eigenen Stand, der regelmäßige Abruf
(`mail_sync_status.py`) überspringt Postfächer, die eingelesen werden, und ein Abruf über „Nachrichten“ hinterließ gar
nichts. Jetzt gibt es je Postfach genau eine Aussage, gebildet aus allen drei:

* `fehler`: der Grund in Alltagssprache und ob der Mensch etwas tun muss,
* `liest`: „wird gelesen: 120 von 4.300 Mails“ (oder „wird durchgesehen: bisher 12 Mails gefunden“),
* `leer`: „ist verbunden und leer, abgerufen um 14:43“,
* `aktuell`: „ist gelesen: 4.300 Mails, zuletzt abgerufen um 14:43“,
* `pausiert`: das Einlesen ist angehalten,
* `nicht_abgerufen`: verbunden, aber noch nie abgerufen,
* `gescheitert`: nichts ist mehr offen, aber Mails kamen nicht ins Gedächtnis; der Grund in einem Satz, die technische
  Angabe getrennt in `technik` (Fremdprobe 3, Befund 2). Gescheiterte Mails heißen nie „wird gelesen“.

Heute, die Einrichtung (Karte „Kingfisher lernt gerade“) und „Für Techniker“ zeigen denselben Satz. Inhalte von Mails
stehen nie darin, nur Zahlen und Zeiten.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

#: Fehler des Einlesens und des regelmäßigen Abrufs, je in einem Satz (ohne Fehlertext des Servers).
GRUND = {
    'inventory_unavailable': 'antwortet gerade nicht. Du musst nichts tun: Kingfisher versucht es von selbst noch einmal',
    'unavailable': 'antwortet gerade nicht. Du musst nichts tun: Kingfisher versucht es von selbst noch einmal',
    'generation_changed': ('wurde beim Anbieter neu angelegt. Du musst nichts tun: Kingfisher liest es noch einmal '
                           'von vorn'),
    'credentials_missing': 'lässt Kingfisher nicht hinein: Das Passwort fehlt. Trage es unter Einstellungen → Zugänge ein',
    'cancelled': 'wurde beim letzten Mal nicht fertig abgerufen. Du musst nichts tun: Kingfisher versucht es erneut',
}
SONST = 'meldet einen Fehler. Kingfisher versucht es von selbst noch einmal; bleibt es dabei, prüfe es unter Einstellungen → Zugänge'

_gelesen: dict[int, dict[str, dict[str, Any]]] = {}
_sperre = threading.Lock()


def zahl(n: int) -> str:
    return f'{n:,}'.replace(',', '.')


def _mails(n: int) -> str:
    return 'eine Mail' if n == 1 else f'{zahl(n)} Mails'


def zeit_text(zeit: datetime | None, jetzt: datetime | None = None) -> str:
    """„um 14:43“ heute, „am 30. September um 14:43“ an einem anderen Tag, in der Zeitzone des Nutzers."""
    if zeit is None:
        return ''
    from .datumstext import MONATE
    from .model import user_timezone
    zone = user_timezone() or timezone.utc
    zeit = (zeit if zeit.tzinfo else zeit.replace(tzinfo=timezone.utc)).astimezone(zone)
    jetzt = (jetzt or datetime.now(timezone.utc)).astimezone(zone)
    if zeit.date() == jetzt.date():
        return f'um {zeit:%H:%M}'
    return f'am {zeit.day}. {MONATE[zeit.month - 1]} um {zeit:%H:%M}'


def _zeit(wert: Any) -> datetime | None:
    if isinstance(wert, datetime):
        return wert if wert.tzinfo else wert.replace(tzinfo=timezone.utc)
    if isinstance(wert, (int, float)) and not isinstance(wert, bool) and wert > 0:
        return datetime.fromtimestamp(float(wert), timezone.utc)
    if isinstance(wert, str) and wert:
        from .datumstext import iso_versuchen
        return iso_versuchen(wert)
    return None


def merke_gelesen(app: Any, anzahl_je_konto: dict[str, int], *, zeit: datetime | None = None) -> None:
    """Ein erfolgreicher Blick in die Postfächer (Nachrichten, Heute): wann, und wie viele Mails dort lagen.

    Nur im Speicher und nur Zahlen: Das genügt, damit „verbunden und leer“ nicht wie „noch nicht abgerufen“ aussieht.
    """
    zeit = zeit or datetime.now(timezone.utc)
    with _sperre:
        eintraege = _gelesen.setdefault(id(app), {})
        for konto, anzahl in anzahl_je_konto.items():
            eintraege[konto] = {'zeit': zeit, 'anzahl': int(anzahl)}


def gelesen(app: Any, konto: str) -> dict[str, Any] | None:
    with _sperre:
        return dict(_gelesen.get(id(app), {}).get(konto) or {}) or None


def _ergebnis(zustand: str, satz: str, *, gelesen_n: int | None = None, gesamt: int | None = None,
              zuletzt: datetime | None = None, technik: str | None = None) -> dict[str, Any]:
    return {'zustand': zustand, 'satz': satz, 'gelesen': gelesen_n, 'gesamt': gesamt,
            'zuletzt': zuletzt.isoformat() if zuletzt else None, 'technik': technik}


def _gescheitert(ordner: list[dict[str, Any]]) -> tuple[dict[str, int], int, str | None]:
    """Gescheiterte je Grund über alle Ordner, was noch offen ist, und die technische Angabe für „Für Techniker“."""
    je_grund: dict[str, int] = {}
    offen, technik = 0, []
    for o in ordner:
        grunde = {str(k): int(v) for k, v in (o.get('failed_by') or {}).items()}
        for grund, anzahl in grunde.items():
            je_grund[grund] = je_grund.get(grund, 0) + anzahl
        # `live_pending` zählt gescheiterte neue Post mit; offen ist nur, was noch nicht versucht wurde.
        neu_gescheitert = max(0, sum(grunde.values()) - int(o.get('failed') or 0))
        offen += int(o.get('pending') or 0) + max(0, int(o.get('live_pending') or 0) - neu_gescheitert)
        if grunde:
            technik.append(f"{o.get('folder')}: " + ', '.join(f'{n} × {g}' for g, n in sorted(grunde.items()))
                           + (f" ({o['failed_technik']})" if o.get('failed_technik') else ''))
    return je_grund, offen, '; '.join(technik) or None


def _nicht_ins_gedaechtnis(anzahl: int) -> str:
    return 'Eine Mail kam nicht ins Gedächtnis.' if anzahl == 1 else f'{zahl(anzahl)} Mails kamen nicht ins Gedächtnis.'


def konto_stand(name: str, *, intake: dict[str, Any] | None = None, abruf: dict[str, Any] | None = None,
                blick: dict[str, Any] | None = None, jetzt: datetime | None = None,
                verbunden: bool = True) -> dict[str, Any]:
    """Die eine Aussage über ein Postfach. `intake` ist der Stand des Einlesens (`Intake.status`), `abruf` der des
    regelmäßigen Abrufs (`mail_sync_status`), `blick` der letzte erfolgreiche Blick hinein (`merke_gelesen`).
    `verbunden=False`: Das Postfach ist eingetragen, aber Kingfisher kann es nicht öffnen (meist fehlt das Passwort)."""
    postfach = f'Postfach {name}'
    if not verbunden:
        return _ergebnis('fehler', f'{postfach} {GRUND["credentials_missing"]}.')
    blick_zeit = _zeit((blick or {}).get('zeit'))
    if intake and intake.get('started'):
        if intake.get('error'):
            return _ergebnis('fehler', f'{postfach} {GRUND.get(str(intake["error"]), SONST)}.')
        if intake.get('paused'):
            return _ergebnis('pausiert', f'Das Einlesen von {postfach} ist angehalten. Du startest es unter '
                                         'Einstellungen → Für Techniker → Zeitplan und Hintergrund wieder.')
        ordner = intake.get('folders') or []
        # Ausgefilterte (Newsletter, Spam) sind gelesen und bewusst beiseitegelegt; ohne sie stünde ein Postfach mit
        # einem Newsletter für immer auf „wird gelesen: 4 von 5“.
        gefunden = sum(int(o.get('captured') or 0) + int(o.get('duplicates') or 0) + int(o.get('filtered') or 0)
                       for o in ordner)
        je_grund, offen, technik = _gescheitert(ordner)
        gescheitert = sum(je_grund.values())
        if gescheitert and not offen and all(o.get('inventory_complete') for o in ordner):
            from .mail_intake_grund import SATZ, haeufigster
            grund = SATZ.get(haeufigster(je_grund) or '', SATZ['unbekannt'])
            return _ergebnis('gescheitert', f'{postfach}: {_nicht_ins_gedaechtnis(gescheitert)} {grund} '
                                            'Kingfisher versucht es später von selbst noch einmal.',
                             gelesen_n=gefunden, technik=technik)
        fertig_gezaehlt = bool(ordner) and all(o.get('inventory_complete') and o.get('total') is not None for o in ordner)
        gesamt = sum(int(o.get('total') or 0) for o in ordner) if fertig_gezaehlt else None
        zuletzt = max(filter(None, (_zeit(intake.get('aktualisiert')), blick_zeit)), default=None)
        wann = zeit_text(zuletzt, jetzt)
        if gesamt is None:
            if gefunden == 0 and blick is not None and int(blick.get('anzahl') or 0) == 0:
                # Der Posteingang ist nachweislich leer; die übrigen Ordner sieht Kingfisher noch durch.
                return _ergebnis('leer', f'{postfach} ist verbunden, und im Posteingang liegt nichts'
                                         + (f' (nachgesehen {wann})' if wann else '') + '.', gelesen_n=0, zuletzt=zuletzt)
            return _ergebnis('liest', f'{postfach} wird durchgesehen: bisher '
                                      + ('keine Mails' if gefunden == 0 else _mails(gefunden)) + ' gefunden.',
                             gelesen_n=gefunden)
        if gefunden < gesamt:
            return _ergebnis('liest', f'{postfach} wird gelesen: {zahl(gefunden)} von {_mails(gesamt)}.'
                                      + (f' {_nicht_ins_gedaechtnis(gescheitert)}' if gescheitert else ''),
                             gelesen_n=gefunden, gesamt=gesamt, technik=technik)
        if gesamt == 0:
            return _ergebnis('leer', f'{postfach} ist verbunden und leer' + (f', abgerufen {wann}' if wann else '') + '.',
                             gelesen_n=0, gesamt=0, zuletzt=zuletzt)
        return _ergebnis('aktuell', f'{postfach} ist gelesen: {_mails(gesamt)}'
                                    + (f', zuletzt abgerufen {wann}' if wann else '') + '.',
                         gelesen_n=gesamt, gesamt=gesamt, zuletzt=zuletzt)
    if abruf and (abruf.get('last_success') or abruf.get('last_failure')):
        erfolg = _zeit(abruf.get('last_success'))
        if abruf.get('last_failure'):
            return _ergebnis('fehler', f'{postfach} {GRUND.get(str(abruf["last_failure"]), SONST)}.', zuletzt=erfolg)
        zuletzt = max(filter(None, (erfolg, blick_zeit)), default=None)
        wann = zeit_text(zuletzt, jetzt)
        bericht = abruf.get('last_report') or {}
        neu = int(bericht.get('recorded') or 0)
        leer = blick is not None and int(blick.get('anzahl') or 0) == 0 and neu == 0
        if leer:
            return _ergebnis('leer', f'{postfach} ist verbunden und leer, abgerufen {wann}.', gelesen_n=0, zuletzt=zuletzt)
        return _ergebnis('aktuell', f'{postfach} ist abgerufen {wann}'
                                    + (f': {_mails(neu)} neu.' if neu else ', nichts Neues.'), zuletzt=zuletzt)
    if blick is not None:
        anzahl = int(blick.get('anzahl') or 0)
        wann = zeit_text(blick_zeit, jetzt)
        if anzahl == 0:
            return _ergebnis('leer', f'{postfach} ist verbunden und leer, abgerufen {wann}.', gelesen_n=0, zuletzt=blick_zeit)
        return _ergebnis('aktuell', f'{postfach} ist abgerufen {wann}: {_mails(anzahl)} im Posteingang.',
                         zuletzt=blick_zeit)
    return _ergebnis('nicht_abgerufen', f'{postfach} ist verbunden, aber noch nicht abgerufen.')


def _verbunden(app: Any, konto: str) -> bool:
    """Kann Kingfisher dieses Postfach öffnen? Ohne Passwort im Schlüsselbund gibt es keinen Leser dafür."""
    mail = getattr(app.state, 'mail', None)
    if mail is None:
        return False
    reader_for = getattr(mail, 'reader_for', None)
    if reader_for is None:
        return True
    try:
        reader_for(konto)
    except Exception:  # noqa: BLE001 - jedes Scheitern heißt: dieses Postfach ist gerade nicht zu öffnen
        return False
    return True


def stand(app: Any, *, intake_status: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Der Stand aller eingerichteten Postfächer, je mit `account_id`, `label` und der einen Aussage."""
    from .mail_intake import Intake
    settings = app.state.settings
    ergebnis = []
    store = None
    for eintrag in settings.mail_accounts:
        if not eintrag.configured:
            continue
        intake = (intake_status or {}).get(eintrag.id)
        if intake is None:
            store = store or Intake(app.state.episodes)
            intake = store.status(eintrag.id)
            if intake.get('started') and (not settings.schedule.enabled
                                          or eintrag.id not in settings.schedule.mail_accounts):
                intake = {**intake, 'paused': True}
        ergebnis.append({'account_id': eintrag.id, 'label': eintrag.label,
                         **konto_stand(eintrag.label, intake=intake,
                                       abruf=(getattr(settings, 'mail_sync_status', None) or {}).get(eintrag.id),
                                       blick=gelesen(app, eintrag.id), verbunden=_verbunden(app, eintrag.id))})
    return ergebnis


__all__ = ['GRUND', 'gelesen', 'konto_stand', 'merke_gelesen', 'stand', 'zeit_text']
