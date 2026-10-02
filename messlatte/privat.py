"""Stufe „Privat“ (M4): Kreis je Person, private Akten-Arten und Fristen aus privaten Mails.

Die Welt nennt je Szenario, was Kingfisher vorschlagen soll (`kreise`, `akten_arten`, `fristen`, `keine_fristen` in
FORMAT.md). Die Stufe läuft in jedem `lauf` mit, sobald die Welt solche Erwartungen hat, auf demselben Bestand wie
die Fragen (mit Rauschen, wenn es eingeschaltet ist). Gemessen wird über die Routen der Oberfläche, wo es sie gibt:

* **Kreise:** je erwarteter Person der Vorschlag von `GET /api/v1/kreis` und ob die Begründung jedes erwartete
  Merkmal nennt. Dazu über **alle** Personen des Bestands (Welt und Rauschen, `kreis.Kreise.vorschlaege`): Wer
  „innerer Kreis“ vorgeschlagen bekommt, ohne dass die Welt das für ihn erwartet, ist ein **falscher innerer Kreis**.
  Zielwert 0: Ein Fremder landet nie im inneren Kreis.
* **Akten-Arten:** je erwarteter Organisation der Vorschlag von `GET /api/v1/akten/art`.
* **Fristen:** `POST /api/v1/akten/arten/fristen`, dann die Aufgabenvorschläge (`GET /api/v1/task-candidates`).
  Erwartet gefunden heißt: ein Vorschlag aus dieser Quelle mit diesem Fälligkeitstag, der Betrag (falls erwartet)
  wörtlich in der Aussage. **Verboten:** eine Zahl im Vorschlag, die in keiner Quelle steht, und ein Vorschlag aus
  einer Quelle unter `keine_fristen`. Vorschläge aus anderen Quellen stehen getrennt als „ohne Erwartung“.
* **Geburtstage und Wiederkehrendes:** `POST /api/v1/wiederkehrendes/vorschlagen`, dann die Wissenskandidaten
  (`GET /api/v1/memory/candidates`). Erwartet gefunden heißt: ein Geburtstag dieser Person mit diesem Tag, oder eine
  wiederkehrende Sache aus dieser Quelle, deren Aussage jedes erwartete Wort enthält. **Verboten:** ein Geburtstag für
  eine Person ohne Erwartung (vor allem für Kollegen und Kontakte, `keine_geburtstage`), Wiederkehrendes aus einer
  Quelle unter `keine_wiederkehrend` und eine Zahl in der Aussage, die nicht in der Quelle steht.
* **Anhänge:** Je PDF-Anhang der Welt (`anhaenge` einer Mail): angekommen als eigene Quelle, mit Text gelesen und
  „Seite N“ im Text, oder, wenn gescannt, ehrlich „noch nicht gelesen“. Fristen aus Anhängen zählen wie die aus Mails
  (Quelle `<Mail-ID>#anhang-<n>`).
* **Regel des Gedächtnisses:** Nach der Stufe ist kein Kreis und keine Art bestätigt, keine Aufgabe und keine Aussage
  entstanden; alles ist Vorschlag.
* **Probe des Briefings** (danach, nicht Teil der Regel oben): Für die Personen mit erwartetem Geburtstag und
  erwartetem innerem Kreis bestätigt die Stufe den Kreis und nimmt den Geburtstag an, wie ein Mensch es täte, und liest
  die Zeile „Geburtstag“ im Briefing des Stichtags (`briefing_geburtstag`).

Die Stufe misst Regeln ohne Modell. Sie sagt nichts darüber, wie gut ein Modell über die Personen formuliert.
"""
from __future__ import annotations

import time
from urllib.parse import quote
from dataclasses import dataclass, field

from .aufnahme import ist_rauschen


@dataclass
class KreisTreffer:
    adresse: str
    erwartet: str
    vorgeschlagen: str = ''
    begruendung: str = ''
    fehlende_merkmale: tuple = ()

    @property
    def richtig(self) -> bool:
        return self.vorgeschlagen == self.erwartet and not self.fehlende_merkmale


