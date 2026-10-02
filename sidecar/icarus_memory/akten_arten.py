"""Private Akten-Arten (M4): Haushalt, Familie, Gesundheit, Verträge. Der eine Ort dafür.

Neben Person, Organisation, Projekt, Ort und Thema (`bezuege.ARTEN`) bekommt eine Akte, deren Absender ein
Arzt, eine Versicherung, ein Energieversorger, ein Vermieter oder eine Schule ist, eine **private Art**. Die Art
gehört zur Akte einer Organisation (die Zahnarztpraxis, die Hausratversicherung, die Kita), nicht zu einer
einzelnen Quelle: Einmal bestätigt, gilt sie für alles, was von dort kommt.

Regeln (`docs/49-kreis-und-privat.md`):

* **Vorschlag, dann Bestätigung.** Kingfisher schlägt die Art aus festen Regeln vor (Absender, Betreff), ohne
  Modell. Erst der Klick eines Menschen macht sie fest (`ArtAblage.bestaetigen`); „Keine davon“ ist auch eine
  Antwort und bleibt stehen. Ein bestätigter Wert wird nie automatisch geändert.
* **Nur aus dem Absender.** Ein Betreff wie „Rechnung“ oder „Vertrag“ kommt auch im Beruf vor; er allein macht
  keine private Akte. Er stützt den Vorschlag und steht in der Begründung.
* **Fristen mit Beleg, nie geraten.** Kündigungs- und Zahlungsfristen aus solchen Mails werden als
  Aufgabenvorschläge vorgelegt (`fristen_vorlegen`), nur mit einem ausgeschriebenen Kalenderdatum („30.11.2026“,
  „30. November 2026“), nie aus „in zwei Wochen“ gerechnet. Datum und Betrag stehen wörtlich so im Vorschlag, wie
  sie in der Quelle stehen; die Textstelle ist der Beleg. Erst die Annahme macht daraus eine Aufgabe mit
  Fälligkeit (`task_candidates.py`).
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as uhrzeit
from typing import Any, Iterable

ARTEN = ('haushalt', 'familie', 'gesundheit', 'vertraege')
KEINE = 'keine'
WAHLEN = (*ARTEN, KEINE)
ART_TEXT = {'haushalt': 'Haushalt', 'familie': 'Familie', 'gesundheit': 'Gesundheit', 'vertraege': 'Verträge',
            KEINE: 'Keine davon'}

TABLES = {'akten_arten': {'sache', 'art', 'vorschlag', 'bestaetigt_am'}}
PRIMARY_KEYS = {'akten_arten': {'sache'}}


def migrate(connection: sqlite3.Connection) -> None:
    """Teil der Migration 16: die bestätigten Arten der Akten (nur was ein Mensch gewählt hat)."""
    connection.execute("""CREATE TABLE akten_arten (
        sache TEXT PRIMARY KEY,
        art TEXT NOT NULL CHECK(art IN ('haushalt','familie','gesundheit','vertraege','keine')),
        vorschlag TEXT NOT NULL DEFAULT '', bestaetigt_am REAL NOT NULL)""")


# -- Vorschlag aus festen Regeln -----------------------------------------------

def _wort(muster: str) -> re.Pattern:
    return re.compile(r'(?<![a-z0-9])(?:' + muster + r')(?![a-z0-9])')


#: Absender (Name oder Domäne, klein, Umlaute umschrieben) -> Art. Wortanfang zählt, damit „zahnarztpraxis“ passt,
#: „physioplaner“ (eine Software) aber nicht „physio“ ist.
ABSENDER = {
    'gesundheit': _wort(r'zahnarzt\w*|zahnaerzt\w*|hausarzt\w*|hausaerzt\w*|kinderarzt\w*|frauenarzt\w*|augenarzt\w*|'
                        r'hautarzt\w*|arztpraxis\w*|aerztehaus|praxis|apotheke\w*|physio|physiotherapie\w*|'
                        r'krankenkasse\w*|kieferorthopaed\w*|orthopaed\w*|heilpraktiker\w*|hebamme\w*|dental\w*|'
                        r'dr\.? ?med\.?|zahnmedizin\w*'),
    'vertraege': _wort(r'\w*versicher\w*|assekuranz\w*|bausparkasse\w*|mobilfunk\w*|fitness\w*|leasing\w*'),
    'haushalt': _wort(r'stadtwerke\w*|\w*energie\w*|strom\w*|gasversorg\w*|wasserversorg\w*|hausverwaltung\w*|'
                      r'vermiet\w*|wohnungs\w*|wohnbau\w*|immobilien\w*|eigentuemer\w*|schornstein\w*|abfall\w*|'
                      r'entsorgung\w*|beitragsservice|rundfunk\w*|sanitaer\w*|heizung\w*'),
    'familie': _wort(r'(?<!hoch)schul\w*|grundschule\w*|gymnasium\w*|realschule\w*|kita\w*|kindergarten\w*|'
                     r'kinderkrippe\w*|krippe|hort|elternbeirat\w*|musikschule\w*|familienkasse\w*'),
}
#: Betreffwörter, die einen Vorschlag stützen (nie allein tragen).
BETREFF = {
    'vertraege': _wort(r'kuendigung\w*|vertrag\w*|vertraeg\w*|police\w*|versicherungsschein\w*|beitragsanpassung\w*|'
                       r'beitrag\w*'),
    'haushalt': _wort(r'nebenkosten\w*|betriebskosten\w*|abschlag\w*|zaehlerstand\w*|jahresabrechnung\w*|miete\w*|'
                      r'mieterhoehung\w*|stromrechnung\w*'),
    'gesundheit': _wort(r'rezept\w*|befund\w*|zahnreinigung\w*|behandlung\w*|impf\w*|vorsorge\w*|untersuchung\w*|'
                        r'arzttermin\w*|kostenplan\w*'),
    'familie': _wort(r'elternabend\w*|elternbrief\w*|zeugnis\w*|einschulung\w*|klassenfahrt\w*|schulausflug\w*'),
}
#: Diese Wörter stützen jede private Art und stehen in der Begründung, wenn sie vorkommen.
ALLGEMEIN = _wort(r'rechnung\w*|termin\w*|zahlungserinnerung\w*|mahnung\w*|kuendigung\w*|vertrag\w*')


def normal(text: Any) -> str:
    """Klein, Umlaute umschrieben, Bindestriche als Leerzeichen: so werden Name und Domäne verglichen."""
    text = str(text or '').casefold()
    for alt, neu in (('ä', 'ae'), ('ö', 'oe'), ('ü', 'ue'), ('ß', 'ss')):
        text = text.replace(alt, neu)
    return re.sub(r'[-_]+', ' ', text)


@dataclass(frozen=True)
class ArtVorschlag:
    """Was Kingfisher für eine Akte vorschlägt, mit Begründung in einem Satz. `art` ist leer ohne Vorschlag."""

    art: str
    begruendung: str
    merkmale: tuple[str, ...] = ()

    def als_dict(self) -> dict[str, Any]:
        return {'art': self.art or None, 'art_text': ART_TEXT.get(self.art, ''), 'begruendung': self.begruendung,
                'merkmale': list(self.merkmale)}


KEIN_VORSCHLAG = ArtVorschlag('', 'Nichts deutet auf Haushalt, Familie, Gesundheit oder Verträge.')


def _treffer(muster: re.Pattern, text: str) -> str:
    gefunden = muster.search(text)
    return gefunden.group(0) if gefunden else ''


def vorschlagen(absender: Iterable[str], betreffe: Iterable[str]) -> ArtVorschlag:
    """Die Art einer Akte aus den Namen und Domänen ihrer Absender und den Betreffen ihrer Quellen. Rein.

    Getragen wird der Vorschlag allein vom Absender („Zahnarztpraxis“, „versicherung“, „stadtwerke“, „kita“);
    Betreffe stützen ihn und entscheiden nur, wenn zwei Arten im Absender stehen.
    """
    namen = [str(a) for a in absender if str(a or '').strip()]
    texte = [normal(a) for a in namen]
    betreffe = [str(b) for b in betreffe if str(b or '').strip()]
    stuetzen: dict[str, list[str]] = {art: [] for art in ARTEN}
    for betreff in betreffe:
        for art, muster in BETREFF.items():
            wort = _treffer(muster, normal(betreff))
            if wort and betreff not in stuetzen[art]:
                stuetzen[art].append(betreff)
    kandidaten: list[tuple[int, int, str, str]] = []
    for art, muster in ABSENDER.items():
        for roh, text in zip(namen, texte):
            if _treffer(muster, text):
                kandidaten.append((-len(stuetzen[art]), ARTEN.index(art), art, roh))
                break
    if not kandidaten:
        return KEIN_VORSCHLAG
    _, _, art, wer = min(kandidaten)
    merkmale = [f'Absender „{wer}“']
    belege = stuetzen[art] or [b for b in betreffe if ALLGEMEIN.search(normal(b))]
    if belege:
        gezeigt = [f'„{b[:60]}“' for b in belege[:2]]
        merkmale.append('Betreff ' + ' und '.join(gezeigt))
    return ArtVorschlag(art, ', '.join(merkmale) + '.', tuple(merkmale))


# -- Fristen in privaten Mails ---------------------------------------------------

_KUENDIGUNG = re.compile(r'kündig|kuendig|kündbar|kuendbar', re.I)
#: „wird am 05.10. abgebucht“ ist keine Frist: Da ist nichts zu tun. Deshalb fehlt „abbuchen“ hier mit Absicht.
_ZAHLUNG = re.compile(r'zahlbar|überweis|ueberweis|fällig|faellig|bezahl|zahlungsziel|zu zahlen|begleichen', re.I)
_BETRAG = re.compile(r'(?<![\d,.])(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s?(?:€|EUR\b|Euro\b)'
                     r'|(?:€|EUR)\s?(\d{1,3}(?:\.\d{3})*,\d{2})(?![\d])')
_BETRAGSZEILE = re.compile(r'(?:rechnungsbetrag|gesamtbetrag|betrag|summe|zu zahlen|endbetrag|nachzahlung)', re.I)
#: Sätze, die eine erledigte Sache melden, sind keine Frist („Ihre Zahlung ist eingegangen“, „wurde gekündigt“).
_ERLEDIGT = re.compile(r'gekündigt|gekuendigt|kündigungsbestätigung|kuendigungsbestaetigung|eingegangen|gutgeschrieben|'
                       r'beglichen|bezahlt\b|vielen dank für ihre zahlung|(?:zahlung|betrag|überweisung) (?:dankend )?erhalten',
                       re.I)
_SATZENDE = re.compile(r'[.!?](?=\s|$)|\n')
_ABKUERZUNG = re.compile(r'(?:\b(?:Dr|Nr|Str|ca|bzw|usw|Hr|Fr|St|Tel|inkl|zzgl|evtl)|\b[a-z]\.[a-z])$')
#: Ein ausgeschriebenes Kalenderdatum: Tag und Monat als Ziffern oder Name. „bis Freitag“ zählt nicht.
_AUSGESCHRIEBEN = re.compile(r'\d{1,2}\.\s?(?:\d{1,2}\.|[A-Za-zÄÖÜäöü]{3,})')


@dataclass(frozen=True)
class FristVorschlag:
    """Eine Frist aus einer Quelle: Art, Datum, Ausdruck und Betrag wörtlich, der Satz als Beleg."""

    art: str
    """`kuendigung` oder `zahlung`."""
    datum: date
    ausdruck: str
    satz: str
    betrag: str = ''

    def aussage(self, wer: str) -> str:
        """Der Satz des Vorschlags. Jede Zahl darin steht wörtlich in der Quelle (Ausdruck, Betrag)."""
        von = f' ({wer})' if wer else ''
        if self.art == 'kuendigung':
            return f'Kündigung möglich bis {self.ausdruck}{von}'
        return f'Zahlung bis {self.ausdruck}' + (f': {self.betrag}' if self.betrag else '') + von


def _saetze(text: str) -> list[str]:
    """Sätze eines Textes, wörtlich. „15. Oktober“, „Dr. Krämer“ und „30.11.“ beenden keinen Satz, „2026.“ schon."""
    ergebnis, anfang = [], 0
    for treffer in _SATZENDE.finditer(text):
        davor = text[anfang:treffer.start()]
        if treffer.group(0) == '.' and ((re.search(r'\d$', davor) and not re.search(r'\d{4}$', davor))
                                        or _ABKUERZUNG.search(davor)):
            continue
        satz = text[anfang:treffer.end()].strip()
        if satz:
            ergebnis.append(satz)
        anfang = treffer.end()
    rest = text[anfang:].strip()
    if rest:
        ergebnis.append(rest)
    return ergebnis


def fristen_finden(text: str, bezug: datetime | date) -> list[FristVorschlag]:
    """Kündigungs- und Zahlungsfristen eines Textes. Rein, ohne Modell.

    Je Satz mit Kündigungs- oder Zahlungswort und ausgeschriebenem Kalenderdatum, das noch nicht verstrichen ist (weder
    am Tag der Quelle noch heute), eine Frist; Sätze, die Erledigtes melden („eingegangen“, „gekündigt“), nicht. Der
    Betrag kommt aus demselben Satz, sonst aus einer Zeile wie „Rechnungsbetrag: 86,40 €“ derselben Mail; fehlt er,
    bleibt er leer.
    """
    from .fristen import bezugstag, fristen_in
    from .model import now

    heute = max(bezugstag(bezug), bezugstag(now()))
    betrag_der_mail = ''
    for zeile in text.splitlines():
        if _BETRAGSZEILE.search(zeile):
            gefunden = _BETRAG.search(zeile)
            if gefunden:
                betrag_der_mail = gefunden.group(0).strip()
                break
    ergebnis: list[FristVorschlag] = []
    for satz in _saetze(text):
        art = 'kuendigung' if _KUENDIGUNG.search(satz) else 'zahlung' if _ZAHLUNG.search(satz) else ''
        if not art or _ERLEDIGT.search(satz):
            continue
        for frist in fristen_in(satz, bezug).fristen:
            # Nur ein ausgeschriebenes Datum, und nur, was noch kommt: Eine verstrichene Frist ist keine Aufgabe mehr.
            if frist.art != 'datum' or not _AUSGESCHRIEBEN.search(frist.ausdruck) or frist.datum < heute:
                continue
            betrag = ''
            if art == 'zahlung':
                im_satz = _BETRAG.search(satz)
                betrag = im_satz.group(0).strip() if im_satz else betrag_der_mail
            vorschlag = FristVorschlag(art, frist.datum, frist.ausdruck.rstrip('.,;'), satz, betrag)
            if all((v.art, v.datum) != (vorschlag.art, vorschlag.datum) for v in ergebnis):
                ergebnis.append(vorschlag)
    return ergebnis


def zahlen_belegt(aussage: str, quelle: str) -> list[str]:
    """Die Zahlen einer Aussage, die in der Quelle **nicht** stehen (leer heißt: jede Zahl ist belegt)."""
    roh = re.sub(r'\s+', ' ', quelle)
    return [z for z in re.findall(r'\d+(?:[.,]\d+)*', aussage) if z not in roh]


# -- Ablage: was ein Mensch bestätigt hat ---------------------------------------------


class ArtAblage:
    """Die bestätigten Arten der Akten. Schreibt nur auf ausdrücklichen Wunsch (`bestaetigen`, `zuruecknehmen`)."""

    def __init__(self, episodes: Any) -> None:
        self.episodes = episodes

    def bestaetigt(self, sache: str) -> dict[str, Any] | None:
        with self.episodes._lock:
            zeile = self.episodes._conn.execute(
                'SELECT art, vorschlag, bestaetigt_am FROM akten_arten WHERE sache = ?', (sache,)).fetchone()
        return dict(zeile) if zeile else None

    def alle(self) -> dict[str, str]:
        with self.episodes._lock:
            return {z['sache']: z['art'] for z in self.episodes._conn.execute('SELECT sache, art FROM akten_arten')}

    def bestaetigen(self, sache: str, art: str, vorschlag: str = '') -> dict[str, Any]:
        if art not in WAHLEN:
            raise ValueError('Unbekannte Art.')
        with self.episodes.transaction():
            self.episodes._conn.execute(
                'INSERT INTO akten_arten VALUES (?,?,?,?) ON CONFLICT(sache) DO UPDATE SET art=excluded.art, '
                'vorschlag=excluded.vorschlag, bestaetigt_am=excluded.bestaetigt_am',
                (sache, art, vorschlag if vorschlag in ARTEN else '', time.time()))
        return self.bestaetigt(sache) or {}

    def zuruecknehmen(self, sache: str) -> bool:
        with self.episodes.transaction():
            return self.episodes._conn.execute('DELETE FROM akten_arten WHERE sache = ?', (sache,)).rowcount > 0


# -- Lesen aus dem Bestand -----------------------------------------------------------

#: So viele der jüngsten Quellen einer Akte gehen in den Vorschlag ein.
QUELLEN_JE_AKTE = 40


def _absender_der_akte(bezuege: Any, sache: str, quellen: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(Absender, Betreffe): Anzeigenamen und Domänen der Absender, zuletzt die Kennung der Akte; Betreffe der Quellen.

    Die lesbare Form steht vorn, damit die Begründung „Absender „Zahnarztpraxis Dr. Krämer““ sagt und nicht die Kennung.
    """
    from .bezuege import zerlegen
    from .identitaet import domaene, nennungen
    art, kennung = zerlegen(sache) or ('', '')
    namen: list[str] = []
    domaenen: list[str] = []
    betreffe: list[str] = []
    for quelle in quellen[:QUELLEN_JE_AKTE]:
        try:
            episode = bezuege.episodes.get(quelle['episode_id'])
        except Exception:  # noqa: BLE001 - eine unlesbare Quelle fehlt nur im Vorschlag
            continue
        if 'anhang' in (episode.tags or ()):
            continue   # ein Anhang trägt Betreff und Absender seiner Mail; doppelt zählt nichts
        betreffe.append(episode.title)
        for nennung in nennungen(episode):
            if nennung.rolle in ('von', 'beteiligt') and nennung.adresse and not nennung.ich:
                name, ort = nennung.name.strip(), domaene(nennung.adresse).rsplit('.', 1)[0]
                if name and name not in namen:
                    namen.append(name)
                if ort and ort not in domaenen:
                    domaenen.append(ort)
    return [*namen, *domaenen, *([kennung] if art == 'organisation' else [])], betreffe


