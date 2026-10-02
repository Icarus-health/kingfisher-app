"""Kreis je Person (M4): innerer Kreis, Kollegen, Kontakte. Vorschlag mit Begründung, Bestätigung durch einen Menschen.

Kingfisher führt Akten über andere Menschen, auch über Familie. Wie viel er über jemanden sagt und wie zurückhaltend,
hängt davon ab, wer die Person für den Nutzer ist. Das kann ein Programm nicht wissen, nur vermuten. Deshalb:

* **Vorschlag aus dem Austausch, ohne Modell.** `vorschlagen` liest feste Merkmale (`Merkmale`): wie viele Mails in
  welche Richtung, über wie viele Monate, privater oder Firmenanbieter (`identitaet.ist_privater_anbieter`), dieselbe
  Firma wie der Nutzer, gemeinsame Termine, Anrede und Gruß (Du und Vorname, familiäre Anrede, Sie), und ob die
  Adresse zu einer Praxis, Versicherung oder Schule gehört (`akten_arten.py`). Die Begründung ist ein Satz:
  „34 Mails in beide Richtungen seit März 2026, privater Anbieter, zwei gemeinsame Termine, Anrede „Mama“.“
* **Fakt erst nach Bestätigung** (`docs/10-verdichtung.md`). Ein Vorschlag wirkt nirgends. Erst `Kreise.bestaetigen`
  (ein Klick in der Akte) legt den Kreis fest; ohne Bestätigung ist er `unbestimmt`, und alles bleibt, wie es war.
* **Nie automatisch geändert.** Ein bestätigter Kreis bleibt, bis ein Mensch ihn ändert. Ändert sich die Lage, zeigt
  die Akte den neuen Vorschlag daneben (`neuer_vorschlag`), mehr nicht.
* **Lieber zu weit draußen als zu weit drinnen.** Der innere Kreis verlangt Austausch in beide Richtungen über
  mindestens zwei Monate und eine persönliche Anrede. Ein Fremder, der „Hallo Mama, das ist meine neue Nummer“
  schreibt, bleibt Kontakt.

Was der Kreis bewirkt (nur Sortierung und Formulierung, nichts verlässt den Rechner), steht in `wirkung` und
`docs/49-kreis-und-privat.md`.
"""
from __future__ import annotations

import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Iterable

INNERER_KREIS, KOLLEGEN, KONTAKTE, UNBESTIMMT = 'innerer_kreis', 'kollegen', 'kontakte', 'unbestimmt'
KREISE = (INNERER_KREIS, KOLLEGEN, KONTAKTE)
KREIS_TEXT = {INNERER_KREIS: 'Innerer Kreis', KOLLEGEN: 'Kollegen', KONTAKTE: 'Kontakte', UNBESTIMMT: 'Noch offen'}
#: Was die Wahl bewirkt, in einem Satz (für die Karte in der Akte).
WIRKUNG = {
    INNERER_KREIS: 'Familie und enge Freunde: Kingfisher nennt sie mit Namen und denkt an ihren Alltag.',
    KOLLEGEN: 'Menschen aus der Arbeit: sachlich und mit Bezug zum Projekt.',
    KONTAKTE: 'Alle anderen: Kingfisher erwähnt sie nur, wenn es direkt um sie geht.',
}

TABLES = {'personen_kreis': {'sache', 'kreis', 'vorschlag', 'bestaetigt_am'}}
PRIMARY_KEYS = {'personen_kreis': {'sache'}}


def migrate(connection: sqlite3.Connection) -> None:
    """Teil der Migration 16: der bestätigte Kreis je Person (nur, was ein Mensch gewählt hat)."""
    connection.execute("""CREATE TABLE personen_kreis (
        sache TEXT PRIMARY KEY,
        kreis TEXT NOT NULL CHECK(kreis IN ('innerer_kreis','kollegen','kontakte')),
        vorschlag TEXT NOT NULL DEFAULT '', bestaetigt_am REAL NOT NULL)""")


# -- Merkmale --------------------------------------------------------------------

