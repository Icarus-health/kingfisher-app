"""Transkript-Eingang: aus einer exportierten Mitschrift wird eine Quelle.

Meetings zeichnet der Nutzer mit MacWhisper auf, andere haben Teams, Meet oder
Zoom. Jede dieser Anwendungen kann eine Mitschrift als Datei ablegen (.txt,
.vtt, .srt, .docx, .md). Dieses Modul liest so eine Datei und sagt, **was
buchstäblich darinsteht**:

* den lesbaren Text (Sprecher bleiben stehen, Zeitmarken fallen weg),
* wer gesprochen hat (nur echte Namen, nie „Sprecher 1“),
* wann es stattfand, **soweit die Datei es verrät** (Dateiname oder Kopf).

Es deutet nichts. Welcher Termin gemeint ist und welcher Sprecher welche Person
ist, entscheidet `transkript_zuordnung.py`, und das nur bei Eindeutigkeit. Der
Dateizeitpunkt (`geaendert`) ist ein schwaches Zeichen und wird deshalb nie als
Zeitpunkt der Quelle übernommen: Ein kopierter Ordner würde sonst jede Quelle
als neue Fassung erscheinen lassen.

Die Rohquelle ist eine Episode der Art `document` mit der Marke `transkript`.
Damit gilt für sie alles, was für Dokumente gilt: Suche, Einordnung, Akten,
Entzug. Ein Fakt wird daraus nur über Vorschlag und Annahme (`10-verdichtung.md`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any

from .document_text import docx_text
from .model import user_timezone
from .nachbereitung import text_aus_mitschrift

SUFFIXES = frozenset({'.txt', '.vtt', '.srt', '.docx', '.md'})
"""Was der Eingangsordner aufnimmt. Alles andere bleibt liegen und wird nicht gelesen."""

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 512 * 1024
MARKE = 'transkript'
"""Marke an der Episode; daran erkennen Zuordnung, Status und Anzeige eine Mitschrift."""

# Wörter, die als Sprechermarke nie ein Name sind (Kopfzeilen einer Mitschrift oder eines Protokolls).
_KEIN_SPRECHER = frozenset({
    'datum', 'date', 'ort', 'thema', 'teilnehmer', 'agenda', 'betreff', 'hinweis', 'protokoll', 'ergebnis',
    'aufgabe', 'todo', 'notiz', 'notizen', 'fazit', 'wichtig', 'anwesend', 'dauer', 'uhrzeit', 'zeit',
    'titel', 'title', 'subject', 'participants', 'attendees', 'location', 'duration', 'summary',
    'zusammenfassung', 'nächste schritte', 'aktionspunkte', 'beschluss', 'beschlüsse', 'transcript',
    'transkript', 'mitschrift', 'speakers', 'sprecher', 'quelle', 'anmerkung', 'frage', 'antwort',
})
_ANONYM = re.compile(r'^(?:sprecher|speaker|teilnehmer|person|guest|gast|unknown|unbekannt|referent|moderator)\s*\d*$', re.I)
_EIGENE_ANREDE = frozenset({'ich', 'me', 'you', 'du', 'sie'})

_ZEITMARKE = r'\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d{1,3})?'
_MIT_ZEIT_VORNE = re.compile(rf'^\s*[\[(]?{_ZEITMARKE}[\])]?\s*[-–]?\s*(?P<rest>\S.*)$')
_NAME_MIT_ZEIT = re.compile(rf'^\s*(?P<n>[^\W\d_][^:\[\](){{}}]{{0,38}}?)\s*[\[(]{_ZEITMARKE}[\])]\s*:\s*(?P<t>\S.*)$')
_NAME_ZEILE_ZEIT = re.compile(rf'^\s*(?P<n>[^\W\d_][^:\[\](){{}}\d]{{0,38}}?)\s+[\[(]?{_ZEITMARKE}[\])]?\s*$')
_ZEITZEILE = re.compile(rf'^\s*[\[(]?{_ZEITMARKE}[\])]?\s*$')
_SPRECHERZEILE = re.compile(r"^\s*(?P<n>[^\W\d_][\w.'’\- ]{0,38}?)\s*:\s+(?P<t>\S.*)$")

# -- Zeit aus Name und Kopf --------------------------------------------------

_TZ = r'(?:\s*(?P<tz>Z|GMT\s?[+-]\d{1,2}(?::?\d{2})?|UTC\s?[+-]\d{1,2}(?::?\d{2})?|[+-]\d{2}:?\d{2}))?'
_MIT_ZEIT = (
    re.compile(rf'(?P<y>\d{{4}})-(?P<m>\d{{2}})-(?P<d>\d{{2}})(?:[T _-]|\s+at\s+|\s+um\s+)+(?P<h>\d{{1,2}})[:.h](?P<mi>\d{{2}})(?::(?P<s>\d{{2}}))?{_TZ}', re.I),
    re.compile(rf'(?<!\d)(?P<y>\d{{4}})(?P<m>\d{{2}})(?P<d>\d{{2}})[_T-](?P<h>\d{{2}})(?P<mi>\d{{2}})(?P<s>\d{{2}})?(?!\d){_TZ}'),
    re.compile(rf'(?<!\d)(?P<d>\d{{1,2}})\.(?P<m>\d{{1,2}})\.(?P<y>\d{{4}})[ ,_-]+(?:um\s+)?(?P<h>\d{{1,2}})[:.](?P<mi>\d{{2}})(?::(?P<s>\d{{2}}))?{_TZ}', re.I),
)
_NUR_TAG = (
    re.compile(r'(?<!\d)(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?!\d)'),
    re.compile(r'(?<!\d)(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})(?!\d)'),
    re.compile(r'(?<!\d)(?P<y>20\d{2})(?P<m>\d{2})(?P<d>\d{2})(?!\d)'),
)
_DATUMSTEILE = re.compile(
    r'(?:\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|(?<!\d)\d{8}(?!\d))'
    r'(?:(?:[T _-]|\s+at\s+|\s+um\s+)+\d{1,2}[:.h]?\d{2}(?::?\d{2})?(?:\s*(?:GMT|UTC)\s?[+-]\d{1,2}(?::?\d{2})?|Z)?)?', re.I)
_ZEIT_IM_NAMEN = re.compile(r'(?<!\d)\d{6}(?!\d)')
_KOPFWORT = re.compile(r'^\s*(?:datum|date|zeit|beginn|start|wann|when)\s*:\s*(?P<wert>.+?)\s*$', re.I)


def _zone(name: str | None) -> Any:
    if name:
        text = name.upper().replace(' ', '')
        if text == 'Z':
            return timezone.utc
        found = re.fullmatch(r'(?:GMT|UTC)?([+-])(\d{1,2}):?(\d{2})?', text)
        if found:
            minuten = int(found.group(2)) * 60 + int(found.group(3) or 0)
            return timezone(timedelta(minutes=minuten if found.group(1) == '+' else -minuten))
    return user_timezone() or timezone.utc


def _datum(gruppen: dict[str, Any]) -> date | None:
    try:
        jahr, monat, tag = int(gruppen['y']), int(gruppen['m']), int(gruppen['d'])
        if not 2000 <= jahr <= 2100:
            return None
        return date(jahr, monat, tag)
    except (ValueError, TypeError):
        return None


def zeit_aus_text(text: str) -> tuple[datetime | None, date | None]:
    """Der abgelesene Zeitpunkt in `text`: (genauer Zeitpunkt, nur Tag).

    Ein genauer Zeitpunkt trägt Datum *und* Uhrzeit. Ohne Zeitzone in der
    Angabe gilt die Zeitzone des Nutzers. Steht nur ein Datum da, kommt nur der
    Tag zurück. Nichts wird geraten: Was nicht darin steht, bleibt leer.
    """
    for muster in _MIT_ZEIT:
        for treffer in muster.finditer(text):
            gruppen = treffer.groupdict()
            tag = _datum(gruppen)
            if tag is None:
                continue
            try:
                moment = datetime(tag.year, tag.month, tag.day, int(gruppen['h']), int(gruppen['mi']),
                                  int(gruppen.get('s') or 0), tzinfo=_zone(gruppen.get('tz')))
            except ValueError:
                continue
            return moment, tag
    for muster in _NUR_TAG:
        for treffer in muster.finditer(text):
            tag = _datum(treffer.groupdict())
            if tag is not None:
                return None, tag
    return None, None


# -- Sprecher und Text -------------------------------------------------------


def _zeilen_vereinheitlichen(text: str) -> list[str]:
    """Bringt die üblichen Schreibweisen auf „Name: Text“.

    Erkannt werden `[00:01:02] Name: Text`, `Name [00:01:02]: Text` und die
    Teams-Form mit Name und Zeit in einer Zeile und dem Text darunter. Was in
    keine dieser Formen passt, bleibt unverändert stehen.
    """
    zeilen = [zeile.rstrip() for zeile in text.replace('\r\n', '\n').replace('\r', '\n').split('\n')]
    ergebnis: list[str] = []
    index = 0
    while index < len(zeilen):
        zeile = zeilen[index]
        gefunden = _NAME_MIT_ZEIT.match(zeile)
        if gefunden:
            ergebnis.append(f"{gefunden.group('n').strip()}: {gefunden.group('t').strip()}")
            index += 1
            continue
        kopf = _NAME_ZEILE_ZEIT.match(zeile)
        if kopf and index + 1 < len(zeilen) and zeilen[index + 1].strip() and not _ZEITZEILE.match(zeilen[index + 1]):
            ergebnis.append(f"{kopf.group('n').strip()}: {zeilen[index + 1].strip()}")
            index += 2
            continue
        ohne = _MIT_ZEIT_VORNE.match(zeile)
        ergebnis.append(ohne.group('rest') if ohne and _SPRECHERZEILE.match(ohne.group('rest')) else zeile)
        index += 1
    return ergebnis


def ist_sprecherzeile(zeile: str) -> bool:
    """Beginnt die Zeile mit einem Sprecherwechsel („Name: Text“)? Für die Abschnittsbildung langer Mitschriften."""
    return _SPRECHERZEILE.match(zeile) is not None


def _echter_name(marke: str) -> bool:
    schluessel = ' '.join(marke.split()).casefold()
    if not schluessel or schluessel in _KEIN_SPRECHER or schluessel in _EIGENE_ANREDE or _ANONYM.match(schluessel):
        return False
    return len(schluessel.split()) <= 4 and not re.search(r'\d', schluessel)


def sprecher_und_text(text: str) -> tuple[list[str], int, str]:
    """(echte Sprecher, Zahl anonymer Sprecher, bereinigter Text).

    Eine Zeile „Name: …“ gilt nur dann als Sprecherwechsel, wenn dieselbe Marke
    mindestens zweimal vorkommt. Sonst wäre „Ergebnis: alles offen“ ein Mensch.
    """
    zeilen = _zeilen_vereinheitlichen(text)
    zaehler: dict[str, int] = {}
    for zeile in zeilen:
        gefunden = _SPRECHERZEILE.match(zeile)
        if gefunden:
            marke = ' '.join(gefunden.group('n').split())
            zaehler[marke] = zaehler.get(marke, 0) + 1
    marken = {marke for marke, anzahl in zaehler.items() if anzahl >= 2 and marke.casefold() not in _KEIN_SPRECHER}
    if marken:
        # Ist das Muster erst etabliert, zählt auch, wer nur einmal sprach: bis drei Wörter,
        # jedes groß geschrieben („Bert Kraus“), nie ein Kopfwort.
        marken |= {marke for marke, anzahl in zaehler.items()
                   if anzahl == 1 and marke.casefold() not in _KEIN_SPRECHER and len(marke.split()) <= 3
                   and (_ANONYM.match(marke.casefold()) or all(wort[:1].isupper() for wort in marke.split()))}
    echte: list[str] = []
    anonym: set[str] = set()
    for zeile in zeilen:
        gefunden = _SPRECHERZEILE.match(zeile)
        if not gefunden:
            continue
        marke = ' '.join(gefunden.group('n').split())
        if marke not in marken:
            continue
        if _ANONYM.match(marke.casefold()):
            anonym.add(marke.casefold())
        elif _echter_name(marke) and marke not in echte:
            echte.append(marke)
    bereinigt = re.sub(r'\n{3,}', '\n\n', '\n'.join(zeilen)).strip()
    return echte, len(anonym), bereinigt


def _lesbare_zeit(moment: datetime) -> str:
    zone = user_timezone()
    lokal = moment.astimezone(zone) if zone is not None else moment
    return lokal.strftime('%d.%m.%Y, %H:%M Uhr')


def _titel_aus_dateiname(stamm: str) -> str:
    """Der Titel ohne Datum, Uhrzeit und Trennzeichen: „2026-09-28 14.30 Jour fixe Winter“ wird „Jour fixe Winter“."""
    text = _DATUMSTEILE.sub(' ', stamm)
    text = re.sub(r'\(\s*(?:[^)]*(?:GMT|UTC)[^)]*)?\)', ' ', text, flags=re.I)
    text = _ZEIT_IM_NAMEN.sub(' ', text)
    text = re.sub(r'_+', ' ', text)
    text = re.sub(r'\b(?:transcript|transkript|mitschrift)\b', ' ', text, flags=re.I)
    return ' '.join(text.split()).strip(' -–—.,')


@dataclass(frozen=True)
class Transkript:
    """Was eine Mitschriftdatei hergibt. Nichts davon ist gedeutet."""

    dateiname: str
    titel: str
    text: str
    format: str
    sprecher: tuple[str, ...] = ()
    anonyme_sprecher: int = 0
    beginn: datetime | None = None
    tag: date | None = None
    zeit_quelle: str = ''
    """`name` (Dateiname), `kopf` (Datum im Text oder Frontmatter) oder leer."""
    geaendert: datetime | None = None
    """Dateizeitpunkt. Nur als schwaches Zeichen für die Zuordnung gedacht."""

    def hinweise(self) -> dict[str, Any]:
        """Die Zeichen für die Zuordnung, als einfaches Wörterbuch (JSON-fähig)."""
        return {
            'titel': self.titel,
            'sprecher': list(self.sprecher),
            'beginn': self.beginn.isoformat() if self.beginn else None,
            'tag': self.tag.isoformat() if self.tag else None,
            'zeit_quelle': self.zeit_quelle,
            'geaendert': self.geaendert.isoformat() if self.geaendert else None,
        }

    def kopf(self) -> str:
        zeilen = [f'Mitschrift: {self.titel}', f'Datei: {self.dateiname}']
        if self.beginn:
            zeilen.append(f'Zeit: {_lesbare_zeit(self.beginn)}')
        elif self.tag:
            zeilen.append(f'Tag: {self.tag.strftime("%d.%m.%Y")}')
        if self.sprecher:
            zeilen.append('Sprecher: ' + ', '.join(self.sprecher))
        return '\n'.join(zeilen)

    def rumpf(self) -> str:
        """Der Text der Episode: Kopf und Mitschrift. Der Digest hängt daran."""
        return f'{self.kopf()}\n\n{self.text}'


def _dekodieren(daten: bytes) -> str:
    if daten.startswith((b'\xff\xfe', b'\xfe\xff')):
        return daten.decode('utf-16')
    try:
        return daten.decode('utf-8-sig')
    except UnicodeDecodeError:
        return daten.decode('cp1252')


def _kopf_zeit(meta: dict[str, str], text: str) -> tuple[datetime | None, date | None]:
    werte = [meta[k] for k in ('date', 'datum', 'start', 'beginn') if meta.get(k)]
    for zeile in text.splitlines()[:12]:
        treffer = _KOPFWORT.match(zeile)
        if treffer:
            werte.append(treffer.group('wert'))
    tag = None
    for wert in werte:
        moment, kopf_tag = zeit_aus_text(wert)
        if moment is not None:
            return moment, kopf_tag
        tag = tag or kopf_tag
    return None, tag


def lesen(name: str, daten: bytes, geaendert: datetime | None = None) -> Transkript:
    """Liest eine Mitschriftdatei. `ValueError` mit deutschem Grund, wenn sie unbrauchbar ist."""
    from .ingest import parse_frontmatter
    endung = PurePosixPath(name).suffix.lower()
    if endung not in SUFFIXES:
        raise ValueError('Dieses Dateiformat wird für Mitschriften nicht gelesen.')
    if len(daten) > MAX_BYTES:
        raise ValueError('Die Datei überschreitet 5 MiB.')
    meta: dict[str, str] = {}
    if endung == '.docx':
        roh = docx_text(daten)
    else:
        if len(daten) > MAX_TEXT:
            raise ValueError('Die Textdatei überschreitet 512 KiB.')
        try:
            roh = _dekodieren(daten)
        except UnicodeError as exc:
            raise ValueError('Die Datei ist kein lesbarer Text.') from exc
        if endung in {'.srt', '.vtt'}:
            roh = text_aus_mitschrift(roh, endung[1:])
        elif endung == '.md':
            meta, roh = parse_frontmatter(roh)
    if '\0' in roh:
        raise ValueError('Die Datei enthält ungültige Zeichen.')
    echte, anonym, text = sprecher_und_text(roh)
    if not text.strip():
        raise ValueError('Die Mitschrift ist leer.')
    stamm = PurePosixPath(name).stem
    titel = (meta.get('title') or meta.get('titel') or '').strip() or _titel_aus_dateiname(stamm) or 'Mitschrift'
    beginn, tag = zeit_aus_text(stamm)
    quelle = 'name' if (beginn or tag) else ''
    if beginn is None:
        moment, kopf_tag = _kopf_zeit(meta, text)
        if moment is not None:
            beginn, tag, quelle = moment, kopf_tag, 'kopf'
        elif tag is None and kopf_tag is not None:
            tag, quelle = kopf_tag, 'kopf'
    return Transkript(dateiname=name, titel=titel, text=text, format=endung[1:], sprecher=tuple(echte),
                      anonyme_sprecher=anonym, beginn=beginn, tag=tag, zeit_quelle=quelle, geaendert=geaendert)


def episode_daten(transkript: Transkript) -> dict[str, Any]:
    """Was `EpisodeStore.record` für diese Mitschrift bekommt (Titel, Text, Zeitpunkt, Beteiligte, Marke)."""
    zone = user_timezone() or timezone.utc
    if transkript.beginn is not None:
        zeitpunkt = transkript.beginn
    elif transkript.tag is not None:
        # Nur der Tag ist bekannt: Mitternacht der Nutzerzone, ohne eine Uhrzeit zu behaupten.
        zeitpunkt = datetime(transkript.tag.year, transkript.tag.month, transkript.tag.day, tzinfo=zone)
    else:
        zeitpunkt = None
    return {'title': f'Mitschrift: {transkript.titel}', 'body': transkript.rumpf(), 'occurred_at': zeitpunkt,
            'participants': list(transkript.sprecher), 'tags': [MARKE]}


def aufnehmen(episodes: Any, transkript: Transkript, herkunft: Any, source_key: str) -> tuple[Any, bool]:
    """Legt die Mitschrift als Quelle ab. Gibt (Episode, neu) zurück.

    Die Identität einer Mitschrift ist ihr **Text** unter ihrem Quellenschlüssel.
    Stimmt der Text mit dem der aktuellen Fassung überein, ist es dieselbe
    Quelle: Nach der Zuordnung tragen ihre Metadaten Sprecher als Beteiligte
    (`EpisodeStore.add_contacts`), und ein erneutes Einlesen mit den
    Metadaten der Datei würde sonst wie eine Dublette mit anderen Metadaten
    aussehen. Eine wegen getrennten Ordners entzogene Quelle gilt bei
    unverändertem Text wieder (Marke `entzogen:ordner`, nie ein Ausschluss
    des Nutzers).
    """
    from .episodes import ENTZUG_MARKE, EpisodeError, EpisodeKind, EpisodeState, digest_of
    daten = episode_daten(transkript)
    kopf_id = episodes.source_head(source_key)
    if kopf_id:
        kopf = episodes.get(kopf_id)
        if kopf.digest == digest_of(daten['body']):
            if kopf.state is EpisodeState.IGNORED and f'{ENTZUG_MARKE}ordner' in kopf.tags:
                try:
                    kopf = episodes.reopen(kopf.id)
                except EpisodeError:
                    pass
            return kopf, False
    return episodes.record(EpisodeKind.DOCUMENT, daten['title'], daten['body'], herkunft, source_key=source_key,
                           occurred_at=daten['occurred_at'], participants=daten['participants'], tags=daten['tags'])


__all__ = ['MARKE', 'MAX_BYTES', 'aufnehmen', 'MAX_TEXT', 'SUFFIXES', 'Transkript', 'episode_daten', 'lesen',
           'ist_sprecherzeile', 'sprecher_und_text', 'zeit_aus_text']
