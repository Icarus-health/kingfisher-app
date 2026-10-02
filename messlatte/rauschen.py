"""Rauschen: unauffällige Alltagsquellen für die Skalierungsmessung.

Ein Postfach hat nicht fünfzig Mails, sondern fünfzigtausend, und fast alle sind
Newsletter, Rechnungen und Routine. Erst zwischen ihnen zeigt sich, ob die Suche
die richtige Stelle findet. Dieser Erzeuger liefert deterministisch (gleicher
`seed`, gleiche Quellen) `anzahl` solcher Quellen, gleichmäßig über die drei
Jahre vor dem Stichtag.

Damit die Suche nicht trivial wird, teilt das Rauschen **Wörter** mit den
Szenarien: gleiche Vor- und Nachnamen in anderen Kombinationen (nie der volle Name
einer Person der Welt), gleiche Orte und Themenwörter in belanglosen Sätzen.

Private Szenarien (`bereich: privat`, M4) geben dem Rauschen keine Wörter und keine Sperren: Das Rauschen bleibt
dadurch Quelle für Quelle dasselbe wie ohne sie, und die Abrufkennzahlen der übrigen Welt bleiben vergleichbar.

Damit das Rauschen nie selbst eine Frage beantwortet oder eine falsche Aussage
provoziert, wird **jeder** erzeugte Text gegen alle Pflicht- und verbotenen
Aussagen aller Fragen, die vollen Personennamen und die Adressen der Welt geprüft
und bei einem Treffer neu gezogen. (Grenze: Alternativen unter vier Zeichen sind
zu unspezifisch und werden nicht geprüft.)
"""
from __future__ import annotations

import random
import re
from datetime import datetime, timedelta
from typing import Sequence

from .bewertung import normalisiere
from .daten import Adresse, Mail, Notiz, Quelle, Termin, Welt

PRAEFIX = 'rauschen'
DREI_JAHRE = timedelta(days=3 * 365)
# Obergrenzen, die das Produkt vorgibt: der Ordner-Adapter bricht bei 5000 Dateien ab,
# der Kalenderabgleich liefert höchstens 10000 Termine.
MAX_NOTIZEN = 4000
MAX_TERMINE = 8000

_VORNAMEN = ['Anna', 'Jonas', 'Petra', 'Markus', 'Sabine', 'Klaus', 'Julia', 'Stefan', 'Monika', 'Thomas',
             'Katrin', 'Dieter', 'Sandra', 'Frank', 'Birgit', 'Uwe', 'Nadine', 'Holger', 'Tanja', 'Rolf']
_NACHNAMEN = ['Keller', 'Bauer', 'Schmitt', 'Vogel', 'Lang', 'Roth', 'Berger', 'Arnold', 'Winter', 'Kraus',
              'Engel', 'Peters', 'Sommer', 'Krämer', 'Busch', 'Franke', 'Albrecht', 'Hoffmann', 'Lorenz', 'Kranz']
_ORTE = ['Wiesbaden', 'Frankfurt', 'Mainz', 'Darmstadt', 'Köln', 'Koblenz', 'Bonn', 'Kassel', 'Trier', 'Worms']
_THEMEN = ['Rechnung', 'Angebot', 'Termin', 'Projekt', 'Lieferung', 'Vertrag', 'Beratung', 'Einladung',
           'Bestellung', 'Erinnerung', 'Urlaub', 'Reise', 'Steuer', 'Strom', 'Versicherung', 'Fortbildung']
_ORGANISATIONEN = ['Stadtwerke', 'Verlag', 'Reisebüro', 'Versicherung', 'Bank', 'Buchhandlung', 'Fitnessstudio',
                   'Kfz-Werkstatt', 'Apotheke', 'Sparkasse', 'Bahn', 'Telefon']