@dataclass
class PrivatMessung:
    kreise: list = field(default_factory=list)
    falsche_innere: list = field(default_factory=list)
    """(Adresse, Herkunft „welt“ oder „rauschen“, Begründung) je Person, die ohne Erwartung innerer Kreis wurde."""
    personen: int = 0
    vorschlaege_je_kreis: dict = field(default_factory=dict)
    arten: list = field(default_factory=list)
    """(Adresse, erwartete Art, vorgeschlagene Art, Begründung)."""
    fristen: list = field(default_factory=list)
    """(Quelle, Art, Datum, Betrag, gefunden, Aussage)."""
    fristen_ohne_erwartung: list = field(default_factory=list)
    zahlen_ohne_beleg: list = field(default_factory=list)
    verbotene_fristen: list = field(default_factory=list)
    bestaetigt_nachher: int = 0
    aufgaben_vorher: int = 0
    aufgaben_nachher: int = 0
    dauer_s: float = 0.0
    geburtstage: list = field(default_factory=list)
    """(Adresse, erwarteter Tag MM-TT, gefunden, Aussage)."""
    geburtstage_falsch: list = field(default_factory=list)
    """(Adresse, Tag, Aussage) je Geburtstagsvorschlag ohne Erwartung."""
    wiederkehrend: list = field(default_factory=list)
    """(Quelle, erwartete Wörter, gefunden, Aussage)."""
    wiederkehrend_verboten: list = field(default_factory=list)
    wiederkehrend_ohne_erwartung: list = field(default_factory=list)
    wk_zahlen_ohne_beleg: list = field(default_factory=list)
    wissen_nachher: int = 0
    """Angenommene Aussagen (Geburtstag, Wiederkehrendes) nach der Stufe, vor der Probe des Briefings: Zielwert 0."""
    briefing: dict = field(default_factory=dict)
    """Probe: erwartete Zeile, gezeigte Zeile, ob gleich, und ob ein Kontakt darin vorkam."""
    anhaenge: list = field(default_factory=list)
    """(Welt-ID, erwartet `gelesen` oder `gescannt`, Stand im Produkt, richtig)."""
    wk_kennt_es: bool = True
    """False, wenn das Produkt Geburtstage und Wiederkehrendes noch nicht kennt (Stand vor dem Rest von M4)."""
    produkt_kennt_es: bool = True
    """False, wenn das Produkt Kreis, Akten-Arten und Fristen noch nicht kennt (Stand vor M4): Dann ist nichts
    vorgeschlagen, und genau das zählt die Stufe (Vorher-Messung)."""

    @property
    def kreise_richtig(self) -> int:
        return sum(1 for k in self.kreise if k.richtig)

    @property
    def arten_richtig(self) -> int:
        return sum(1 for _, erwartet, vorgeschlagen, _ in self.arten if erwartet == vorgeschlagen)

    @property
    def fristen_gefunden(self) -> int:
        return sum(1 for f in self.fristen if f[4])

    @property
    def geburtstage_gefunden(self) -> int:
        return sum(1 for g in self.geburtstage if g[2])

    @property
    def wiederkehrend_gefunden(self) -> int:
        return sum(1 for w in self.wiederkehrend if w[2])

    @property
    def anhaenge_richtig(self) -> int:
        return sum(1 for a in self.anhaenge if a[3])

    @property
    def nur_vorschlaege(self) -> bool:
        return (self.bestaetigt_nachher == 0 and self.aufgaben_vorher == self.aufgaben_nachher
                and self.wissen_nachher == 0)


def _fehlende(merkmale, begruendung: str) -> tuple:
    text = ' '.join(begruendung.split()).casefold()
    return tuple(m for m in merkmale if ' '.join(m.split()).casefold() not in text)


def _vor_m4(welten, messung: PrivatMessung) -> PrivatMessung:
    """Ein Produkt ohne Kreis und Akten-Arten: Jede Erwartung bleibt unerfüllt, nichts ist vorgeschlagen."""
    messung.produkt_kennt_es = False
    messung.kreise = [KreisTreffer(e.adresse, e.kreis) for w in welten for e in w.kreis_erwartungen]
    messung.arten = [(e.adresse, e.art, '', '') for w in welten for e in w.art_erwartungen]
    messung.fristen = [(e.quelle, e.art, e.datum, e.betrag, False, '') for w in welten for e in w.frist_erwartungen]
    return messung