#: Schwellen des inneren Kreises: so viele Mails insgesamt, über so viele verschiedene Monate.
INNEN_MAILS = 4
INNEN_MONATE = 2
#: Kollegen: so viele Mails in beide Richtungen (oder ein gemeinsamer Termin).
KOLLEGEN_MAILS = 3
#: So viele der jüngsten Mails zwischen beiden werden auf Anrede und Gruß gelesen.
GELESENE_MAILS = 12

_DU = re.compile(r'(?<![\wäöüß])(?:du|dich|dir|dein|deine|deinen|deinem|deiner|euch|euer|eure)(?![\wäöüß])', re.I)
_SIE = re.compile(r'(?<![\wäöüß])(?:Sie|Ihnen|Ihre|Ihren|Ihrem|Ihrer)(?![\wäöüß])'
                  r'|(?i:sehr geehrte|mit freundlichen grüßen)')
_VORNAME = re.compile(r'^[ \t]*(?i:hallo|hi|hey|liebe|lieber|moin|servus|huhu)[ \t]+'
                      r'(?!(?i:frau|herr|dr|prof|eltern|kolleg\w*|kund\w*|damen|team|mitglied\w*|nachbar\w*|alle|zusammen)\b)'
                      r'[A-ZÄÖÜ][a-zäöüß]+[ \t]*[,!]?', re.M)
#: Familiäre Anrede („Hallo Mama“, „Deine Mama“) und familiärer Gruß („Hab dich lieb“). Die Anrede wiegt mehr und
#: steht zuerst in der Begründung; ein Gruß allein gilt auch.
_ANREDE = re.compile(r'(?<![\wäöüß])(?:mama|mami|mutti|papa|papi|vati|oma|omi|opa|opi|schatz|liebling|schwesterherz|'
                     r'bruderherz)(?![\wäöüß])', re.I)
_GRUSS = re.compile(r'(?<![\wäöüß])(?:hab dich lieb|küsschen|kuss|bussi|drück dich|dein bruder|deine schwester|'
                    r'deine tochter|dein sohn|deine tante|dein onkel)(?![\wäöüß])', re.I)
#: Zitierte frühere Mail: ab hier zählt der Text nicht mehr zu dieser Mail.
_ZITAT = re.compile(r'^(?:>|Am .{4,80} schrieb|-{3,}\s*(?:Ursprüngliche|Original)|Von:\s)', re.M)
_ZAHLWORT = {1: 'ein', 2: 'zwei', 3: 'drei', 4: 'vier', 5: 'fünf', 6: 'sechs', 7: 'sieben', 8: 'acht', 9: 'neun',
             10: 'zehn', 11: 'elf', 12: 'zwölf'}


@dataclass(frozen=True)
class Merkmale:
    """Was Kingfisher über den Austausch mit einer Person weiß; nur Zahlen und Kennzeichen, kein Text außer der Anrede."""

    adresse: str
    von_ihr: int = 0
    """Mails, die die Person geschrieben hat."""
    von_dir: int = 0
    """Mails des Nutzers, in denen sie in An oder Cc steht."""
    seit: str = ''
    """Tag der ersten Mail im Austausch (ISO), leer ohne Mail."""
    monate: int = 0
    """Verschiedene Kalendermonate mit Mails."""
    termine: int = 0
    privat: bool = False
    eigene_firma: bool = False
    dienst: str = ''
    """Private Akten-Art der Organisation hinter der Adresse (Praxis, Versicherung, Schule …), sonst leer."""
    du: bool = False
    vorname: bool = False
    sie: bool = False
    familiaer: str = ''
    """Die familiäre Anrede, wörtlich („Mama“), sonst ein familiärer Gruß („Hab dich lieb“), sonst leer."""

    @property
    def mails(self) -> int:
        return self.von_ihr + self.von_dir

    @property
    def beide_richtungen(self) -> bool:
        return self.von_ihr > 0 and self.von_dir > 0

    def als_dict(self) -> dict[str, Any]:
        return {**asdict(self), 'mails': self.mails, 'beide_richtungen': self.beide_richtungen}