def name_der_akte(bezuege: Any, sache: str, quellen: list[dict[str, Any]]) -> str:
    """Wie der Absender sich selbst nennt („Zahnarztpraxis Dr. Krämer“), sonst der Name der Akte („Grundschule
    Sonnenberg“). Ein Personenname („Susanne Albers“) nennt die Akte nicht: Gezeigt wird der Name, der die Art trägt."""
    from .identitaet import nennungen
    for quelle in quellen[:QUELLEN_JE_AKTE]:
        try:
            episode = bezuege.episodes.get(quelle['episode_id'])
        except Exception:  # noqa: BLE001
            continue
        for nennung in nennungen(episode):
            name = nennung.name.strip()
            if (nennung.rolle == 'von' and nennung.adresse and not nennung.ich and name
                    and any(muster.search(normal(name)) for muster in ABSENDER.values())):
                return name
    return bezuege.beschriftung(sache, quellen=quellen)


def vorschlag_fuer(bezuege: Any, sache: str, quellen: list[dict[str, Any]] | None = None) -> ArtVorschlag:
    """Der Vorschlag für die Akte einer Organisation; andere Sachen bekommen keinen."""
    if not sache.startswith('organisation:'):
        return KEIN_VORSCHLAG
    quellen = quellen if quellen is not None else bezuege.quellen_von(sache)
    absender, betreffe = _absender_der_akte(bezuege, sache, quellen)
    return vorschlagen(absender, betreffe)