def messen(instanz, welten, aufgenommen) -> PrivatMessung:
    """Kreise, Arten und Fristen über die Routen; falsche innere Kreise über alle Personen des Bestands."""
    from icarus_memory.akten_routes import bausteine, nachfuehren
    from icarus_memory.bezuege import org_aus_adresse, sache_id

    begonnen = time.perf_counter()
    app = instanz.app
    messung = PrivatMessung(aufgaben_vorher=len(app.state.tasks.all_tasks(limit=1_000_000)))
    try:
        from icarus_memory import akten_arten
        from icarus_memory.kreis import INNERER_KREIS, Kreise
    except ImportError:
        messung.aufgaben_nachher = messung.aufgaben_vorher
        return _vor_m4(welten, messung)
    nachfuehren(app, warten=True)
    erwartet = {e.adresse: e for w in welten for e in w.kreis_erwartungen}
    for adresse, e in erwartet.items():
        stand = instanz.anfrage('GET', f'/api/v1/kreis?sache={quote("person:a:" + adresse)}')
        vorschlag = stand['vorschlag']
        messung.kreise.append(KreisTreffer(adresse, e.kreis, vorschlag['kreis'], vorschlag['begruendung'],
                                           _fehlende(e.merkmale, vorschlag['begruendung'])))
    # Alle Personen: Wer wird innerer Kreis, ohne dass die Welt es erwartet? (Eigene Adressen aus der Welt, wie im Betrieb
    # aus den Konten.)
    bezuege, _ = bausteine(app)
    vorschlaege = Kreise(bezuege, instanz.eigene).vorschlaege()
    messung.personen = len(vorschlaege)
    adressen_der_welt = {a.adresse.casefold() for w in welten for q in w.quellen for a in _beteiligte(q)}
    for vorschlag in vorschlaege.values():
        messung.vorschlaege_je_kreis[vorschlag.kreis] = messung.vorschlaege_je_kreis.get(vorschlag.kreis, 0) + 1
    messung.falsche_innere = falsche_innere(
        {sache: (v.kreis, v.begruendung) for sache, v in vorschlaege.items()},
        {a: e.kreis for a, e in erwartet.items()}, adressen_der_welt, INNERER_KREIS)
    for e in (e for w in welten for e in w.art_erwartungen):
        sache = sache_id('organisation', org_aus_adresse(e.adresse))
        stand = instanz.anfrage('GET', f'/api/v1/akten/art?sache={quote(sache)}')
        messung.arten.append((e.adresse, e.art, stand['vorschlag']['art'] or '', stand['vorschlag']['begruendung']))
    # Fristen: Anstoß über die Route, dann die Aufgabenvorschläge.
    instanz.anfrage('POST', '/api/v1/akten/arten/fristen')
    kandidaten = [k for k in instanz.anfrage('GET', '/api/v1/task-candidates')
                  if str(k.get('proposed_by', '')).startswith(akten_arten.VORGESCHLAGEN_VON)]
    episode_zu_welt = {episode: welt for welt, episode in aufgenommen.episoden.items()}
    quellen = {q.id: q for w in welten for q in w.quellen}
    je_quelle: dict[str, list[dict]] = {}
    for k in kandidaten:
        beleg = k['evidence'][0]
        welt_id = episode_zu_welt.get(beleg['episode_id'], beleg['episode_id'])
        je_quelle.setdefault(welt_id, []).append(k)
        try:
            episode = instanz.episodes.get(beleg['episode_id'])
            text = f'{episode.title}\n{episode.body}\n' + ' '.join(episode.participants)
        except Exception:  # noqa: BLE001 - ohne Quelle ist jede Zahl unbelegt
            text = ''
        ohne = akten_arten.zahlen_belegt(k['statement'], text)
        if ohne or beleg['quote'] not in text:
            messung.zahlen_ohne_beleg.append((welt_id, k['statement'], ohne))
    keine = {q for w in welten for q in w.keine_fristen}
    gezaehlt: set[str] = set()
    for e in (e for w in welten for e in w.frist_erwartungen):
        passend = [k for k in je_quelle.get(e.quelle, []) if (k.get('valid_until') or '')[:10] == e.datum
                   and (not e.betrag or e.betrag in k['statement'])]
        gezaehlt.update(k['id'] for k in passend)
        messung.fristen.append((e.quelle, e.art, e.datum, e.betrag, bool(passend),
                                passend[0]['statement'] if passend else ''))
    for welt_id, liste in sorted(je_quelle.items()):
        for k in liste:
            if welt_id in keine:
                messung.verbotene_fristen.append((welt_id, k['statement']))
            elif k['id'] not in gezaehlt:
                herkunft = 'rauschen' if ist_rauschen(welt_id) else (
                    'welt' if welt_id.split('#anhang-')[0] in quellen else 'unbekannt')
                messung.fristen_ohne_erwartung.append((welt_id, herkunft, k['statement']))
    with instanz.episodes._lock:
        verbindung = instanz.episodes._conn
        messung.bestaetigt_nachher = (verbindung.execute('SELECT COUNT(*) FROM personen_kreis').fetchone()[0]
                                      + verbindung.execute('SELECT COUNT(*) FROM akten_arten').fetchone()[0])
    messung.aufgaben_nachher = len(app.state.tasks.all_tasks(limit=1_000_000))
    messung.anhaenge = anhaenge_messen(instanz, welten, aufgenommen)
    geburtstage_und_wiederkehrendes(instanz, welten, aufgenommen, messung)
    messung.dauer_s = round(time.perf_counter() - begonnen, 2)
    briefing_probe(instanz, welten, messung)
    return messung