@dataclass(frozen=True)
class Vorschlag:
    kreis: str
    begruendung: str
    merkmale: Merkmale = field(compare=False, default=None)  # type: ignore[assignment]

    def als_dict(self) -> dict[str, Any]:
        return {'kreis': self.kreis, 'kreis_text': KREIS_TEXT[self.kreis], 'begruendung': self.begruendung,
                'merkmale': self.merkmale.als_dict() if self.merkmale else None}


def vorschlagen(m: Merkmale) -> Vorschlag:
    """Der Kreis aus den Merkmalen, mit Begründung. Rein und deterministisch.

    * **Innerer Kreis:** Mails in beide Richtungen, mindestens `INNEN_MAILS` über mindestens `INNEN_MONATE` Monate,
      nicht die eigene Firma, keine Praxis oder Versicherung, und eine familiäre Anrede oder Du mit Vornamen bei
      privatem Anbieter. Du und Vorname bei einer Firmenadresse reichen nicht: Unter Kollegen ist das üblich.
    * **Kollegen:** Mails in beide Richtungen, keine Praxis oder Versicherung, und dieselbe Firma wie der Nutzer oder
      eine Firmenadresse mit mindestens `KOLLEGEN_MAILS` Mails oder einem gemeinsamen Termin.
    * **Kontakte:** alle anderen.
    """
    # Du und Vorname allein sagen wenig: Unter Kollegen ist das üblich. Erst mit privatem Anbieter wird es persönlich.
    persoenlich = bool(m.familiaer) or (m.du and m.vorname and m.privat)
    if (m.beide_richtungen and m.mails >= INNEN_MAILS and m.monate >= INNEN_MONATE and not m.eigene_firma
            and not m.dienst and persoenlich):
        kreis = INNERER_KREIS
    elif m.beide_richtungen and not m.dienst and (
            m.eigene_firma or (not m.privat and (m.mails >= KOLLEGEN_MAILS or m.termine > 0))):
        kreis = KOLLEGEN
    else:
        kreis = KONTAKTE
    return Vorschlag(kreis, begruendung(m), m)


def _monat(iso: str) -> str:
    from .datumstext import MONATE
    try:
        tag = date.fromisoformat(iso[:10])
    except ValueError:
        return ''
    return f'{MONATE[tag.month - 1]} {tag.year}'


def _anzahl(zahl: int, einzahl: str, mehrzahl: str) -> str:
    if zahl == 1:
        return f'ein{"e" if einzahl.endswith("Mail") else ""} {einzahl}'
    return f'{_ZAHLWORT.get(zahl, str(zahl))} {mehrzahl}' if zahl <= 12 else f'{zahl} {mehrzahl}'


def begruendung(m: Merkmale) -> str:
    """Ein Satz aus den Merkmalen, in Alltagssprache. Nennt nur, was zutrifft."""
    from .akten_arten import ART_TEXT
    teile: list[str] = []
    seit = f' seit {_monat(m.seit)}' if m.seit and _monat(m.seit) else ''
    if m.beide_richtungen:
        teile.append(f'{m.mails} Mails in beide Richtungen{seit}')
    elif m.von_ihr:
        teile.append(f'{_anzahl(m.von_ihr, "Mail", "Mails")} an dich, keine Antwort von dir')
    elif m.von_dir:
        teile.append(f'{_anzahl(m.von_dir, "Mail", "Mails")} von dir, keine Antwort')
    else:
        teile.append('kein Mailwechsel')
    if m.eigene_firma:
        teile.append('dieselbe Firma wie du')
    elif m.privat:
        teile.append('privater Anbieter')
    elif m.adresse:
        teile.append('Firmenadresse')
    if m.termine:
        teile.append(_anzahl(m.termine, 'gemeinsamer Termin', 'gemeinsame Termine'))
    if m.familiaer:
        teile.append(f'{"Gruß" if _GRUSS.fullmatch(m.familiaer) else "Anrede"} „{m.familiaer}“')
    elif m.du and m.vorname:
        teile.append('per Du und mit Vornamen')
    elif m.du:
        teile.append('per Du')
    elif m.sie:
        teile.append('per Sie')
    if m.dienst:
        teile.append(f'Absender aus dem Bereich {ART_TEXT.get(m.dienst, m.dienst)}')
    satz = ', '.join(teile)
    return satz[:1].upper() + satz[1:] + '.'