def stand(bezuege: Any, sache: str, quellen: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Was die Karte „Art der Akte“ zeigt: bestätigte Art, Vorschlag mit Begründung, ob er abweicht."""
    vorschlag = vorschlag_fuer(bezuege, sache, quellen)
    fest = ArtAblage(bezuege.episodes).bestaetigt(sache)
    art = fest['art'] if fest else None
    return {'sache': sache, 'art': art, 'art_text': ART_TEXT.get(art or '', ''), 'bestaetigt': fest is not None,
            'vorschlag': vorschlag.als_dict(), 'wahlen': [{'art': a, 'text': ART_TEXT[a]} for a in WAHLEN],
            'neuer_vorschlag': bool(fest and vorschlag.art and vorschlag.art != art)}


def private_art(bezuege: Any, sache: str, quellen: list[dict[str, Any]] | None = None) -> str:
    """Die geltende private Art einer Akte: bestätigt, sonst vorgeschlagen; leer, wenn keine (oder „Keine davon“)."""
    fest = ArtAblage(bezuege.episodes).bestaetigt(sache)
    if fest is not None:
        return fest['art'] if fest['art'] in ARTEN else ''
    return vorschlag_fuer(bezuege, sache, quellen).art


def private_kandidaten(bezuege: Any) -> list[str]:
    """Organisationen, die eine private Art haben können: ein Absender, dessen Name oder Domäne ein privates Muster
    trifft (`ABSENDER`), oder eine von einem Menschen bestätigte private Art. Ein Durchgang über die Absender, kein
    Lesen jeder Akte: Mit vielen Organisationen (10.000 Quellen und mehr) blieben sonst Akten jenseits der ersten
    paar hundert ungesehen.
    """
    from .bezuege import org_aus_adresse, sache_id
    from .identitaet import domaene
    with bezuege.episodes._lock:
        zeilen = bezuege.episodes._conn.execute(
            "SELECT DISTINCT json_extract(c.value, '$.adresse') AS adresse, json_extract(c.value, '$.name') AS name "
            "FROM episodes e, json_each(e.document, '$.contacts') c "
            "WHERE json_extract(c.value, '$.rolle') IN ('von', 'beteiligt') AND json_extract(c.value, '$.adresse') != ''"
        ).fetchall()
    kandidaten: set[str] = set()
    for zeile in zeilen:
        adresse = str(zeile['adresse'] or '')
        kennung = org_aus_adresse(adresse)
        if not kennung:
            continue
        texte = (normal(zeile['name']), normal(domaene(adresse).rsplit('.', 1)[0]), normal(kennung))
        if any(muster.search(text) for muster in ABSENDER.values() for text in texte if text):
            kandidaten.add(sache_id('organisation', kennung))
    try:
        kandidaten.update(s for s, art in ArtAblage(bezuege.episodes).alle().items()
                          if art in ARTEN and s.startswith('organisation:'))
    except Exception:  # noqa: BLE001 - ohne Ablage (alter Speicher) nur die Muster
        pass
    return sorted(kandidaten)


# -- Fristen als Aufgabenvorschläge ----------------------------------------------------

VORGESCHLAGEN_VON = 'privat-fristen:'


@dataclass
class FristenLauf:
    akten: int = 0
    quellen: int = 0
    vorgeschlagen: int = 0
    vorhanden: int = 0
    vorschlaege: list[dict[str, Any]] = field(default_factory=list)


def _faelligkeit(datum: date) -> datetime:
    from .model import user_timezone
    from datetime import timezone
    return datetime.combine(datum, uhrzeit(12, 0), tzinfo=user_timezone() or timezone.utc)


def fristen_vorlegen(bezuege: Any, proposals: Any, *, max_akten: int = 2000) -> FristenLauf:
    """Legt für Kündigungs- und Zahlungsfristen aus Akten mit privater Art Aufgabenvorschläge an.

    Ein Vorschlag je Quelle, Art und Datum; was schon einmal vorgeschlagen war (offen, angenommen oder abgelehnt),
    kommt nicht wieder. Schreibt nur Vorschläge, nie eine Aufgabe.
    """
    from .anhaenge import ist_anhang, seite_der_stelle
    from .proposals import Evidence, ProposalKind
    lauf = FristenLauf()
    for sache in private_kandidaten(bezuege)[:max_akten]:
        quellen = bezuege.quellen_von(sache)
        art = private_art(bezuege, sache, quellen)
        if not art:
            continue
        lauf.akten += 1
        wer = name_der_akte(bezuege, sache, quellen)
        # Dieselbe Frist in der Mail und in ihrem Anhang ist eine Aufgabe, nicht zwei.
        in_der_akte: set[tuple[str, date, str]] = set()
        for quelle in quellen[:QUELLEN_JE_AKTE]:
            if quelle.get('art') not in ('message', 'document'):
                continue
            try:
                episode = bezuege.episodes.get(quelle['episode_id'])
            except Exception:  # noqa: BLE001
                continue
            if quelle['art'] == 'document' and not ist_anhang(episode):
                continue   # Dokumente aus Ordnern tragen keinen Absender; Fristen nur aus Mails und ihren Anhängen
            lauf.quellen += 1
            schon = {(p.evidence[0].quote if p.evidence else '', p.valid_until.date() if p.valid_until else None)
                     for p in proposals.von(VORGESCHLAGEN_VON + episode.id, limit=50)}
            for frist in fristen_finden(episode.body, episode.reference_time()):
                if frist.satz not in episode.body or zahlen_belegt(frist.aussage(''), episode.body):
                    continue
                gleich = (frist.art, frist.datum, frist.betrag)
                if (frist.satz, frist.datum) in schon or gleich in in_der_akte:
                    in_der_akte.add(gleich)
                    lauf.vorhanden += 1
                    continue
                in_der_akte.add(gleich)
                if ist_anhang(episode):
                    seite = seite_der_stelle(episode.body, frist.satz)
                    herkunft = (f'Aus dem Anhang „{episode.title.split(" (Anhang zu ")[0]}“'
                                + (f', Seite {seite},' if seite else '') + f' einer Mail der Akte „{wer}“')
                else:
                    herkunft = f'Aus einer Mail der Akte „{wer}“'
                vorschlag, neu = proposals.propose(
                    ProposalKind.TASK, frist.aussage(wer),
                    f'{herkunft} ({ART_TEXT[art]}). Datum und Betrag stehen so in der Quelle. '
                    'Erst deine Bestätigung macht daraus eine Aufgabe.',
                    evidence=[Evidence(episode.id, frist.satz, episode.digest)],
                    proposed_by=VORGESCHLAGEN_VON + episode.id, valid_until=_faelligkeit(frist.datum))
                if neu:
                    lauf.vorgeschlagen += 1
                    lauf.vorschlaege.append({'id': vorschlag.id, 'episode_id': episode.id, 'art': frist.art,
                                             'datum': frist.datum.isoformat(), 'betrag': frist.betrag})
                else:
                    lauf.vorhanden += 1
    return lauf


__all__ = ['ARTEN', 'ART_TEXT', 'ArtAblage', 'ArtVorschlag', 'FristVorschlag', 'KEINE', 'WAHLEN', 'fristen_finden',
           'fristen_vorlegen', 'normal', 'private_art', 'stand', 'vorschlag_fuer', 'vorschlagen', 'zahlen_belegt']