def anhaenge_messen(instanz, welten, aufgenommen) -> list:
    """Je PDF-Anhang der Welt: als Quelle angekommen, gelesen mit Seite, oder ehrlich „noch nicht gelesen“."""
    from .daten import Mail
    ergebnis = []
    for mail in (q for w in welten for q in w.quellen if isinstance(q, Mail)):
        for nummer, anhang in enumerate(mail.anhaenge, 1):
            welt_id = f'{mail.id}#anhang-{nummer}'
            erwartet = 'gelesen' if anhang.seiten else 'gescannt'
            episode_id = aufgenommen.episoden.get(welt_id)
            if episode_id is None:
                ergebnis.append((welt_id, erwartet, 'nicht aufgenommen', False))
                continue
            episode = instanz.episodes.get(episode_id)
            stand = next((t.split(':', 1)[1] for t in episode.tags if t.startswith('anhang:')), 'unbekannt')
            if erwartet == 'gelesen':
                richtig = stand == 'gelesen' and '\nSeite 1\n' in episode.body and all(
                    z in episode.body for seite in anhang.seiten for z in seite)
            else:
                richtig = stand == 'gescannt' and 'noch nicht gelesen' in episode.body
            ergebnis.append((welt_id, erwartet, stand, richtig))
    return ergebnis


def _wissen(instanz) -> list:
    try:
        return [c for c in instanz.app.state.claims.all_claims(include_inactive=False)
                if c.predicate in ('geburtstag', 'wiederkehrend')]
    except Exception:  # noqa: BLE001
        return []


