"""„Was brauche ich morgen?“: Termine, Fristen und Aufgaben eines kommenden Zeitraums, ohne Modell.

Ein Stabschef hat das parat. Kingfisher auch, denn alles steht schon da: die Termine im verbundenen
Kalender (`app.state.calendar`), die Fristen und Zusagen in den Akten (`fristlage.py`), die Aufgaben
mit Fälligkeit (`tasks.py`) und, wo die Heute-Seite sie schon berechnet hat, die Wegezeit
(`wegezeit.py`). Dieses Modul stellt es für einen Zeitraum zusammen, den die Frage nennt
(`time_scope.kommender_zeitraum`: morgen, nächste Woche, am Freitag, am 24.10.).

Grenzen, an denen nichts weich ist:

* **Nur feste Frageformen** („Was steht … an?“, „Was brauche ich …?“, „Was habe ich …?“, „Was ist … los?“,
  „Welche Termine …?“, „Was muss ich … erledigen?“, „Bin ich … frei?“) mit einem kommenden Zeitraum. Nennt
  die Frage eine Sache oder fragt sie Vergangenes, geht sie den üblichen Weg.
* **Nur, was Kingfisher kennt.** Ist nichts da, sagt die Antwort das („Für morgen steht nichts im Kalender
  und keine Frist an.“). Sie behauptet nie, dass jemand frei ist: Ein Kalender kann unvollständig sein.
* **Jede Zeile trägt ihre Quelle** (Termin im Gedächtnis, Akte, Aufgabe). Nichts außerhalb des Zeitraums.
* **Nichts geht hinaus.** Die Wegezeit wird nur aus dem Zwischenspeicher gelesen (`nur_lesen`); für die
  Antwort wird kein Kartendienst angefragt.
* **Der gleiche Wochentag wie heute ist mehrdeutig:** Die Antwort fragt in einem Satz nach, statt zu raten.
* **Nie weiter als `calendar_window.MAX_CALENDAR_WINDOW`** voraus; kürzt sie, sagt sie es.

Wie die offenen Punkte ist die Antwort eine Ansicht: Im Gesprächsverlauf steht nur die Frage und der Tag, an
dem sie gestellt wurde; beim Öffnen wird sie neu zusammengestellt, aber nur am selben Tag. Danach heißt es
ehrlich „Diese Antwort galt für den …“, denn „morgen“ meint dann einen anderen Tag.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from . import fristlage, identitaet, wegezeit
from .calendar_window import MAX_CALENDAR_WINDOW, display_events, display_warning
from .datumstext import iso_versuchen
from .model import now as _jetzt_utc, user_timezone
from .time_scope import kommender_zeitraum

logger = logging.getLogger(__name__)

_KURZ = ('Mo', 'Di', 'Mi', 'Do', 'Fr', 'Sa', 'So')
#: Höchstens so viele Termine werden aus den Akten vorbereitet (Zeitbudget); die übrigen stehen ohne Hinweis.
MAX_VORBEREITET = 12
#: Höchstens so viele Zeilen je Abschnitt.
MAX_ZEILEN = 20

_FORMEN = re.compile(r'''^(?:und\s+)?(?:
    was\s+steht(?:\s+(?:bei\s+(?:mir|uns)|im\s+kalender|auf\s+dem\s+plan))?\s+an
  | was\s+steht(?:\s+bei\s+(?:mir|uns))?\s+(?:im\s+kalender|auf\s+dem\s+plan)
  | was\s+liegt\s+an
  | was\s+brauch(?:e)?\s+(?:ich|wir)
  | was\s+(?:habe|hab|haben)\s+(?:ich|wir)(?:\s+vor)?
  | was\s+ist(?:\s+bei\s+(?:mir|uns))?\s+los
  | welche\s+termine(?:\s+(?:habe|hab|haben)\s+(?:ich|wir)|\s+stehen\s+an|\s+gibt\s+es|\s+sind(?:\s+dran)?)?
  | was\s+(?:muss|soll)\s+ich\s+(?:erledigen|vorbereiten|tun|machen|schaffen)
  | (?:bin|sind)\s+(?:ich|wir)\s+frei
  | (?:habe|hab|haben)\s+(?:ich|wir)\s+(?:frei|zeit)
  | was\s+kommt\s+auf\s+(?:mich|uns)\s+zu
)$''', re.I | re.X)
_FUELLER = re.compile(r'\b(?:eigentlich|denn|so|alles|noch|überhaupt|ueberhaupt|mal|gerade|genau|bitte|dann|da|'
                      r'jetzt|für|fuer|wohl|überhaupt)\b', re.I)


@dataclass
class Antwort:
    text: str
    links: list[dict[str, Any]] = field(default_factory=list)
    zeitraum: dict[str, Any] | None = None
    rueckfrage: bool = False


def _frageform(frage: str, beschriftung: dict[str, Any]) -> bool:
    rest = frage[:beschriftung['start']] + ' ' + frage[beschriftung['ende']:]
    rest = _FUELLER.sub(' ', rest)
    rest = re.sub(r'[?!.,;:]', ' ', rest)
    return bool(_FORMEN.fullmatch(' '.join(rest.split()).casefold()))


def ist_frage(frage: Any, now: datetime | None = None) -> bool:
    """Eine feste Frageform nach dem, was ansteht, mit einem kommenden Zeitraum; kein Modell."""
    if not isinstance(frage, str) or not frage.strip() or len(frage) > 300:
        return False
    gefunden = kommender_zeitraum(frage, now)
    return gefunden is not None and _frageform(frage, gefunden[2])


def gilt_noch(gefragt_am: Any, jetzt: datetime | None = None) -> bool:
    """Gilt eine gespeicherte Antwort noch? Nur am Tag der Frage (Zeitzone des Nutzers): „morgen“ wandert sonst."""
    zone = user_timezone() or timezone.utc
    gefragt = iso_versuchen(gefragt_am)
    if gefragt is None or gefragt.tzinfo is None:
        return False
    jetzt = (jetzt or _jetzt_utc()).astimezone(zone)
    return gefragt.astimezone(zone).date() == jetzt.date()


# -- Bausteine ----------------------------------------------------------------------------------------


def _uhr(zeit: datetime) -> str:
    return f'{zeit:%H:%M}'


def _tag(tag: date) -> str:
    return f'{_KURZ[tag.weekday()]} {tag.day}.{tag.month}.'


def _wann(event: Any, zone: Any) -> str:
    beginn = event.start.astimezone(zone)
    if event.all_day:
        return f'{_tag(beginn.date())}, ganztägig'
    ende = event.end.astimezone(zone) if event.end else None
    if ende and ende > beginn and ende.date() == beginn.date():
        return f'{_tag(beginn.date())}, {_uhr(beginn)}–{_uhr(ende)} Uhr'
    return f'{_tag(beginn.date())}, {_uhr(beginn)} Uhr'


def _namen(app, teilnehmer: list[str], eigene: list[str]) -> str:
    """Die anderen Teilnehmer mit Namen (aus dem Bestand, wenn der Kalender nur Adressen kennt); nie die eigenen."""
    from .vorbereitung import teilnehmer as teilnehmer_aus
    try:
        index = app.state.episodes.participants_for_addresses(teilnehmer)
    except Exception:  # noqa: BLE001 - ohne Index bleiben die Angaben des Kalenders
        index = {}
    namen = []
    for t in teilnehmer_aus(teilnehmer, index=index, eigene=eigene):
        name = ' '.join(str(t.get('name') or t.get('adresse') or '').split())
        if name and name not in namen:
            namen.append(name)
    if not namen:
        return ''
    if len(namen) > 5:
        return ', '.join(namen[:5]) + f' und {len(namen) - 5} weitere'
    return namen[0] if len(namen) == 1 else ', '.join(namen[:-1]) + ' und ' + namen[-1]


def _vorbereitung(app, eintrag: dict[str, Any], akten: Any, eigene: list[str], jetzt: datetime) -> tuple[str | None, str]:
    """(Episode des Termins im Gedächtnis, Hinweis „vorbereitet …“) aus den Akten; nichts geht hinaus."""
    from . import terminvorbereitung
    episode_id, notiz = terminvorbereitung.termin_im_gedaechtnis(
        app.state.episodes, str(eintrag.get('uid') or ''), str(eintrag.get('source_id') or ''))
    termin = terminvorbereitung.Termin.aus_dict(eintrag, notiz=notiz, episode_id=episode_id)
    if termin is None or not termin.teilnehmer or akten is None:
        return episode_id, ''
    try:
        v = terminvorbereitung.vorbereiten(termin, akten=akten, episodes=app.state.episodes, eigene=eigene,
                                           jetzt=jetzt, workspace=getattr(app.state, 'workspace', None))
    except Exception:  # noqa: BLE001 - der Termin bleibt in der Antwort, nur ohne Vorbereitung
        logger.exception('Termin konnte für die Antwort nicht vorbereitet werden')
        return episode_id, ''
    if not v.bereit:
        return episode_id, ''
    bekannt = sum(1 for p in v.personen if p.bekannt)
    return episode_id, f'vorbereitet: {"ein Teilnehmer" if bekannt == 1 else f"{bekannt} Teilnehmer"} in den Akten'


def _wegezeit(app, eintraege: list[dict[str, Any]], eintrag: dict[str, Any], beginn: datetime) -> str:
    """Die Wegezeit aus dem Zwischenspeicher der Heute-Seite, nur gelesen; sonst ein ehrliches Wort."""
    if eintrag.get('all_day') or not (eintrag.get('location') or '').strip():
        return ''
    from .wegezeit_routes import dienst
    try:
        fahrdienst = dienst(app)
        if not fahrdienst.stand().get('aktiv'):
            return ''
        auskunft = fahrdienst.auskunft(eintrag.get('location'), beginn=beginn,
                                       vorheriger=wegezeit.vorheriger_termin(eintraege, eintrag), nur_lesen=True)
    except Exception:  # noqa: BLE001 - der Weg ist Beiwerk
        logger.exception('Wegezeit konnte nicht gelesen werden')
        return ''
    if auskunft.status == wegezeit.BERECHNET and auskunft.losfahren is not None:
        satz = (f'Fahrzeit etwa {auskunft.minuten} Minuten {wegezeit.MITTEL_TEXT.get(auskunft.verkehrsmittel, "")}'
                f'; Losfahren um {auskunft.losfahren.hour}:{auskunft.losfahren.minute:02d} Uhr')
        return satz + (f'. {auskunft.knapp}' if auskunft.knapp else '')
    if auskunft.status == wegezeit.NICHT_BERECHNET:
        return 'Fahrzeit noch nicht berechnet (die Heute-Seite rechnet sie)'
    return ''


def _termine(app, von: datetime, bis: datetime, zone: Any, eigene: list[str], akten: Any,
             jetzt: datetime, einzeltag: bool) -> tuple[list[tuple[str, str | None]], list[str]]:
    """Zeilen (Text, Episode) der Termine im Zeitraum und Hinweise; ein Fehler kostet nur die Termine."""
    kalender = getattr(app.state, 'calendar', None)
    if kalender is None:
        return [], ['Es ist kein Kalender verbunden.']
    tage = (bis.date() - von.date()).days + 1
    try:
        events = list(kalender.events(days=tage, at=von.astimezone(timezone.utc)))
    except Exception as exc:  # noqa: BLE001 - kein Fehlertext, er könnte Adressen tragen
        logger.warning('Kalender für die Antwort nicht lesbar: %s', type(exc).__name__)
        return [], ['Der Kalender ist gerade nicht erreichbar.']
    sichtbar, unbekannt = display_events(events, von, bis, zone=zone)
    sichtbar.sort(key=lambda e: (e.start.astimezone(timezone.utc), e.uid))
    hinweise = [display_warning(unbekannt)] if unbekannt else []
    eintraege = []
    for e in sichtbar:
        eintrag = e.to_dict()
        eintrag['start'] = e.start.astimezone(zone).isoformat()
        eintrag['end'] = (e.end or e.start).astimezone(zone).isoformat()
        eintraege.append(eintrag)
    zeilen: list[tuple[str, str | None]] = []
    for nummer, (e, eintrag) in enumerate(zip(sichtbar, eintraege)):
        if nummer >= MAX_ZEILEN:
            hinweise.append(f'Nur die ersten {MAX_ZEILEN} von {len(sichtbar)} Terminen stehen hier.')
            break
        teile = [f'{_wann(e, zone)}: „{" ".join(str(e.summary or "Ohne Titel").split())}“']
        ort = ' '.join(str(e.location or '').split())
        if ort:
            teile[0] += f', {ort}'
        namen = _namen(app, list(e.attendees or ()), eigene)
        if namen:
            teile.append(f'mit {namen}')
        episode_id, hinweis = (_vorbereitung(app, eintrag, akten, eigene, jetzt) if nummer < MAX_VORBEREITET
                               else (None, ''))
        if hinweis:
            teile.append(hinweis)
        if einzeltag:
            weg = _wegezeit(app, eintraege, eintrag, e.start.astimezone(zone))
            if weg:
                teile.append(weg)
        text = '; '.join(teile)
        if episode_id is None:
            text += f' (Kalender „{" ".join(str(e.source_label or "Kalender").split())}“)'
        zeilen.append((text, episode_id))
    return zeilen, hinweise


def _fristen(app, von: datetime, bis: datetime, jetzt: datetime, eigene: list[str],
             akten: Any, bezuege: Any) -> list[tuple[str, str | None]]:
    heute = jetzt.date()
    letzter = (bis - timedelta(microseconds=1)).date()
    gesammelt = fristlage.sammeln(akten, bezuege, jetzt=jetzt, eigene=eigene, tage_voraus=max((letzter - heute).days, 0))
    zeilen = []
    for f in gesammelt:
        if f.status != 'kommend' or not von.date() <= f.datum <= letzter:
            continue
        quelle = f'{f.quelle_art} „{f.titel}“' if f.quelle_art else f'„{f.titel}“'
        zeilen.append((f'{fristlage.beschreibung(f).rstrip(".")}: „{f.text}“ ({quelle})', f.episode_id))
    return zeilen[:MAX_ZEILEN]


def _aufgaben(app, von: datetime, bis: datetime, zone: Any, jetzt: datetime) -> tuple[list[str], list[str]]:
    tasks = getattr(app.state, 'tasks', None)
    if tasks is None:
        return [], []
    eigene, wartend = [], []
    for task in tasks.open_tasks(limit=None):
        faellig = task.due if task.due is None or task.due.tzinfo else task.due.replace(tzinfo=timezone.utc)
        if faellig is None or not von <= faellig < bis:
            continue
        wann = _tag(faellig.astimezone(zone).date())
        titel = ' '.join(str(task.title).split())
        if task.wartet_auf:
            seit = task.wartet_tage(jetzt)
            dauer = f' seit {seit} Tagen' if seit else ''
            wartend.append(f'„{titel}“ liegt bei {task.wartet_auf}{dauer}, fällig {wann} (Aufgabe)')
        else:
            eigene.append(f'„{titel}“, fällig {wann} (Aufgabe)')
    return eigene[:MAX_ZEILEN], wartend[:MAX_ZEILEN]


def _eigene(app) -> list[str]:
    """Die eigenen Adressen: die des Agenten (Messlatte, Verdrahtung), sonst die der Einstellungen."""
    sammler = getattr(getattr(app.state, 'agent', None), '_eigene', None)
    if callable(sammler):
        try:
            return [str(a) for a in sammler() or ()]
        except Exception:  # noqa: BLE001
            pass
    return list(identitaet.eigene_adressen(getattr(app.state, 'settings', None)))


# -- Die Antwort --------------------------------------------------------------------------------------


def antwort(app, frage: str, now: datetime | None = None) -> Antwort | None:
    """Die Antwort auf eine Frage nach dem, was ansteht; None, wenn die Frage keine solche ist."""
    if not ist_frage(frage, now):
        return None
    zone = user_timezone() or timezone.utc
    jetzt = (now or _jetzt_utc()).astimezone(zone)
    von, bis, beschriftung = kommender_zeitraum(frage, jetzt)
    if beschriftung.get('mehrdeutig'):
        return Antwort(beschriftung['rueckfrage'], [], None, rueckfrage=True)
    text = beschriftung['text']
    # Echte Dauer, nicht Kalendertage: Über eine Zeitumstellung hinweg wäre „400 Tage“ sonst eine Stunde länger.
    grenze = (jetzt.astimezone(timezone.utc) + MAX_CALENDAR_WINDOW).astimezone(zone)
    if von >= grenze:
        return Antwort(f'Das liegt weiter als {MAX_CALENDAR_WINDOW.days} Tage voraus; so weit lese ich Kalender und '
                       'Akten nicht.', [], None)
    gekuerzt = bis > grenze
    if gekuerzt:
        bis = grenze
    einzeltag = (bis - von) <= timedelta(days=1)
    eigene = _eigene(app)

    hinweise: list[str] = []
    akten = bezuege = None
    try:
        from .akten_routes import bausteine, nachfuehren
        berechnung = nachfuehren(app)
        if isinstance(berechnung, dict) and berechnung.get('offen'):
            hinweise.append(f'Die Akten werden noch aufgebaut ({berechnung["offen"]} Quellen fehlen noch); '
                            'Fristen können fehlen.')
        bezuege, akten = bausteine(app)
    except Exception:  # noqa: BLE001 - ohne Akten bleiben Kalender und Aufgaben
        logger.exception('Akten für die Antwort nicht lesbar')
        hinweise.append('Die Akten sind gerade nicht lesbar; Fristen fehlen.')

    termine, kalender_hinweise = _termine(app, von, bis, zone, eigene, akten, jetzt, einzeltag)
    hinweise.extend(kalender_hinweise)
    fristen: list[tuple[str, str | None]] = []
    if akten is not None:
        try:
            fristen = _fristen(app, von, bis, jetzt, eigene, akten, bezuege)
        except Exception:  # noqa: BLE001
            logger.exception('Fristen für die Antwort nicht lesbar')
            hinweise.append('Die Fristen sind gerade nicht lesbar.')
    aufgaben, wartend = _aufgaben(app, von, bis, zone, jetzt)
    if gekuerzt:
        hinweise.append(f'Gekürzt: Ich lese nur bis {MAX_CALENDAR_WINDOW.days} Tage voraus.')

    links: list[dict[str, Any]] = []

    def mit_quelle(text: str, episode_id: str | None) -> str:
        if not episode_id:
            return text
        links.append({'episode_id': episode_id, 'label': f'Quelle {len(links) + 1} öffnen', 'automatic_memory': True})
        return f'{text} [Quelle {len(links)}]'

    abschnitte = [('Termine', [mit_quelle(t, e) for t, e in termine]),
                  ('Fristen und Zusagen', [mit_quelle(t, e) for t, e in fristen]),
                  ('Aufgaben', aufgaben), ('Wartet auf', wartend)]
    zeitraum = {'von': von.isoformat(), 'bis': bis.isoformat(), 'text': text, 'gekuerzt': gekuerzt}
    if not any(zeilen for _, zeilen in abschnitte):
        ohne_kalender = any(h.startswith(('Es ist kein Kalender', 'Der Kalender')) for h in kalender_hinweise)
        satz = (f'Für {text} steht keine Frist an.' if ohne_kalender
                else f'Für {text} steht nichts im Kalender und keine Frist an.')
        return Antwort('\n'.join([satz, *hinweise]), links, zeitraum)
    zeilen = [f'Was {text} ansteht (aus Kalender, Akten und Aufgaben):']
    for titel, inhalt in abschnitte:
        if inhalt:
            zeilen.append('')
            zeilen.append(f'{titel}:')
            zeilen.extend(f'- {z}' for z in inhalt)
    if hinweise:
        zeilen.append('')
        zeilen.extend(hinweise)
    return Antwort('\n'.join(zeilen), links, zeitraum)


__all__ = ['Antwort', 'MAX_VORBEREITET', 'antwort', 'gilt_noch', 'ist_frage']