_NEWSLETTER = [
    ('Neues aus {ort}: {thema} im Herbst', 'Diese Woche im Überblick: Veranstaltungen in {ort}, ein Bericht zum Thema {thema} '
     'und die Öffnungszeiten der Feiertage.\n\nSie erhalten diese Nachricht, weil Sie sich angemeldet haben. Abbestellen jederzeit möglich.'),
    ('{thema} aktuell: Tipps von {vorname} {nachname}', 'In dieser Ausgabe gibt {vorname} {nachname} Hinweise zum Thema {thema}. '
     'Dazu ein Rückblick auf die Messe in {ort}.\n\nViele Grüße, Ihre Redaktion'),
    ('Ihr Angebot der Woche', 'Nur diese Woche: Rabatt auf ausgewählte Artikel rund um {thema}. '
     'Abholung in {ort} oder Lieferung nach Hause.\n\nZur Abmeldung nutzen Sie den Link am Ende dieser Nachricht.'),
    ('Einladung: {thema}-Abend in {ort}', 'Wir laden Sie herzlich zu unserem {thema}-Abend in {ort} ein. '
     'Für Getränke ist gesorgt. Eine Anmeldung ist nicht erforderlich.\n\nIhr Team'),
]
_RECHNUNGEN = [
    ('Rechnung {nummer}', 'Sehr geehrte Kundin, sehr geehrter Kunde,\n\nanbei erhalten Sie Ihre Rechnung {nummer} über {betrag} Euro '
     'für {thema}. Bitte überweisen Sie den Betrag innerhalb von vierzehn Tagen.\n\n{organisation}'),
    ('Ihre Kontoübersicht', 'Guten Tag,\n\nIhre aktuelle Übersicht steht bereit. Es gab {anzahl} Buchungen, darunter eine Zahlung '
     'an {organisation} in {ort}.\n\nIhre {organisation}'),
    ('Zahlungsbestätigung {nummer}', 'Wir bestätigen den Eingang Ihrer Zahlung zur Rechnung {nummer}. Vielen Dank.\n\n{organisation}'),
    ('Beitragsrechnung {thema}', 'Der Beitrag für {thema} wird im kommenden Monat abgebucht. Eine Änderung Ihrer Daten '
     'ist nicht notwendig.\n\n{organisation}'),
]
_ROUTINE = [
    ('Terminabstimmung {thema}', 'Hallo {vorname},\n\nhast du diese Woche Zeit für ein kurzes Telefonat zum Thema {thema}? '
     'Ich bin flexibel und in {ort} unterwegs.\n\nViele Grüße\n{vorname2}'),
    ('Kurze Rückfrage', 'Hallo,\n\nkannst du mir bitte die Unterlagen zum Thema {thema} noch einmal schicken? '
     'Ich finde sie gerade nicht.\n\nDanke und Gruß\n{vorname2}'),
    ('Protokoll {thema}', 'Anbei das Protokoll unserer Besprechung zum Thema {thema}. Es gibt keine offenen Punkte.\n\n{vorname2} {nachname}'),
    ('Kaffee?', 'Lust auf einen Kaffee in {ort}? Ich melde mich, wenn ich weiß, wann ich dort bin.\n\n{vorname2}'),
    ('Danke für gestern', 'Hallo {vorname},\n\nvielen Dank für das Gespräch gestern. Es war hilfreich, auch wenn wir das Thema {thema} '
     'noch nicht abschließen konnten.\n\n{vorname2}'),
]
_TERMINE = ['{thema} mit {vorname} {nachname}', 'Besprechung {thema}', 'Telefonat {vorname}', 'Mittagessen in {ort}',
            'Arzttermin {ort}', 'Stammtisch {ort}', 'Fortbildung {thema}', 'Werkstatt {organisation}']
_NOTIZEN = [
    ('Einkaufsliste', 'Brot, Milch, Kaffee, Batterien für {thema}.'),
    ('Idee {thema}', 'Gedanke zum Thema {thema}: später mit {vorname} {nachname} besprechen, vielleicht in {ort}.'),
    ('Merkzettel {organisation}', 'Bei {organisation} nach den Öffnungszeiten fragen. Nichts Dringendes.'),
    ('Buchtipp', 'Gelesen: ein Buch über {thema} von {vorname} {nachname}. Gut, aber zu lang.'),
]


