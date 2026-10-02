"""Aufnahme: die Welt über die Produktpfade einspielen.

Jede Quellenart nimmt genau den Weg, den das Produkt nimmt:

* **Mail** über `mail_intake.Intake.step` mit dem echten `connectors/mail.py::MailConnector`
  als Leser. Ersetzt ist nur die Verbindung (`postfach.py`); Kopfzeilen,
  Textwahl, Fortschrittsspeicher, Wiederholung und `mail_ingestion.remember`
  sind Produktcode. Ordner INBOX und Sent, wie beim Nutzer.
* **Notizen und Transkripte** über `scheduler.ingest_job` (derselbe Auftrag wie
  der Zeitplan) mit dem Adapter `markdown`: Dateien mit Kopfzeilen (`title`,
  `date`, `participants`) in einem freigegebenen Ordner.
* **Termine** über den Mac-Kalender-Adapter (`mac_calendar.MacCalendar`): freigeben,
  Kalender wählen, Momentaufnahme des Arbeiters einspielen (Live-Anzeige, nur das
  laufende Jahr) und dann die Gedächtnisabschnitte des Arbeiters an die Route
  `/api/v1/mac-calendar/memory` senden. Das Produkt legt daraus Episoden der Art
  `event` an (`calendar_memory.py`); die UID des Termins ist die Welt-ID.

Danach ordnet `einordnung.py` die Quellen ein, sonst findet die Suche nichts.
Das Ergebnis hält die Zuordnung Welt-ID <-> Episode-ID fest.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Callable, Sequence

from .daten import Mail, Notiz, Quelle, Termin, Transkript
from .einordnung import KonstanteEinordnung, einordnen, stand
from .ergebnisse import AufnahmeErgebnis
from .postfach import Postfach, postfach_installieren, quelle_aus_message_id

KONTO = 'messlatte'
KALENDER = 'messlatte'
RAUSCHEN = 'rauschen-'
_VAULT = re.compile(r'vault:(?:[^/]+/)*([^/]+)\.md$')


def ist_rauschen(quelle_id: str) -> bool:
    return quelle_id.startswith(RAUSCHEN)


def _kopf(wert: str) -> str:
    """Kopfzeilenwert einzeilig machen; das Produkt liest nur flache `schlüssel: wert`-Zeilen."""
    return ' '.join(str(wert).split())


def _datei(quelle: Notiz | Transkript) -> str:
    zeilen = ['---', f'title: {_kopf(quelle.titel)}', f'date: {quelle.zeit.isoformat()}']
    if isinstance(quelle, Transkript) and quelle.teilnehmer:
        zeilen.append('participants: ' + ', '.join(_kopf(n) for n in quelle.teilnehmer))
    zeilen += ['---', quelle.text]
    return '\n'.join(zeilen) + '\n'


def _dateien_schreiben(wurzel: Path, quellen: Sequence[Quelle]) -> dict[str, Path]:
    ordner = {Notiz: wurzel / 'notizen', Transkript: wurzel / 'transkripte'}
    ergebnis = {}
    for quelle in quellen:
        ziel = ordner.get(type(quelle))
        if ziel is None:
            continue
        ziel.mkdir(parents=True, exist_ok=True)
        pfad = ziel / f'{quelle.id}.md'
        pfad.write_text(_datei(quelle), encoding='utf-8')
        ergebnis[quelle.id] = pfad
    return ergebnis


def _welt_id_aus_herkunft(quelle: str) -> str | None:
    """Welt-ID aus der Herkunftsangabe einer Episode (Mail, Datei oder Termin), sonst None."""
    from icarus_memory.calendar_memory import uid_aus_herkunft

    welt_id = quelle_aus_message_id(quelle)
    if welt_id is None:
        treffer = _VAULT.search(quelle)
        welt_id = treffer.group(1) if treffer else uid_aus_herkunft(quelle)
    return welt_id


class _Einordner:
    """Wählt je Episode die Einordnung: Rauschen konstant, der Rest wie gewünscht."""

    def __init__(self, instanz, modell=None):
        self.instanz = instanz
        self.konstant = KonstanteEinordnung()
        self.modell = modell

    def _welt_id(self, episode_id: str) -> str | None:
        return _welt_id_aus_herkunft(self.instanz.episodes.get(episode_id).provenance.source_ref or '')

    def ids(self, episode_ids: list[str]) -> None:
        if not episode_ids:
            return
        if self.modell is None:
            einordnen(self.instanz, self.konstant, episode_ids)
            return
        rauschen, echt = [], []
        for episode_id in episode_ids:
            (rauschen if ist_rauschen(self._welt_id(episode_id) or '') else echt).append(episode_id)
        einordnen(self.instanz, self.konstant, rauschen)
        einordnen(self.instanz, self.modell, echt)


def _mails(instanz, mails: Sequence[Mail], einordner: _Einordner, laufzeit: dict,
           postfach_haken: Callable[[Postfach], None] | None = None) -> None:
    from icarus_memory.connectors.mail import MailConfig, MailConnector
    from icarus_memory.mail_intake import Intake

    postfach = Postfach()
    for mail in sorted(mails, key=lambda m: (m.zeit, m.id)):
        postfach.ablegen_mail(mail)
    if postfach_haken is not None:
        postfach_haken(postfach)
    ordner = [name for name in ('INBOX', 'Sent') if name in postfach.ordner]
    if not ordner:
        return
    sperre = instanz.app.state.conversation_lock
    intake = Intake(instanz.episodes)
    intake.start(KONTO, ordner)
    with postfach_installieren(postfach):
        # Das Konto trägt die Adresse des Nutzers, wie im Betrieb; daran erkennt die Aufnahme „ich“.
        konto = (instanz.eigene[0] if instanz.eigene else 'lea@messlatte.example')
        leser = MailConnector(MailConfig(imap_host='imap.messlatte.example', username=konto,
                                         password='unbenutzt'))
        grenze = len(mails) // 4 + 40  # Schritte; jeder holt bis zu 50 Mails
        wiederholt = False
        for _ in range(grenze):
            episoden = intake.step(KONTO, leser, batch=50, permission_lock=sperre, claims=instanz.claims)
            einordner.ids(list(episoden))
            if episoden:
                continue  # Es kam etwas an; der teure Statusabruf lohnt erst, wenn ein Schritt leer bleibt.
            status = intake.status(KONTO)
            offen = any(not f['inventory_complete'] or f['pending'] or f['live_pending'] for f in status['folders'])
            if offen:
                continue
            fehlgeschlagen = sum(f['failed'] for f in status['folders'])
            if fehlgeschlagen and not wiederholt:
                # Der Knopf „Erneut versuchen“ des Produkts: einmal, dann zählt der Rest als fehlgeschlagen.
                intake.retry(KONTO)
                wiederholt = True
                continue
            break
    status = intake.status(KONTO)
    laufzeit['mail'] = Counter(
        aufgenommen=sum(f['captured'] for f in status['folders']),
        dupliziert=sum(f['duplicates'] for f in status['folders']),
        fehlgeschlagen=sum(f['failed'] for f in status['folders']))
    laufzeit['mail_fehler'] = status.get('error')


def _dateien(instanz, wurzel: Path, quellen: Sequence[Quelle], einordner: _Einordner, laufzeit: dict) -> None:
    from icarus_memory.scheduler import ingest_job
    from icarus_memory.source_versions import exclude_missing_documents, track_document

    geschrieben = _dateien_schreiben(wurzel, quellen)
    if not geschrieben:
        return
    ordner = {str(wurzel / name): 'markdown' for name in ('notizen', 'transkripte') if (wurzel / name).is_dir()}
    vorher = {e.id for e in instanz.episodes.each_episode()}
    ergebnisse = ingest_job(
        instanz.episodes, [wurzel], ordner,
        on_source=lambda root, ref, episode: track_document(instanz.episodes, instanz.claims, root, ref, episode),
        on_complete=lambda root, adapter, beobachtet: exclude_missing_documents(
            instanz.episodes, instanz.claims, root, adapter, beobachtet))()
    neu = [e.id for e in instanz.episodes.each_episode() if e.id not in vorher]
    einordner.ids(neu)
    laufzeit['dateien'] = Counter(aufgenommen=len(neu), fehlgeschlagen=sum(not r.ok for r in ergebnisse))
    laufzeit['dateien_meldungen'] = [r.detail for r in ergebnisse if not r.ok]


def _im_gedaechtnisfenster(termin: Termin, stichtag: datetime) -> bool:
    from icarus_memory.calendar_memory import fenster
    von, bis = fenster(stichtag)
    return termin.ende > von and termin.beginn < bis


def _adresse(a) -> str:
    return f'{a.name} <{a.adresse}>' if a.name else a.adresse


def _termine(instanz, termine: Sequence[Termin], stichtag: datetime, einordner: _Einordner, laufzeit: dict) -> None:
    from icarus_memory.calendar_memory import abschnitte, fenster
    from icarus_memory.mac_calendar import WorkerUpdate

    if not termine:
        return
    # Live-Anzeige: der Mac-Adapter gleicht nur das laufende Jahr ab (wie im Betrieb).
    von = stichtag.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    bis = stichtag.replace(month=12, day=31, hour=23, minute=59, second=0, microsecond=0)
    im_fenster = [t for t in termine if t.ende > von and t.beginn < bis]
    kalender = [{'id': KALENDER, 'name': 'Messlatte', 'source': 'Messlatte'}]

    def ereignis(t: Termin, live: bool) -> dict:
        eintrag = {'uid': t.id, 'summary': t.titel, 'start': t.beginn, 'end': t.ende, 'all_day': False,
                   'location': t.ort, 'source_id': KALENDER, 'source_label': 'Messlatte',
                   'attendees': [a.adresse if live else _adresse(a) for a in t.teilnehmer]}
        if not live:
            eintrag.update(start=t.beginn.isoformat(), end=t.ende.isoformat(), notes=t.notiz)
        return eintrag

    mac = instanz.app.state.mac_calendar
    freigegeben = mac.enable()
    mac.update(WorkerUpdate(generation=freigegeben['generation'], status='granted', calendars=kalender))
    gewaehlt = mac.select([KALENDER])
    mac.update(WorkerUpdate(generation=gewaehlt['generation'], status='granted', calendars=kalender,
                            events=[ereignis(t, True) for t in im_fenster], range_from=von, range_to=bis))
    instanz.kalender_neu_lesen()

    # Gedächtnis: wie der Mac-Arbeiter, abschnittsweise über die Produktroute.
    gedaechtnis_von, gedaechtnis_bis = fenster(stichtag)
    vorher = {e.id for e in instanz.episodes.each_episode()}
    im_gedaechtnis = [t for t in termine if t.ende > gedaechtnis_von and t.beginn < gedaechtnis_bis]
    antworten = []
    for a, b in abschnitte(gedaechtnis_von, gedaechtnis_bis):
        abschnitt = [ereignis(t, False) for t in im_gedaechtnis if t.ende > a and t.beginn < b]
        antworten.append(instanz.anfrage('POST', '/api/v1/mac-calendar/memory', {
            'generation': gewaehlt['generation'], 'range_from': a.isoformat(), 'range_to': b.isoformat(),
            'events': abschnitt}))
    einordner.ids([e.id for e in instanz.episodes.each_episode() if e.id not in vorher])
    laufzeit['termine'] = Counter(im_kalender=len(im_fenster), ausserhalb=len(termine) - len(im_gedaechtnis),
                                  neu=sum(x.get('neu', 0) for x in antworten))


def zuordnung(instanz) -> dict[str, str]:
    """Welt-ID -> Episoden-ID, aus der Herkunftsangabe jeder Episode im Bestand."""
    ergebnis: dict[str, str] = {}
    for episode in instanz.episodes.each_episode():
        welt_id = _welt_id_aus_herkunft(episode.provenance.source_ref or '')
        if welt_id is not None:
            ergebnis[welt_id] = episode.id
    return ergebnis


def aufnehmen(instanz, quellen: Sequence[Quelle], stichtag: datetime, *, modell=None,
              arbeitsordner: Path | None = None,
              postfach_haken: Callable[[Postfach], None] | None = None) -> AufnahmeErgebnis:
    """Spielt `quellen` ein und hält Zähler, Dauer und Zuordnung fest.

    `modell`: ein lokaler Anbieter, der die Nicht-Rauschen-Quellen einordnet (wie im
    Betrieb); ohne ihn ordnet `KonstanteEinordnung` alles ein. `postfach_haken`
    bekommt das Postfach vor dem Abruf (für Tests, die Serverfehler einspielen).
    """
    start = time.perf_counter()
    quellen = list(quellen)
    wurzel = Path(arbeitsordner) if arbeitsordner else instanz.verzeichnis / 'quellen'
    wurzel.mkdir(parents=True, exist_ok=True)
    einordner = _Einordner(instanz, modell)
    laufzeit: dict = {}
    _mails(instanz, [q for q in quellen if isinstance(q, Mail)], einordner, laufzeit, postfach_haken)
    _dateien(instanz, wurzel, [q for q in quellen if isinstance(q, (Notiz, Transkript))], einordner, laufzeit)
    _termine(instanz, [q for q in quellen if isinstance(q, Termin)], stichtag, einordner, laufzeit)

    zugeordnet = zuordnung(instanz)
    anhaenge = sum(1 for welt_id in zugeordnet if '#anhang-' in welt_id)
    je_art: dict = {}
    nicht_angekommen: dict = {}
    for art in ('mail', 'transkript', 'notiz', 'termin'):
        der_art = [q for q in quellen if q.art == art]
        if not der_art:
            continue
        angekommen = [q for q in der_art if q.id in zugeordnet]
        je_art[art] = {'quellen': len(der_art), 'aufgenommen': len(angekommen),
                       'fehlend': len(der_art) - len(angekommen)}
        if art == 'termin':
            zaehler = laufzeit.get('termine', Counter())
            je_art[art].update(im_kalender=zaehler['im_kalender'], ausserhalb_fenster=zaehler['ausserhalb'])
        for q in der_art:
            if q.id not in zugeordnet:
                nicht_angekommen[q.id] = ('außerhalb des Gedächtnisfensters' if art == 'termin' and not _im_gedaechtnisfenster(q, stichtag)
                                          else 'über den Produktpfad nicht aufgenommen')
    mail = laufzeit.get('mail', Counter())
    dateien = laufzeit.get('dateien', Counter())
    fortschritt = stand(instanz)
    termine = laufzeit.get('termine', Counter())
    return AufnahmeErgebnis(
        aufgenommen=len(zugeordnet) - anhaenge, dupliziert=mail['dupliziert'],
        fehlgeschlagen=len(nicht_angekommen),  # was die Welt hat, das Produkt aber nicht: die Wahrheit über Ausfälle
        je_art=je_art, episoden=zugeordnet, nicht_angekommen=nicht_angekommen,
        meldungen=tuple(m for m in (laufzeit.get('mail_fehler'), *laufzeit.get('dateien_meldungen', ())) if m),
        termine_im_kalender=termine['im_kalender'], termine_ausserhalb_fenster=termine['ausserhalb'],
        einordnung=(f"{fortschritt['done']} von {fortschritt['total']} eingeordnet"
                    f" ({'Modell ' + getattr(modell, 'model', '?') if modell else 'konstante Einordnung'})"
                    + (f", {fortschritt['skipped']} zurückgestellt" if fortschritt['skipped'] else '')
                    + (f", {fortschritt['retry']} zur Wiederholung" if fortschritt['retry'] else '')),
        dauer_s=round(time.perf_counter() - start, 3), quellen_gesamt=len(quellen),
        rauschen=sum(ist_rauschen(q.id) for q in quellen))