def geburtstage_und_wiederkehrendes(instanz, welten, aufgenommen, messung: PrivatMessung) -> None:
    """Geburtstage und Wiederkehrendes über die Routen; vorher (ohne Modul) bleibt jede Erwartung unerfüllt."""
    geburtstage = [e for w in welten for e in w.geburtstag_erwartungen]
    wiederkehrend = [e for w in welten for e in w.wiederkehr_erwartungen]
    try:
        from icarus_memory import akten_arten, wiederkehrendes as wk
    except ImportError:
        messung.wk_kennt_es = False
        messung.geburtstage = [(e.adresse, e.datum, False, '') for e in geburtstage]
        messung.wiederkehrend = [(e.quelle, list(e.enthaelt), False, '') for e in wiederkehrend]
        return
    instanz.anfrage('POST', '/api/v1/wiederkehrendes/vorschlagen')
    kandidaten = instanz.anfrage('GET', '/api/v1/memory/candidates')
    episode_zu_welt = {episode: welt for welt, episode in aufgenommen.episoden.items()}
    geb = [k for k in kandidaten if k['predicate'] == wk.PRAEDIKAT_GEBURTSTAG
           and str(k.get('proposed_by', '')).startswith(wk.VON_GEBURTSTAG)]
    erwartet = {e.adresse: e for e in geburtstage}
    for e in geburtstage:
        passend = [k for k in geb if k['subject_ref'] == 'person:a:' + e.adresse and k['value'] == e.datum]
        messung.geburtstage.append((e.adresse, e.datum, bool(passend), passend[0]['statement'] if passend else ''))
    for k in geb:
        adresse = k['subject_ref'][len('person:a:'):]
        if adresse not in erwartet or erwartet[adresse].datum != k['value']:
            messung.geburtstage_falsch.append((adresse, k['value'], k['statement']))
    wied = [k for k in kandidaten if k['predicate'] == wk.PRAEDIKAT_WIEDERKEHREND
            and str(k.get('proposed_by', '')).startswith(wk.VON_WIEDERKEHREND)]
    keine = {q for w in welten for q in w.keine_wiederkehrend}
    gezaehlt: set[str] = set()
    je_quelle: dict[str, list[dict]] = {}
    for k in wied:
        beleg = k['evidence'][0]
        welt_id = episode_zu_welt.get(beleg['episode_id'], beleg['episode_id'])
        je_quelle.setdefault(welt_id, []).append(k)
        try:
            episode = instanz.episodes.get(beleg['episode_id'])
            text = f'{episode.title}\n{episode.body}'
        except Exception:  # noqa: BLE001
            text = ''
        ohne = akten_arten.zahlen_belegt(k['statement'], text)
        if ohne or beleg['quote'] not in text:
            messung.wk_zahlen_ohne_beleg.append((welt_id, k['statement'], ohne))
    for e in wiederkehrend:
        passend = [k for k in je_quelle.get(e.quelle, []) if k['id'] not in gezaehlt
                   and all(wort.casefold() in k['statement'].casefold() for wort in e.enthaelt)]
        if passend:
            gezaehlt.add(passend[0]['id'])
        messung.wiederkehrend.append((e.quelle, list(e.enthaelt), bool(passend), passend[0]['statement'] if passend else ''))
    for welt_id, liste in sorted(je_quelle.items()):
        for k in liste:
            if welt_id in keine:
                messung.wiederkehrend_verboten.append((welt_id, k['statement']))
            elif k['id'] not in gezaehlt:
                herkunft = 'rauschen' if ist_rauschen(welt_id) else 'welt'
                messung.wiederkehrend_ohne_erwartung.append((welt_id, herkunft, k['statement']))
    messung.wissen_nachher = len(_wissen(instanz))


def briefing_probe(instanz, welten, messung: PrivatMessung) -> None:
    """Wie ein Mensch: innere Kreise bestätigen, Geburtstage annehmen, dann die Zeile im Briefing des Stichtags lesen."""
    erwartet_text = next((t for w in welten for t in w.briefing_geburtstag), '')
    if not erwartet_text or not messung.wk_kennt_es:
        messung.briefing = {'erwartet': erwartet_text, 'gezeigt': '', 'gleich': False, 'gemessen': False}
        return
    innen = {e.adresse for w in welten for e in w.kreis_erwartungen if e.kreis == 'innerer_kreis'}
    kandidaten = instanz.anfrage('GET', '/api/v1/memory/candidates')
    for adresse, datum, gefunden, _ in messung.geburtstage:
        if not gefunden or adresse not in innen:
            continue
        sache = 'person:a:' + adresse
        instanz.anfrage('PUT', '/api/v1/kreis', {'sache': sache, 'kreis': 'innerer_kreis'})
        for k in kandidaten:
            if k['subject_ref'] == sache and k['predicate'] == 'geburtstag' and k['value'] == datum:
                instanz.anfrage('POST', f'/api/v1/memory/candidates/{k["id"]}/accept', {'supersedes': []})
    # Ein Kontakt mit Geburtstag im Kalender (keine_geburtstage) wird als Kontakt bestätigt: Er darf nie erscheinen.
    for adresse in (a for w in welten for a in w.keine_geburtstage):
        instanz.anfrage('PUT', '/api/v1/kreis', {'sache': 'person:a:' + adresse, 'kreis': 'kontakte'})
    briefing = instanz.anfrage('GET', '/api/v1/tag/briefing?nachladen=true')
    zeilen = (briefing.get('tageslage') or {}).get('zeilen') or []
    gezeigt = next((z['text'] for z in zeilen if z['art'] == 'geburtstag'), '')
    kontakte = [g for g in briefing.get('geburtstage') or []
                if g['sache'][len('person:a:'):] in {a for w in welten for a in w.keine_geburtstage}]
    messung.briefing = {'erwartet': erwartet_text, 'gezeigt': gezeigt, 'gleich': gezeigt == erwartet_text,
                        'gemessen': True, 'kontakte_im_briefing': len(kontakte)}