def _woerter(welten: Sequence[Welt]) -> tuple[list[str], list[str], list[str]]:
    """Vornamen, Nachnamen und Orte: Grundbestand plus die Wörter der Welt."""
    vor, nach, orte = list(_VORNAMEN), list(_NACHNAMEN), list(_ORTE)
    for welt in welten:
        namen = [n for p in welt.personen for n in p.namen]
        namen += [a.name for q in _quellen(welt) if isinstance(q, Mail) for a in (q.von, *q.an)]
        for name in namen:
            teile = [t for t in re.findall(r'[A-ZÄÖÜ][a-zäöüß-]{2,}', name) if t not in {'Frau', 'Herr', 'Dr'}]
            if len(teile) >= 2:
                vor.append(teile[0])
                nach.append(teile[-1])
        for q in _quellen(welt):
            texte = [getattr(q, f, '') or '' for f in ('betreff', 'titel', 'ort')]
            orte += [o for t in texte for o in re.findall(r'\b[A-ZÄÖÜ][a-zäöüß]{4,}\b', t)]
    return sorted(set(vor)), sorted(set(nach)), sorted(set(orte))


def _quellen(welt: Welt) -> list:
    """Die Quellen der Welt ohne private Szenarien (siehe Modulkopf)."""
    privat = welt.private_szenarien
    return [q for q in welt.quellen if q.szenario not in privat]


def _sperrliste(welten: Sequence[Welt]) -> list[str]:
    """Alles, was im Rauschen nie vorkommen darf (normalisiert)."""
    gesperrt: set[str] = set()
    for welt in welten:
        for frage in (f for f in welt.fragen if f.szenario not in welt.private_szenarien):
            for gruppe in frage.erwartet.aussagen:
                gesperrt |= {normalisiere(a) for a in gruppe}
            gesperrt |= {normalisiere(v) for v in frage.verboten.aussagen}
        for person in welt.personen:
            gesperrt |= {normalisiere(n) for n in person.namen} | {normalisiere(a) for a in person.adressen}
        gesperrt |= {normalisiere(a) for a in welt.nutzer.adressen}
        gesperrt.add(normalisiere(welt.nutzer.name))
    return sorted(g for g in gesperrt if len(g) >= 4)


def _adresse(vorname: str, nachname: str, domain: str) -> Adresse:
    stamm = (vorname[0] + '.' + nachname).lower().replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue').replace('ß', 'ss')
    return Adresse(f'{vorname} {nachname}', f'{stamm}@{domain}')


# Öffentlich für `lange.py`: dasselbe Vokabular und dieselbe Sperrliste, damit Füllmaterial nie antwortet.
THEMEN, ORGANISATIONEN = tuple(_THEMEN), tuple(_ORGANISATIONEN)
woerter, sperrliste = _woerter, _sperrliste