def anrede(texte: Iterable[str]) -> dict[str, Any]:
    """Du, Vorname, Sie und familiäre Anrede in Mails zwischen beiden. Rein; zitierte frühere Mails zählen nicht."""
    du = sie = vorname = 0
    anrede_, gruss = '', ''
    for text in texte:
        eigen = _ZITAT.split(text, maxsplit=1)[0] if _ZITAT.search(text) else text
        du += bool(_DU.search(eigen))
        sie += bool(_SIE.search(eigen))
        vorname += bool(_VORNAME.search(eigen))
        # Familiär ist nur eine Anrede oder ein Gruß: der Anfang der ersten Zeile bis zum Komma und kurze
        # Schlusszeilen („Hab dich lieb“, „Deine Mama“). „Grillen bei Mama und Papa“ mitten im Text ist keine Anrede.
        zeilen = [z.strip() for z in eigen.splitlines() if z.strip()]
        anfang = re.split(r'[,!.?]', zeilen[0])[0] if zeilen else ''
        rahmen = '\n'.join([anfang, *(z for z in zeilen[1:][-3:] if len(z) <= 40)])
        if not anrede_ and (treffer := _ANREDE.search(rahmen)):
            anrede_ = treffer.group(0)
        if not gruss and (treffer := _GRUSS.search(rahmen)):
            gruss = treffer.group(0)
    return {'du': du > 0 and du >= sie, 'vorname': vorname > 0, 'sie': sie > du, 'familiaer': anrede_ or gruss}


# -- Lesen aus dem Bestand ---------------------------------------------------------

_ABSENDER_SQL = ("(SELECT json_extract(c.value, '$.adresse') FROM json_each(e.document, '$.contacts') c "
                 "WHERE json_extract(c.value, '$.rolle') = 'von' LIMIT 1)")
#: Hat der Nutzer die Mail geschrieben? Die Aufnahme kennzeichnet eigene Adressen mit `ich` (`kontakte.py`).
_ICH_SQL = ("EXISTS (SELECT 1 FROM json_each(e.document, '$.contacts') c WHERE json_extract(c.value, '$.rolle') = 'von' "
            "AND json_extract(c.value, '$.ich'))")


def _zeilen(bezuege: Any, sache: str | None) -> list[Any]:
    """Je Quelle mit Adressbezug einer Person: Sache, Quelle, Art, Zeit, Rolle der Person, Absender der Quelle."""
    from .bezuege import FINGERABDRUCK, GUELTIG, GUELTIG_PARAMS
    bedingung = 'b.sache = ?' if sache else "b.sache LIKE 'person:a:%'"
    abgelehnt = ("NOT EXISTS (SELECT 1 FROM sach_nutzer u WHERE u.episode_id = b.episode_id AND u.sache = b.sache "
                 "AND u.aktion = 'nicht' AND u.fingerprint = " + FINGERABDRUCK + ")")
    with bezuege.episodes._lock:
        return bezuege.episodes._conn.execute(
            "SELECT b.sache AS sache, e.id AS id, e.kind AS kind, COALESCE(e.occurred_at, e.recorded_at) AS zeit, "
            "b.rolle AS rolle, " + _ABSENDER_SQL + " AS absender, " + _ICH_SQL + " AS ich "
            "FROM sach_bezuege b JOIN episodes e ON e.id = b.episode_id "
            "WHERE " + bedingung + " AND b.grundlage = 'anker' AND " + GUELTIG + " AND " + abgelehnt,
            ((sache,) if sache else ()) + GUELTIG_PARAMS).fetchall()