def falsche_innere(vorschlaege: dict, erwartet: dict, adressen_der_welt: set, innen: str = 'innerer_kreis') -> list:
    """(Adresse, Herkunft, Begründung) je Person, die „innerer Kreis“ vorgeschlagen bekommt, ohne dass die Welt es
    für sie erwartet. `vorschlaege`: Sache -> (Kreis, Begründung); `erwartet`: Adresse -> Kreis. Rein."""
    ergebnis = []
    for sache, (kreis, begruendung) in sorted(vorschlaege.items()):
        adresse = sache[len('person:a:'):]
        if kreis == innen and erwartet.get(adresse) != innen:
            ergebnis.append((adresse, 'welt' if adresse in adressen_der_welt else 'rauschen', begruendung))
    return ergebnis


def _beteiligte(quelle) -> tuple:
    from .daten import Mail, Termin
    if isinstance(quelle, Mail):
        return (quelle.von, *quelle.an, *quelle.cc)
    if isinstance(quelle, Termin):
        return quelle.teilnehmer
    return ()


def zu_dict(m: PrivatMessung) -> dict:
    return {
        'kreise': {'erwartet': len(m.kreise), 'richtig': m.kreise_richtig,
                   'je_person': [{'adresse': k.adresse, 'erwartet': k.erwartet, 'vorgeschlagen': k.vorgeschlagen,
                                  'begruendung': k.begruendung, 'fehlende_merkmale': list(k.fehlende_merkmale)}
                                 for k in m.kreise],
                   'falsche_innere': [list(f) for f in m.falsche_innere], 'personen': m.personen,
                   'vorschlaege_je_kreis': dict(m.vorschlaege_je_kreis)},
        'akten_arten': {'erwartet': len(m.arten), 'richtig': m.arten_richtig, 'je_akte': [list(a) for a in m.arten]},
        'fristen': {'erwartet': len(m.fristen), 'gefunden': m.fristen_gefunden, 'je_frist': [list(f) for f in m.fristen],
                    'ohne_erwartung': [list(f) for f in m.fristen_ohne_erwartung],
                    'zahlen_ohne_beleg': [list(f) for f in m.zahlen_ohne_beleg],
                    'aus_verbotenen_quellen': [list(f) for f in m.verbotene_fristen]},
        'geburtstage': {'erwartet': len(m.geburtstage), 'gefunden': m.geburtstage_gefunden,
                        'je_person': [list(g) for g in m.geburtstage], 'ohne_erwartung': [list(g) for g in m.geburtstage_falsch]},
        'wiederkehrend': {'erwartet': len(m.wiederkehrend), 'gefunden': m.wiederkehrend_gefunden,
                          'je_erwartung': [list(w) for w in m.wiederkehrend],
                          'aus_verbotenen_quellen': [list(w) for w in m.wiederkehrend_verboten],
                          'ohne_erwartung': [list(w) for w in m.wiederkehrend_ohne_erwartung],
                          'zahlen_ohne_beleg': [list(w) for w in m.wk_zahlen_ohne_beleg]},
        'anhaenge': {'erwartet': len(m.anhaenge), 'richtig': m.anhaenge_richtig, 'je_anhang': [list(a) for a in m.anhaenge]},
        'wissen_nachher': m.wissen_nachher, 'briefing': dict(m.briefing), 'wk_kennt_es': m.wk_kennt_es,
        'nur_vorschlaege': m.nur_vorschlaege, 'dauer_s': m.dauer_s, 'produkt_kennt_es': m.produkt_kennt_es,
    }


