"""„Worauf warte ich noch?“ und „Was habe ich zugesagt?“: aus den Akten, ohne Modell.

Ein Stabschef weiß das auswendig. Die Akten wissen es auch (`akten.py`): Jeder vermutlich offene Punkt trägt seine
Richtung (`von_mir` oder `an_mich`, nur bei Mails) und die Entscheidungen des Nutzers (`akten_entscheidungen.py`).

* **Worauf warte ich?** Zusagen anderer an dich und deine eigenen Bitten, zu denen keine spätere Erledigung oder
  Absage vorliegt und die du nicht als erledigt abgelegt hast.
* **Was habe ich zugesagt?** Deine eigenen Zusagen, ebenso.

Vermutlich erledigt ist auch, was eine Antwort im selben Mailverlauf beantwortet (`antwort_im_verlauf.py`), und eine
Einladung ist keine Zusage. Wichtiges steht vorn (Befund A3 der Persona-Prüfung): deine eigenen „wartet auf“-Aufgaben,
Punkte, bei denen du schon nachgefragt hast, verstrichene, dann bald fällige Fristen. Ein Mailverlauf ist eine Zeile.

Wie die Mappe im Gespräch ist die Antwort eine Ansicht: Gespeichert wird nur die Frage, nie ein Zitat; beim Öffnen
des Gesprächs wird sie neu aus den Akten zusammengestellt (`conversations.py`, `server.py`). Jede Zeile nennt ihre
Quelle. Die Antwort behauptet nicht, dass etwas offen ist: Es heißt „vermutlich“.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from typing import Any, Iterable

from .datumstext import tag_text

# Nur die nackte Frageform (mit „noch“, „eigentlich“ …): Nennt die Frage eine Person, ein Projekt oder einen
# Auftrag („Worauf warte ich noch von Silke?“, „Merk dir: …“), geht sie den üblichen Weg mit Suche.
_FUELLER = r'(?:\s+(?:noch|eigentlich|denn|gerade|aktuell|alles|so|überhaupt|ueberhaupt|insgesamt))*'
WARTET_AUF = re.compile(
    r'^\s*(?:und\s+)?(?:'
    r'(?:worauf|auf\s+was)\s+(?:warte|warten)\s+(?:ich|wir)' + _FUELLER +
    r'|wer\s+(?:schuldet|schulden)\s+(?:mir|uns)' + _FUELLER + r'(?:\s+(?:etwas|was))?' + _FUELLER +
    r'|was\s+(?:steht|ist)\s+(?:bei|von)\s+anderen' + _FUELLER + r'\s+(?:aus|offen)'
    r')\s*\??\s*$', re.I)
ZUGESAGT = re.compile(
    r'^\s*(?:und\s+)?(?:'
    r'was\s+(?:habe|hab|haben)\s+(?:ich|wir)' + _FUELLER + r'\s+(?:zugesagt|versprochen)'
    r'|welche\s+zusagen\s+(?:habe|hab|haben)\s+(?:ich|wir)' + _FUELLER + r'(?:\s+offen)?'
    r')\s*\??\s*$', re.I)
ARTEN = ('wartet_auf', 'zugesagt')
#: Höchstens so viele Akten je Art werden gelesen (wie im Briefing, `fristlage.sammeln`).
JE_ART = 60
MAX_PUNKTE = 12


def art_der_frage(frage: str) -> str | None:
    """`wartet_auf`, `zugesagt` oder None: eine feste Frageform, kein Modell."""
    if not isinstance(frage, str) or len(frage) > 300:
        return None
    if WARTET_AUF.match(frage):
        return 'wartet_auf'
    if ZUGESAGT.match(frage):
        return 'zugesagt'
    return None


def passt(art: str, eintrag: dict[str, Any]) -> bool:
    """Gehört ein offener Punkt der Akte zu dieser Frage? Dieselbe Regel für Gespräch, Akte und Personenkarte.

    Worauf du wartest: Zusagen anderer an dich und deine eigenen Bitten (auch deine Einladungen). Eine Einladung an
    dich ist keine Zusage (die Akte führt sie als Bitte, `akten._Leser.zeile`).
    """
    richtung, was = eintrag.get('richtung'), eintrag.get('art')
    if art == 'wartet_auf':
        return (richtung == 'an_mich' and was == 'Zusage') or (richtung == 'von_mir' and was == 'Bitte')
    return richtung == 'von_mir' and was == 'Zusage'


_passt = passt

#: Rang der Wichtigkeit (Befund A3: Wichtiges steht vorn). Kleiner ist wichtiger.
RANG_AUFGABE = 0       # du hast selbst „wartet auf“ gesetzt
RANG_NACHGEFASST = 1   # du hast im selben Verlauf schon nachgefragt
RANG_UEBERFAELLIG = 2  # eine Frist des Punkts ist verstrichen
RANG_FRIST = 3         # eine Frist steht bevor
RANG_SONST = 4
#: Ältere verstrichene Fristen heben einen Punkt nicht mehr nach vorn (wie `fristlage.TAGE_ZURUECK`).
TAGE_ZURUECK = 45


def _zeit(punkt: dict[str, Any]) -> datetime:
    try:
        moment = datetime.fromisoformat(str(punkt.get('occurred_at') or punkt.get('recorded_at') or ''))
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _fristen_der_akte(akte: dict[str, Any], heute: Any) -> dict[tuple[str, str], int]:
    """(Quelle, Wortlaut) -> Tage bis zur frühesten geltenden Frist (negativ: verstrichen)."""
    tage: dict[tuple[str, str], int] = {}
    for status in ('kommend', 'verstrichen'):
        for f in akte.get('fristen', {}).get(status, []):
            if f.get('ersetzt_durch'):
                continue
            try:
                abstand = (date.fromisoformat(f['datum']) - heute).days
            except (KeyError, ValueError):
                continue
            schluessel = (f['episode_id'], f['text'])
            tage[schluessel] = min(tage.get(schluessel, abstand), abstand)
    return tage


def _aufgaben_punkte(aufgaben: Iterable[Any], jetzt: datetime) -> list[dict[str, Any]]:
    """Offene Aufgaben mit „wartet auf“: Was du selbst als Warten vermerkt hast, steht vorn."""
    punkte = []
    for aufgabe in aufgaben:
        if getattr(getattr(aufgabe, 'status', None), 'value', getattr(aufgabe, 'status', None)) != 'open':
            continue
        wer = str(getattr(aufgabe, 'wartet_auf', None) or '').strip()
        if not wer:
            continue
        quelle = str(getattr(getattr(aufgabe, 'provenance', None), 'source_ref', '') or '')
        faellig = getattr(aufgabe, 'due', None)
        punkte.append({
            'aufgabe': {'id': aufgabe.id, 'title': aufgabe.title}, 'wartet_auf': wer, 'text': aufgabe.title,
            'episode_id': quelle[len('episode:'):] if quelle.startswith('episode:') else None,
            'occurred_at': (getattr(aufgabe, 'created_at', None) or jetzt).isoformat(),
            'frist_tage': (faellig.date() - jetzt.date()).days if faellig is not None else None,
            'rang': RANG_AUFGABE, 'art': 'Aufgabe', 'richtung': 'von_mir'})
    return punkte


def sammeln(akten: Any, bezuege: Any, art: str, *, jetzt: datetime | None = None,
            noch_offen: int = 0, aufgaben: Iterable[Any] = (), je_art: int | None = None,
            sache: str | None = None) -> dict[str, Any]:
    """Die passenden offenen Punkte aus den zuletzt aktiven Akten, wichtigste zuerst, je Verlauf einmal.

    `noch_offen`: Quellen, deren Bezüge noch berechnet werden (die Antwort sagt dann, dass sie unvollständig sein
    kann). Gelesen werden je Art die `JE_ART` zuletzt aktiven Akten; sind es mehr, steht das in der Antwort.
    `aufgaben`: offene Aufgaben; bei `wartet_auf` stehen die mit „wartet auf“ vorn (du hast sie selbst vermerkt).
    `sache`: nur diese eine Akte (Karte „Worauf ich warte“ einer Person).

    Reihenfolge (Befund A3): deine „wartet auf“-Aufgaben, dann Punkte, bei denen du im selben Verlauf schon
    nachgefragt hast, dann verstrichene, dann bald fällige Fristen, dann der Rest; innerhalb davon jüngste zuerst.
    Mehrere Punkte desselben Mailverlaufs mit derselben Gegenseite sind eine Zeile (die Zusage vor deiner Bitte).
    """
    if art not in ARTEN:
        raise ValueError('Unbekannte Art der Frage.')
    jetzt = jetzt or datetime.now(timezone.utc)
    heute = jetzt.date()
    je_art = JE_ART if je_art is None else je_art
    punkte: dict[str, dict[str, Any]] = {}
    akten_gesamt = akten_gelesen = 0
    if sache is not None:
        seiten = [{'gesamt': 1, 'sachen': [{'sache': sache}]}]
    else:
        seiten = [bezuege.sachen(art=sachen_art, limit=je_art) for sachen_art in ('person', 'organisation', 'projekt')]
    for seite in seiten:
        akten_gesamt += seite['gesamt']
        akten_gelesen += len(seite['sachen'])
        for eintrag in seite['sachen']:
            # Nur Offenes und Fristen, ohne Namen (Befund A4): Die Namen der gezeigten Akten folgen in einem Durchgang.
            akte = akten.akte(eintrag['sache'], jetzt=jetzt, alle=True, nur_offen=True)
            if akte is None:
                continue
            fristen = _fristen_der_akte(akte, heute)
            for e in akte['offen']['eintraege']:
                ziel = e.get('ziel')
                if not ziel or not passt(art, e):
                    continue
                # Die persönlichste Akte gibt den Namen: Person vor Organisation vor Projekt.
                punkte.setdefault(ziel, {**e, 'sache': akte['sache'], 'sache_name': akte.get('name') or '',
                                         'frist_tage': fristen.get((e['episode_id'], e['text']))})
    gesammelt = list(punkte.values())
    if art == 'wartet_auf' and gesammelt:
        gesammelt = _je_verlauf(akten.episodes, gesammelt, bezuege.eigene_adressen())
    for punkt in gesammelt:
        tage = punkt.get('frist_tage')
        # Wie im Briefing (`fristlage.TAGE_ZURUECK`): Was seit Wochen verstrichen ist, hat sich meist still erledigt.
        punkt['rang'] = (RANG_NACHGEFASST if punkt.get('nachgefasst') else
                         RANG_UEBERFAELLIG if tage is not None and -TAGE_ZURUECK <= tage < 0 else
                         RANG_FRIST if tage is not None and tage >= 0 else RANG_SONST)
    if art == 'wartet_auf':
        aufgaben = [a for a in aufgaben if _wartet(a)]
        if sache is not None:
            from .personen import wartet_auf as wartet_auf_person
            name = bezuege.beschriftung(sache)
            aufgaben = [a for a in aufgaben if wartet_auf_person(a, name)]
        eigene_aufgaben = _aufgaben_punkte(aufgaben, jetzt)
        quellen_der_aufgaben = {p['episode_id'] for p in eigene_aufgaben if p['episode_id']}
        # Eine Aufgabe zur selben Quelle ersetzt den Punkt der Akte (du hast es schon selbst vermerkt).
        gesammelt = eigene_aufgaben + [p for p in gesammelt if p.get('episode_id') not in quellen_der_aufgaben]
    geordnet = sorted(gesammelt, key=lambda p: (p['rang'], -_zeit(p).timestamp()))
    gezeigt = geordnet[:MAX_PUNKTE]
    namen = bezuege.beschriftungen(list(dict.fromkeys(p['sache'] for p in gezeigt if p.get('sache')
                                                       and not p.get('sache_name'))))
    for p in gezeigt:
        if p.get('sache') and not p.get('sache_name'):
            p['sache_name'] = namen.get(p['sache'], '')
    return {'punkte': gezeigt, 'gesamt': len(geordnet), 'noch_offen': max(0, int(noch_offen)),
            'akten_gesamt': akten_gesamt, 'akten_gelesen': akten_gelesen,
            'wichtig': sum(1 for p in geordnet if p['rang'] <= RANG_UEBERFAELLIG)}


def _wartet(aufgabe: Any) -> bool:
    return (getattr(getattr(aufgabe, 'status', None), 'value', getattr(aufgabe, 'status', None)) == 'open'
            and bool(str(getattr(aufgabe, 'wartet_auf', None) or '').strip()))


def _je_verlauf(episodes: Any, punkte: list[dict[str, Any]], eigene: Iterable[str]) -> list[dict[str, Any]]:
    """Eine Zeile je Mailverlauf und Gegenseite; merkt sich, ob du dort schon nachgefragt hast.

    Im Verlauf „Zusage von Frau Brandl, deine Nachfrage“ ist die Zusage der Punkt, auf den du wartest, und deine
    Nachfrage zeigt, dass er dir wichtig ist (`nachgefasst`, mit Datum). Ohne Kopfzeilen bleibt jede Mail für sich.
    """
    from .antwort_im_verlauf import verlaeufe
    from .episodes import mail_address
    selbst = {mail_address(a) for a in eigene if mail_address(a)}
    faeden = verlaeufe(episodes, [p['episode_id'] for p in punkte])
    gruppen: dict[tuple, list[dict[str, Any]]] = {}
    for p in punkte:
        verlauf = faeden.get(p['episode_id'])
        beteiligte = [mail_address(x) for x in p.get('participants') or []]
        gegenseite = (beteiligte[0] if p.get('richtung') == 'an_mich' and beteiligte
                      else next((a for a in beteiligte[1:] if a and a not in selbst), ''))
        wurzel = verlauf[0].episode_id if verlauf else p['episode_id']
        gruppen.setdefault((wurzel, gegenseite or p['episode_id']), []).append(p)
    ergebnis = []
    for gruppe in gruppen.values():
        gruppe.sort(key=_zeit)
        zusagen = [p for p in gruppe if p.get('richtung') == 'an_mich']
        bitten = [p for p in gruppe if p.get('richtung') == 'von_mir']
        haupt = dict(zusagen[-1] if zusagen else bitten[-1])
        # Nachgefasst: Im selben Verlauf hast du nach dieser Zusage noch einmal geschrieben, oder deine Bitte folgt
        # einer früheren Mail derselben Sache (eine Antwort oder deine erste Frage). Gelesen wird der Verlauf selbst,
        # nicht nur, was als Bitte eingeordnet ist: Eine Erinnerung („ob der Vertrag inzwischen vorliegt“) zählt.
        verlauf = faeden.get(haupt['episode_id']) or []
        beginn = _zeit(haupt)
        if haupt.get('richtung') == 'an_mich':
            nachfragen = [m for m in verlauf if m.zeit > beginn and m.absender in selbst and not m.automatisch]
        else:
            frueher = [m for m in verlauf if m.zeit < beginn and not m.automatisch]
            nachfragen = [m for m in verlauf if m.episode_id == haupt['episode_id']] if frueher else []
        if nachfragen:
            letzte = max(nachfragen, key=lambda m: m.zeit)
            haupt['nachgefasst'] = letzte.zeit.isoformat()
            haupt['nachgefasst_episode_id'] = letzte.episode_id
            haupt['verlauf_seit'] = verlauf[0].zeit.isoformat()
        fristen = [p['frist_tage'] for p in gruppe if p.get('frist_tage') is not None]
        haupt['frist_tage'] = min(fristen) if fristen else None
        haupt['im_verlauf'] = len(gruppe)
        ergebnis.append(haupt)
    return ergebnis


def _wer(punkt: dict[str, Any]) -> str:
    """„Silke Vogt (Akademie Taunus), Zusage“ oder „Deine Bitte an Silke Vogt“."""
    from .episodes import mail_address
    from .kontakte import anzeigename
    akte = punkt.get('sache_name') or ''
    if punkt.get('richtung') == 'an_mich':
        absender = (punkt.get('participants') or [''])[0]
        name = anzeigename(absender) or mail_address(absender) or akte
        # Die Organisation oder das Projekt dazu; die Akte einer anderen Person (etwa in Kopie) nennt niemanden.
        if str(punkt.get('sache') or '').startswith('person:'):
            akte = ''
        return f'{name if not akte or akte == name else f"{name} ({akte})"}, {punkt["art"]}'
    was = 'Einladung' if punkt.get('einladung') else punkt['art']
    return f'Deine {was}' + (f' an {akte}' if akte else '')


def _hinweis(punkt: dict[str, Any]) -> str:
    """Warum der Punkt vorn steht: nachgefragt, verstrichen, bald fällig."""
    teile = []
    if punkt.get('nachgefasst') and punkt.get('richtung') == 'von_mir':
        teile.append(f'Nachfrage; der Verlauf läuft seit {tag_text(punkt.get("verlauf_seit"))}')
    elif punkt.get('nachgefasst'):
        teile.append(f'du hast am {tag_text(punkt["nachgefasst"])} nachgefragt')
    tage = punkt.get('frist_tage')
    if tage is not None and tage >= -TAGE_ZURUECK:
        teile.append('Frist heute' if tage == 0 else 'Frist morgen' if tage == 1 else
                     f'Frist in {tage} Tagen' if tage > 1 else 'Frist seit gestern verstrichen' if tage == -1 else
                     f'Frist seit {-tage} Tagen verstrichen')
    return f' ({"; ".join(teile)})' if teile else ''


def als_text(gesammelt: dict[str, Any], art: str) -> tuple[str, list[dict[str, Any]]]:
    """Die Antwort als Text mit nummerierten Quellen."""
    punkte, gesamt = gesammelt['punkte'], gesammelt['gesamt']
    links: list[dict[str, Any]] = []
    # Was die Antwort nicht gesehen hat, sagt sie (nichts still begrenzen).
    grenzen = []
    if gesammelt.get('noch_offen'):
        grenzen.append(f'Die Akten werden noch aufgebaut ({gesammelt["noch_offen"]} Quellen fehlen noch); '
                       'die Liste kann unvollständig sein.')
    if gesammelt.get('akten_gesamt', 0) > gesammelt.get('akten_gelesen', 0):
        grenzen.append(f'Durchgesehen: die {gesammelt["akten_gelesen"]} zuletzt aktiven von '
                       f'{gesammelt["akten_gesamt"]} Akten.')
    if not punkte:
        if art == 'wartet_auf':
            text = ('In deinen Akten finde ich nichts, worauf du noch wartest: keine Zusage an dich und keine Bitte '
                    'von dir ohne spätere Erledigung.')
        else:
            text = 'In deinen Akten finde ich keine eigene Zusage ohne spätere Erledigung.'
        return '\n'.join([text, *grenzen]), links
    if art == 'wartet_auf':
        kopf = (f'Du wartest vermutlich noch auf {"eine Sache" if gesamt == 1 else f"{gesamt} Dinge"} '
                '(aus deinen Akten; keine spätere Erledigung gefunden):')
    else:
        kopf = (f'Du hast vermutlich noch {"eine Zusage" if gesamt == 1 else f"{gesamt} Zusagen"} offen '
                '(aus deinen Akten; keine spätere Erledigung gefunden):')
    zeilen = [kopf]
    for nummer, punkt in enumerate(punkte, 1):
        quelle = ''
        if punkt.get('episode_id'):
            links.append({'episode_id': punkt['episode_id'], 'label': f'Quelle {len(links) + 1} öffnen',
                          'automatic_memory': True})
            quelle = f' [Quelle {len(links)}]'
        if punkt.get('aufgabe'):
            # Was du selbst als „wartet auf“ vermerkt hast: die Aufgabe, nicht ein Zitat.
            zeilen.append(f'{nummer}. Deine Aufgabe „{" ".join(str(punkt["text"]).split())}“, wartet auf '
                          f'{punkt["wartet_auf"]}{_hinweis(punkt)}{quelle}')
            continue
        wann = tag_text(punkt.get('occurred_at') or punkt.get('recorded_at'))
        # Zeilenumbrüche des Originals würden die nummerierte Liste zerreißen: ein Zitat, eine Zeile.
        zitat = ' '.join(str(punkt['text']).split())
        zeilen.append(f'{nummer}. {_wer(punkt)}{f" vom {wann}" if wann else ""}{_hinweis(punkt)}: „{zitat}“{quelle}')
    if gesamt > len(punkte):
        zeilen.append(f'Die wichtigsten {len(punkte)} von {gesamt}; die übrigen stehen in den Akten.')
    zeilen.extend(grenzen)
    zeilen.append('Ob es wirklich noch offen ist, steht in den Quellen nicht. In der Akte legst du einen Punkt mit '
                  'einem Klick als erledigt ab.')
    return '\n'.join(zeilen), links


__all__ = ['ARTEN', 'als_text', 'art_der_frage', 'passt', 'sammeln']