class _Erzeuger:
    def __init__(self, welten: Sequence[Welt], seed: int):
        self.rng = random.Random(seed)
        self.welt = welten[0]
        self.vornamen, self.nachnamen, self.orte = _woerter(welten)
        self.gesperrt = _sperrliste(welten)
        self.eigene = self.welt.nutzer
        self.nutzer_adresse = Adresse(self.eigene.name, self.eigene.adressen[0])

    def _slots(self) -> dict:
        r = self.rng
        organisation = r.choice(_ORGANISATIONEN)
        return {
            'vorname': r.choice(self.vornamen), 'vorname2': r.choice(self.vornamen),
            'nachname': r.choice(self.nachnamen), 'ort': r.choice(self.orte), 'thema': r.choice(_THEMEN),
            'organisation': organisation, 'nummer': f'{r.randint(10000, 99999)}',
            'betrag': f'{r.randint(5, 900)},{r.randint(0, 99):02d}', 'anzahl': r.randint(3, 40),
        }

    def _sauber(self, *texte: str) -> bool:
        gesamt = normalisiere(' '.join(texte))
        return not any(g in gesamt for g in self.gesperrt)

    def _ziehen(self, vorlagen, bauen):
        """Zieht neu, bis nichts Gesperrtes im Text steht; sonst ein neutraler Notausgang."""
        for _ in range(30):
            slots = self._slots()
            ergebnis = bauen(self.rng.choice(vorlagen), slots)
            # Auch die Namen, die als Absender dienen, dürfen keine Person der Welt ergeben.
            namen = (f"{slots['vorname']} {slots['nachname']}", f"{slots['vorname2']} {slots['nachname']}")
            if self._sauber(*ergebnis[1], *namen):
                return ergebnis
        slots = {k: 'Alltag' if isinstance(v, str) else 1 for k, v in self._slots().items()}
        return bauen(vorlagen[0], slots)

    def _domain(self, art: str, slots: dict) -> str:
        return f"{art}-{slots['organisation'].lower().replace('ü', 'ue').replace('ä', 'ae')}-{self.rng.randint(1, 60)}.example"

    def mail(self, index: int, zeit: datetime, art: str) -> Mail:
        vorlagen = {'newsletter': _NEWSLETTER, 'rechnung': _RECHNUNGEN, 'routine': _ROUTINE}[art]

        def bauen(vorlage, slots):
            betreff, text = vorlage
            return slots, (betreff.format(**slots), text.format(**slots))
        slots, (betreff, text) = self._ziehen(vorlagen, bauen)
        domain = self._domain('info' if art != 'routine' else 'privat', slots)
        privat = art == 'routine'
        absender = (_adresse(slots['vorname2'], slots['nachname'], domain) if privat
                    else Adresse(f"{slots['organisation']} {slots['ort']}", f'service@{domain}'))
        gesendet = privat and self.rng.random() < 0.3
        if gesendet:
            return Mail(id=f'{PRAEFIX}-{index:06d}', zeit=zeit, szenario=PRAEFIX, von=self.nutzer_adresse, an=(absender,),
                        betreff='Re: ' + betreff, text=text, ordner='Sent')
        return Mail(id=f'{PRAEFIX}-{index:06d}', zeit=zeit, szenario=PRAEFIX, von=absender, an=(self.nutzer_adresse,),
                    betreff=betreff, text=text)

    def termin(self, index: int, zeit: datetime) -> Termin:
        def bauen(vorlage, slots):
            return slots, (vorlage.format(**slots),)
        slots, (titel,) = self._ziehen(_TERMINE, bauen)
        beginn = zeit + timedelta(days=self.rng.randint(0, 14), hours=self.rng.randint(0, 8))
        beginn = beginn.replace(minute=self.rng.choice((0, 15, 30, 45)), second=0, microsecond=0)
        return Termin(id=f'{PRAEFIX}-{index:06d}', zeit=zeit, szenario=PRAEFIX, beginn=beginn,
                      ende=beginn + timedelta(minutes=self.rng.choice((30, 45, 60, 90))), titel=titel,
                      ort=slots['ort'] if self.rng.random() < 0.5 else '')

    def notiz(self, index: int, zeit: datetime) -> Notiz:
        def bauen(vorlage, slots):
            return slots, (vorlage[0].format(**slots), vorlage[1].format(**slots))
        _, (titel, text) = self._ziehen(_NOTIZEN, bauen)
        return Notiz(id=f'{PRAEFIX}-{index:06d}', zeit=zeit, szenario=PRAEFIX, titel=titel, text=text)


def erzeuge(anzahl: int, welten: Sequence[Welt], seed: int = 1) -> tuple[Quelle, ...]:
    """`anzahl` Alltagsquellen, gleichmäßig über die drei Jahre vor dem Stichtag."""
    if anzahl <= 0:
        return ()
    stichtag = welten[0].stichtag
    erzeuger = _Erzeuger(welten, seed)
    rng = erzeuger.rng
    schritt = DREI_JAHRE / anzahl
    ergebnis: list[Quelle] = []
    termine = notizen = 0
    for index in range(anzahl):
        # Mitte des Zeitfensters plus Streuung; immer vor dem Stichtag und nie vor dem Fenster.
        zeit = stichtag - DREI_JAHRE + schritt * index + schritt * rng.random()
        zeit = min(zeit, stichtag - timedelta(minutes=1)).replace(microsecond=0)
        wurf = rng.random()
        if wurf < 0.10 and termine < MAX_TERMINE:
            ergebnis.append(erzeuger.termin(index + 1, zeit))
            termine += 1
        elif wurf < 0.14 and notizen < MAX_NOTIZEN:
            ergebnis.append(erzeuger.notiz(index + 1, zeit))
            notizen += 1
        else:
            art = rng.choices(['newsletter', 'rechnung', 'routine'], weights=[0.45, 0.25, 0.30])[0]
            ergebnis.append(erzeuger.mail(index + 1, zeit, art))
    return tuple(ergebnis)