@dataclass
class _Zaehler:
    von_ihr: set = field(default_factory=set)
    von_dir: set = field(default_factory=set)
    termine: set = field(default_factory=set)
    zeiten: dict = field(default_factory=dict)


def _zaehlen(zeilen: Iterable[Any], eigene: set[str]) -> dict[str, _Zaehler]:
    ergebnis: dict[str, _Zaehler] = {}
    for z in zeilen:
        zaehler = ergebnis.setdefault(z['sache'], _Zaehler())
        if z['kind'] == 'event':
            zaehler.termine.add(z['id'])
        elif z['kind'] == 'message':
            absender = str(z['absender'] or '').casefold()
            if z['rolle'] == 'von':
                zaehler.von_ihr.add(z['id'])
            elif z['rolle'] in ('an', 'cc') and (absender in eigene or z['ich']):
                zaehler.von_dir.add(z['id'])
            else:
                continue
            zaehler.zeiten[z['id']] = str(z['zeit'] or '')
    return ergebnis


class SammelVeraltet(Exception):
    """Seit der Rückfrage hat sich die Zahl der offenen Vorschläge geändert; es wurde nichts gespeichert."""

    def __init__(self, jetzt: int) -> None:
        super().__init__(f'Inzwischen sind es {jetzt} Vorschläge. Bitte noch einmal ansehen; gespeichert ist nichts.')
        self.jetzt = jetzt