def markdown(m: PrivatMessung) -> list[str]:
    ja = lambda wert: 'ja' if wert else '**nein**'  # noqa: E731
    zeilen = ['## Stufe Privat (Kreis, Akten-Arten, Fristen, Geburtstage, Wiederkehrendes)', '',
              *([] if m.produkt_kennt_es else ['Das Produkt kennt Kreis, private Akten-Arten und Fristvorschläge noch '
                                                'nicht (Stand vor M4): Es schlägt nichts vor.', '']),
              f'Regeln ohne Modell, auf demselben Bestand wie die Fragen ({m.personen} Personen mit Adresse), '
              f'{m.dauer_s} s.', '',
              f'- **Kreise wie erwartet vorgeschlagen (mit allen Merkmalen in der Begründung): '
              f'{m.kreise_richtig} von {len(m.kreise)}**',
              f'- **Falsche innere Kreise (innerer Kreis ohne Erwartung, Welt und Rauschen): {len(m.falsche_innere)}**',
              f'- **Akten-Arten wie erwartet vorgeschlagen: {m.arten_richtig} von {len(m.arten)}**',
              f'- **Fristen gefunden: {m.fristen_gefunden} von {len(m.fristen)}** · Zahlen ohne Beleg: '
              f'{len(m.zahlen_ohne_beleg)} · Fristen aus Quellen, die keine haben: {len(m.verbotene_fristen)} · '
              f'weitere Fristvorschläge ohne Erwartung: {len(m.fristen_ohne_erwartung)}',
              *([] if m.wk_kennt_es else ['- Das Produkt kennt Geburtstage und Wiederkehrendes noch nicht: Es schlägt nichts vor.']),
              f'- **PDF-Anhänge als Quelle wie erwartet (gelesen mit Seite, gescannt ehrlich „noch nicht gelesen“): '
              f'{m.anhaenge_richtig} von {len(m.anhaenge)}**',
              f'- **Geburtstage gefunden (nur innerer Kreis): {m.geburtstage_gefunden} von {len(m.geburtstage)}** · '
              f'Geburtstage ohne Erwartung (Kollegen, Kontakte, falscher Tag): {len(m.geburtstage_falsch)}',
              f'- **Wiederkehrendes gefunden: {m.wiederkehrend_gefunden} von {len(m.wiederkehrend)}** · Zahlen ohne Beleg: '
              f'{len(m.wk_zahlen_ohne_beleg)} · aus Quellen, die keins haben: {len(m.wiederkehrend_verboten)} · '
              f'weitere ohne Erwartung: {len(m.wiederkehrend_ohne_erwartung)}',
              f'- Regel des Gedächtnisses: nichts bestätigt, keine Aufgabe und keine Aussage angelegt, alles Vorschlag: '
              f'{ja(m.nur_vorschlaege)}',
              *([f'- Probe des Briefings (innere Kreise bestätigt, Geburtstage angenommen): „{m.briefing.get("gezeigt") or "–"}“ '
                 f'(erwartet „{m.briefing.get("erwartet")}“): {ja(m.briefing.get("gleich"))}; Kontakte im Briefing: '
                 f'{m.briefing.get("kontakte_im_briefing", 0)}'] if m.briefing.get('gemessen') else []),
              '- Vorschläge über alle Personen: ' + ', '.join(f'{k} {n}' for k, n in sorted(m.vorschlaege_je_kreis.items())),
              '', '| Person | erwartet | vorgeschlagen | Begründung | fehlende Merkmale |', '|---|---|---|---|---|']
    for k in m.kreise:
        zeilen.append(f"| {k.adresse} | {k.erwartet} | {k.vorgeschlagen}{'' if k.richtig else ' **✗**'} | {k.begruendung} | "
                      f"{', '.join(k.fehlende_merkmale) or '–'} |")
    zeilen += ['', '| Akte (Absender) | erwartet | vorgeschlagen | Begründung |', '|---|---|---|---|']
    for adresse, erwartet, vorgeschlagen, begruendung in m.arten:
        zeilen.append(f"| {adresse} | {erwartet} | {vorgeschlagen or '–'}{'' if erwartet == vorgeschlagen else ' **✗**'} | "
                      f'{begruendung} |')
    zeilen += ['', '| Quelle | Art | Datum | Betrag | gefunden | Vorschlag |', '|---|---|---|---|---|---|']
    for quelle, art, datum, betrag, gefunden, aussage in m.fristen:
        zeilen.append(f"| {quelle} | {art} | {datum} | {betrag or '–'} | {ja(gefunden)} | {aussage or '–'} |")
    if m.anhaenge:
        zeilen += ['', '| Anhang | erwartet | im Produkt | richtig |', '|---|---|---|---|']
        zeilen += [f'| {a} | {e} | {s} | {ja(r)} |' for a, e, s, r in m.anhaenge]
    if m.geburtstage:
        zeilen += ['', '| Person | Geburtstag erwartet | gefunden | Vorschlag |', '|---|---|---|---|']
        zeilen += [f"| {a} | {d} | {ja(g)} | {s or '–'} |" for a, d, g, s in m.geburtstage]
    if m.wiederkehrend:
        zeilen += ['', '| Quelle | erwartet (Wörter) | gefunden | Vorschlag |', '|---|---|---|---|']
        zeilen += [f"| {q} | {', '.join(w)} | {ja(g)} | {s or '–'} |" for q, w, g, s in m.wiederkehrend]
    if m.geburtstage_falsch:
        zeilen += ['', '### Geburtstage ohne Erwartung', ''] + [f'- {a} ({d}): {s}' for a, d, s in m.geburtstage_falsch]
    if m.wiederkehrend_verboten or m.wk_zahlen_ohne_beleg:
        zeilen += ['', '### Verbotenes Wiederkehrendes', '']
        zeilen += [f'- {q}: „{s}“, Zahlen ohne Beleg: {", ".join(z) or "–"}' for q, s, z in m.wk_zahlen_ohne_beleg]
        zeilen += [f'- {q}: „{s}“ (die Quelle hat nichts Wiederkehrendes)' for q, s in m.wiederkehrend_verboten]
    if m.wiederkehrend_ohne_erwartung:
        zeilen += ['', '### Wiederkehrendes ohne Erwartung', '']
        zeilen += [f'- {q} ({h}): {s}' for q, h, s in m.wiederkehrend_ohne_erwartung[:30]]
    if m.falsche_innere:
        zeilen += ['', '### Falsche innere Kreise', ''] + [f'- {a} ({h}): {b}' for a, h, b in m.falsche_innere[:30]]
    if m.zahlen_ohne_beleg or m.verbotene_fristen:
        zeilen += ['', '### Verbotene Fristvorschläge', '']
        zeilen += [f'- {q}: „{s}“, Zahlen ohne Beleg: {", ".join(z) or "–"}' for q, s, z in m.zahlen_ohne_beleg]
        zeilen += [f'- {q}: „{s}“ (die Quelle hat keine Frist)' for q, s in m.verbotene_fristen]
    if m.fristen_ohne_erwartung:
        zeilen += ['', '### Fristvorschläge ohne Erwartung', '']
        zeilen += [f'- {q} ({h}): {s}' for q, h, s in m.fristen_ohne_erwartung[:30]]
    zeilen += ['', 'Grenze: Die Regeln lesen Absender, Betreff, Anrede und ausgeschriebene Daten. Ob ein Modell danach '
               'angemessen über die Personen spricht, misst diese Stufe nicht.', '']
    return zeilen


__all__ = ['KreisTreffer', 'PrivatMessung', 'falsche_innere', 'markdown', 'messen', 'zu_dict']