class Kreise:
    """Vorschläge und bestätigte Kreise. Schreibt nur auf ausdrücklichen Wunsch (`bestaetigen`, `zuruecknehmen`)."""

    def __init__(self, bezuege: Any, eigene: Iterable[str] = ()) -> None:
        self.bezuege = bezuege
        self.episodes = bezuege.episodes
        self.eigene = {a.casefold() for a in eigene if a}
        self._dienste: dict[str, str] = {}

    # -- Ablage --

    def bestaetigt(self, sache: str) -> dict[str, Any] | None:
        with self.episodes._lock:
            zeile = self.episodes._conn.execute(
                'SELECT kreis, vorschlag, bestaetigt_am FROM personen_kreis WHERE sache = ?', (sache,)).fetchone()
        return dict(zeile) if zeile else None

    def alle(self) -> dict[str, str]:
        """Sache -> bestätigter Kreis, für alle bestätigten Personen."""
        return alle_bestaetigten(self.episodes)

    def bestaetigen(self, sache: str, kreis: str) -> dict[str, Any]:
        """Legt den Kreis fest (der Klick eines Menschen). Merkt sich, was Kingfisher in dem Moment vorschlug."""
        if kreis not in KREISE:
            raise ValueError('Unbekannter Kreis.')
        if not sache.startswith('person:'):
            raise ValueError('Einen Kreis haben nur Personen.')
        vorschlag = self.vorschlag(sache).kreis
        with self.episodes.transaction():
            self.episodes._conn.execute(
                'INSERT INTO personen_kreis VALUES (?,?,?,?) ON CONFLICT(sache) DO UPDATE SET kreis=excluded.kreis, '
                'vorschlag=excluded.vorschlag, bestaetigt_am=excluded.bestaetigt_am', (sache, kreis, vorschlag, time.time()))
        return self.stand(sache)

    def zuruecknehmen(self, sache: str) -> bool:
        with self.episodes.transaction():
            return self.episodes._conn.execute('DELETE FROM personen_kreis WHERE sache = ?', (sache,)).rowcount > 0

    # -- Sammelbestätigung (nur Kollegen) --

    def offene_kollegen(self) -> list[str]:
        """Alle Personen, für die „Kollegen“ vorgeschlagen und noch nichts bestätigt ist."""
        fest = self.alle()
        return sorted(s for s, v in self.vorschlaege().items() if v.kreis == KOLLEGEN and s not in fest)

    def sammel_bestaetigen(self, kreis: str, anzahl: int) -> dict[str, Any]:
        """Bestätigt alle offenen Vorschläge „Kollegen“ mit einem Klick. Nie für den inneren Kreis.

        `anzahl` ist die Zahl, die der Mensch in der Rückfrage las („21 Personen als Kollegen festlegen?“). Stimmt sie
        nicht mehr, wird nichts gespeichert (`SammelVeraltet`). Alle Zeilen tragen denselben Zeitpunkt; er ist die
        Kennung der Sammlung, mit der `sammlung_zuruecknehmen` genau diese Liste wieder offen lässt.
        """
        if kreis != KOLLEGEN:
            raise ValueError('Gesammelt bestätigt Kingfisher nur Kollegen. Den inneren Kreis bestätigst du je Person.')
        offen = self.offene_kollegen()
        if len(offen) != anzahl:
            raise SammelVeraltet(len(offen))
        if not offen:
            return {'sammlung': None, 'anzahl': 0}
        vorschlaege = self.vorschlaege()
        moment = time.time()
        with self.episodes.transaction():
            self.episodes._conn.executemany(
                'INSERT INTO personen_kreis VALUES (?,?,?,?) ON CONFLICT(sache) DO NOTHING',
                [(sache, KOLLEGEN, vorschlaege[sache].kreis, moment) for sache in offen])
        return {'sammlung': moment, 'anzahl': len(offen)}

    def letzte_sammlung(self) -> dict[str, Any] | None:
        """Die jüngste Sammelbestätigung, die noch steht (mehr als eine Person, gleicher Zeitpunkt, Kollegen)."""
        with self.episodes._lock:
            zeile = self.episodes._conn.execute(
                "SELECT bestaetigt_am, COUNT(*) AS n FROM personen_kreis WHERE kreis = 'kollegen' GROUP BY bestaetigt_am "
                'HAVING n > 1 ORDER BY bestaetigt_am DESC LIMIT 1').fetchone()
        return {'sammlung': zeile['bestaetigt_am'], 'anzahl': zeile['n']} if zeile else None

    def sammlung_zuruecknehmen(self, sammlung: float) -> int:
        """Lässt genau die Personen einer Sammlung wieder offen, die seitdem niemand einzeln geändert hat."""
        with self.episodes.transaction():
            return self.episodes._conn.execute(
                "DELETE FROM personen_kreis WHERE kreis = 'kollegen' AND bestaetigt_am = ?", (sammlung,)).rowcount

    # -- Vorschlag --

    def _dienst(self, adresse: str) -> str:
        """Private Akten-Art der Organisation hinter der Adresse (Praxis, Versicherung, Schule), sonst leer."""
        from .akten_arten import private_art
        from .bezuege import org_aus_adresse, sache_id
        kennung = org_aus_adresse(adresse, self._eigene_domaenen())
        if not kennung:
            return ''
        if kennung not in self._dienste:
            try:
                self._dienste[kennung] = private_art(self.bezuege, sache_id('organisation', kennung))
            except Exception:  # noqa: BLE001 - ohne Akte der Organisation bleibt der Dienst unbekannt
                self._dienste[kennung] = ''
        return self._dienste[kennung]

    def _eigene_domaenen(self) -> set[str]:
        from .identitaet import domaene
        return {domaene(a) for a in self.eigene if domaene(a)}

    def merkmale(self, sache: str, zaehler: _Zaehler | None = None, *, texte_lesen: bool = True) -> Merkmale:
        """Die Merkmale einer Person. `texte_lesen=False` spart Anrede und Dienst (nur Zahlen): für Personen, die ohnehin
        Kontakte bleiben, weil der Austausch nur in eine Richtung lief."""
        from .identitaet import domaene, ist_privater_anbieter
        adresse = sache[len('person:a:'):] if sache.startswith('person:a:') else ''
        if zaehler is None:
            zaehler = _zaehlen(_zeilen(self.bezuege, sache), self.eigene).get(sache, _Zaehler())
        zeiten = sorted(t for t in zaehler.zeiten.values() if t)
        monate = len({t[:7] for t in zeiten})
        privat = bool(adresse) and ist_privater_anbieter(adresse)
        eigene_firma = bool(adresse) and not privat and domaene(adresse).casefold() in self._eigene_domaenen()
        gruss = {'du': False, 'vorname': False, 'sie': False, 'familiaer': ''}
        if texte_lesen and zaehler.zeiten:
            neueste = sorted(zaehler.zeiten, key=lambda i: (zaehler.zeiten[i], i), reverse=True)[:GELESENE_MAILS]
            gruss = anrede(self._texte(neueste))
        return Merkmale(adresse, len(zaehler.von_ihr), len(zaehler.von_dir), zeiten[0][:10] if zeiten else '', monate,
                        len(zaehler.termine), privat, eigene_firma,
                        self._dienst(adresse) if adresse and texte_lesen else '',
                        gruss['du'], gruss['vorname'], gruss['sie'], gruss['familiaer'])

    def _texte(self, ids: list[str]) -> list[str]:
        """Die Texte in der Reihenfolge von `ids` (jüngste zuerst): Dieselbe Lage gibt dieselbe Begründung."""
        if not ids:
            return []
        with self.episodes._lock:
            zeilen = self.episodes._conn.execute(
                f"SELECT id, body FROM episodes WHERE id IN ({','.join('?' for _ in ids)})", ids).fetchall()
        texte = {z['id']: z['body'] for z in zeilen}
        return [texte[i] for i in ids if i in texte]

    def vorschlag(self, sache: str) -> Vorschlag:
        return vorschlagen(self.merkmale(sache))

    def stand(self, sache: str) -> dict[str, Any]:
        """Was die Karte „Kreis“ zeigt: bestätigter Kreis, Vorschlag mit Begründung, die drei Wahlen."""
        vorschlag = self.vorschlag(sache)
        fest = self.bestaetigt(sache)
        kreis = fest['kreis'] if fest else UNBESTIMMT
        # Ohne Mails und gemeinsame Termine gibt es nichts, worauf ein Vorschlag beruhen könnte (etwa eine Person, die
        # nur in Notizen oder im Gespräch vorkommt). Dann schlägt Kingfisher nichts vor; der Mensch legt den Kreis
        # selbst fest, mit denselben drei Knöpfen (Fremdprobe 2, Befund 19).
        ohne = not (vorschlag.merkmale and (vorschlag.merkmale.mails or vorschlag.merkmale.termine))
        return {'sache': sache, 'kreis': kreis, 'kreis_text': KREIS_TEXT[kreis], 'bestaetigt': fest is not None,
                'bestaetigt_am': fest['bestaetigt_am'] if fest else None, 'vorschlag': vorschlag.als_dict(),
                'ohne_vorschlag': ohne,
                'neuer_vorschlag': bool(fest and not ohne and vorschlag.kreis != fest['kreis']),
                'wahlen': [{'kreis': k, 'text': KREIS_TEXT[k], 'wirkung': WIRKUNG[k]} for k in KREISE]}

    def vorschlaege(self) -> dict[str, Vorschlag]:
        """Vorschläge für alle Personen mit Adresse. Texte liest nur, wer die Zahlen für mehr als „Kontakte“ hat:
        Austausch in beide Richtungen mit mindestens `KOLLEGEN_MAILS` Mails oder einem gemeinsamen Termin."""
        zaehler = _zaehlen(_zeilen(self.bezuege, None), self.eigene)
        ergebnis: dict[str, Vorschlag] = {}
        for sache, z in zaehler.items():
            ohne_texte = self.merkmale(sache, z, texte_lesen=False)
            lesen = ohne_texte.beide_richtungen and (ohne_texte.mails >= KOLLEGEN_MAILS or ohne_texte.termine > 0)
            ergebnis[sache] = vorschlagen(self.merkmale(sache, z) if lesen else ohne_texte)
        return ergebnis

    def uebersicht(self, *, liste: int = 20) -> dict[str, Any]:
        """Für „Kingfisher und du“: wie viele bestätigt, wie viele Vorschläge offen, und welche.

        Offen ist ein Vorschlag „innerer Kreis“ oder „Kollegen“ ohne Bestätigung: nur diese ändern, wie Kingfisher
        über jemanden spricht. Wer nicht vorgeschlagen ist, muss nicht bestätigt werden. Dazu die bestätigten
        Personen, für die Kingfisher heute einen anderen Kreis vorschlagen würde.
        """
        fest = self.alle()
        vorschlaege = self.vorschlaege()
        offen = [(s, v) for s, v in vorschlaege.items() if s not in fest and v.kreis in (INNERER_KREIS, KOLLEGEN)]
        offen.sort(key=lambda p: (KREISE.index(p[1].kreis), -p[1].merkmale.mails, p[0]))
        geaendert = [s for s, k in fest.items() if s in vorschlaege and vorschlaege[s].kreis != k]
        namen = self.bezuege.beschriftungen([s for s, _ in offen[:liste]])
        je_kreis = {k: sum(1 for wert in fest.values() if wert == k) for k in KREISE}
        offen_je_kreis = {k: sum(1 for _, v in offen if v.kreis == k) for k in (INNERER_KREIS, KOLLEGEN)}
        return {'bestaetigt': len(fest), 'je_kreis': je_kreis, 'offen': len(offen), 'offen_je_kreis': offen_je_kreis,
                'geaendert': len(geaendert), 'letzte_sammlung': self.letzte_sammlung(),
                'vorschlaege': [{'sache': s, 'name': namen.get(s, s), 'kreis': v.kreis, 'kreis_text': KREIS_TEXT[v.kreis],
                                 'begruendung': v.begruendung} for s, v in offen[:liste]]}


def alle_bestaetigten(episodes: Any) -> dict[str, str]:
    """Sache -> bestätigter Kreis. Wirft nie: Ohne Tabelle (alter Speicher, Test) gibt es keinen."""
    try:
        with episodes._lock:
            return {z['sache']: z['kreis'] for z in episodes._conn.execute('SELECT sache, kreis FROM personen_kreis')}
    except Exception:  # noqa: BLE001
        return {}


def bestaetigter_kreis(episodes: Any, sache: str) -> str:
    """Der bestätigte Kreis einer Person, sonst `unbestimmt`. Wirft nie."""
    try:
        with episodes._lock:
            zeile = episodes._conn.execute('SELECT kreis FROM personen_kreis WHERE sache = ?', (sache,)).fetchone()
    except Exception:  # noqa: BLE001
        return UNBESTIMMT
    return zeile['kreis'] if zeile else UNBESTIMMT


# -- Wirkung -------------------------------------------------------------------------

#: Hinweis für das Antwortmodell je Kreis (Feld `kreis` einer Quelle im Kontext). Nur Formulierung, nichts verlässt
#: den Rechner.
FUER_MODELL = {
    INNERER_KREIS: 'innerer Kreis: mit Vornamen nennen, Alltägliches (Geburtstag, Termine) darf vorkommen',
    KOLLEGEN: 'Kollegen: sachlich, mit Bezug zum Projekt, nichts Privates',
    KONTAKTE: 'Kontakte: nur sagen, wonach gefragt ist, zurückhaltend formulieren',
}


def ungefragt_erlaubt(kreis: str | None) -> bool:
    """Darf etwas aus der Akte dieser Person ungefragt (im Briefing) erscheinen? Nicht bei bestätigten „Kontakte“."""
    return kreis != KONTAKTE


__all__ = ['FUER_MODELL', 'INNERER_KREIS', 'KOLLEGEN', 'KONTAKTE', 'KREISE', 'KREIS_TEXT', 'Kreise', 'Merkmale',
           'SammelVeraltet',
           'UNBESTIMMT', 'Vorschlag', 'WIRKUNG', 'alle_bestaetigten', 'bestaetigter_kreis', 'anrede', 'begruendung', 'ungefragt_erlaubt',
           'vorschlagen']
