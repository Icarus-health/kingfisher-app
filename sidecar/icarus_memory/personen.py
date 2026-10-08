"""Menschen — abgeleitet, nicht gespeichert.

Ein Stabschef kennt die Menschen um den Chef herum. Icarus weiß längst, mit wem
seine Episoden zu tun hatten: `Episode.participants` steht seit der
Mittelfristschicht da und wurde bisher nur mitgeschleppt. Dieses Modul macht
daraus eine Ansicht — und **nur** eine Ansicht.

Es gibt hier keine Personentabelle, keinen Anlegen-Knopf, kein Feld, das jemand
pflegen müsste. Wer in einer aufgenommenen Notiz vorkommt, ist da; wer nirgends
mehr vorkommt, ist weg. Zwei Gründe:

- Eine eigene Ablage wäre eine zweite Wahrheit neben dem Bestand
  (Architekturgrenze 10 der Produktvision) — und sie müsste gepflegt werden.
  Genau die Arbeit, die das Programm dem Nutzer abnehmen soll.
- Was hier steht, ist jederzeit aus dem Rohmaterial neu herleitbar. Eine
  falsche Person verschwindet, indem man die Episode korrigiert, nicht indem
  jemand einen Datensatz aufräumt, von dem er nichts weiß.

## Zusammenführen, ohne zu raten

Ein Mensch ist zuerst seine **Adresse** (`identitaet.py`): Gleiche Adresse,
dieselbe Person, gleich wie der Anzeigename lautet. Namen sind Aliasse.
Gleicher Name mit verschiedenen Adressen sind zwei Personen, bis der Nutzer sie
zusammenführt (`person_merges.py`). Ein Name ohne Adresse (Notiz, Transkript)
wird nur zugeordnet, wenn genau eine Adresse ihn trägt; sonst bleibt er offen.
Kein Fuzzy-Matching, keine Vornamen-Heuristik, kein „Dr. Meier ist vermutlich
Thomas Meier“. Die eigenen Adressen („ich“) sind keine Kontakte.

Zwei Einträge für einen Menschen sind ärgerlich und in einer Sekunde als
Dopplung zu erkennen. Zwei Menschen in einem Eintrag sind ein Schaden, den
niemand bemerkt — bis eine Zusage der einen Person der anderen zugeschrieben
wird. Die Asymmetrie entscheidet die Regel.

## Warum `recall()` und nicht `search()`

Die Aussagen zu einer Person kommen über `store.recall()`. Der Unterschied ist
nicht kosmetisch: `search()` liefert auch Ersetztes, Abgelaufenes und
Widerrufenes. Auf einer Personenseite stünde das dann als geltende Wahrheit
über einen Menschen — genau der Fehler, den der Widerruf verhindern soll.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

# Die Monatsnamen kommen aus dem Briefing statt hier ein zweites Mal zu stehen.
# Zwei Listen driften auseinander, und dann heißt derselbe Monat an zwei Stellen
# der Oberfläche verschieden.
from .episodes import EpisodeKind, EpisodeState

from . import identitaet
from .datumstext import MONATE
from .identitaet import Nennung, Verzeichnis, name_schluessel
from .model import FREMDE_HERKUNFT
from .people_quality import ist_sammelpostfach, lokalteil

#: Höchstens drei Themen. Mehr ist keine Auskunft mehr, sondern eine Wolke.
MAX_THEMEN = 3

#: Wie viele Aussagen zu einer Person höchstens gezeigt werden.
MAX_AUSSAGEN = 8


#: Zahlwörter für die Tage, die als Tage ausgesprochen werden. Darüber steht
#: das Datum — „vor neunundzwanzig Tagen“ sagt kein Mensch.
ZAHLWORT = {3: "drei", 4: "vier", 5: "fünf", 6: "sechs"}


@dataclass
class Person:
    """Ein Mensch, wie er sich aus dem Bestand ergibt.

    Nichts davon wird geschrieben. Jedes Feld ist eine Antwort auf eine Frage,
    die ein Stabschef beantworten können muss, bevor sein Chef in ein Gespräch
    geht: Wer ist das, wann hatten wir zuletzt miteinander zu tun, worum ging
    es, was wissen wir, und was liegt bei ihm.
    """

    name: str
    """Die Schreibweise, die am häufigsten vorkommt."""

    episoden_anzahl: int
    """In wie vielen Quellen dieser Mensch vorkommt (auch nur erwähnt)."""
    letzter_kontakt: datetime | None
    tage_her: int | None

    kontakt_text: str = ""
    """Wann zuletzt Kontakt war, in Worten: „gestern“, „vor drei Tagen“,
    „am 7. August“.

    Hier und nicht in der Oberfläche, weil die Formulierung eine Entscheidung
    ist und keine Darstellung: Eine nackte Zahl („3“, „29 Tage“) zwingt den
    Leser zu rechnen, und gerechnet wird hier nicht.
    """

    kontakte: int = 0
    """In wie vielen Quellen er selbst beteiligt war (`ist_kontakt`); nur sie sind „belegte Kontakte“."""

    themen: list[str] = field(default_factory=list)
    offene_aufgaben: list[dict[str, Any]] = field(default_factory=list)
    aussagen: list[dict[str, Any]] = field(default_factory=list)

    herkuenfte: list[str] = field(default_factory=list)
    """Aus welchen Quellenarten die gemeinsamen Episoden stammen.

    Damit kann die aufrufende Schicht entscheiden, ob dieser Mensch nur aus
    fremdem Material bekannt ist — siehe `nur_von_aussen`.
    """

    id: str = ""
    """Der Anker: `a:<adresse>` oder, ohne Adresse, `n:<name>`."""

    adressen: list[str] = field(default_factory=list)
    """Alle Adressen dieses Menschen. Höchstens eine, solange der Nutzer nicht
    zusammengeführt hat: Zwei Adressen sind zwei Menschen."""

    namen: list[str] = field(default_factory=list)
    """Alle Anzeigenamen (Aliasse), häufigste zuerst."""

    unterscheidung: str = ""
    """Die Domäne der Adresse; sie trennt zwei gleichnamige Menschen für den Leser."""

    anzeige: str = ""
    """Der Name, bei gleichnamigen Menschen mit Domäne: „Alex Winter (ifeh-hessen.example)“."""

    rollen: dict[str, int] = field(default_factory=dict)
    """In wie vielen Quellen er schrieb (`von`), Empfänger (`an`) oder Cc war."""

    offen_mit: list[str] = field(default_factory=list)
    """Nur bei einem Namen ohne Adresse: die Adressen, zwischen denen die
    Nennung nicht zu entscheiden war. Dann ist diese Person „offen“."""

    def verweis(self) -> str:
        """Womit die Ansicht diesen Menschen wieder aufruft: die Adresse, sonst der Name."""
        return self.adressen[0] if self.adressen else self.name

    def nur_von_aussen(self) -> bool:
        """Kennt Icarus diesen Menschen ausschließlich aus fremdem Material?

        Dann ist schon der Name eine fremde Behauptung: Niemand hat bestätigt,
        dass es diese Person gibt, eine Mail hat es behauptet. Das gehört
        gekennzeichnet.

        Bewusst „alle“ und nicht „irgendeine“: Was alles markiert, markiert
        nichts. Sobald der Nutzer selbst einmal von diesem Menschen erzählt
        hat, ist er kein Fremdbefund mehr.
        """
        return bool(self.herkuenfte) and all(
            h in FREMDE_HERKUNFT for h in self.herkuenfte
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "episoden_anzahl": self.episoden_anzahl,
            "kontakte": self.kontakte,
            "letzter_kontakt": (
                self.letzter_kontakt.astimezone().isoformat()
                if self.letzter_kontakt else None
            ),
            "tage_her": self.tage_her,
            "kontakt_text": self.kontakt_text,
            "themen": list(self.themen),
            "offene_aufgaben": list(self.offene_aufgaben),
            "aussagen": list(self.aussagen),
            "herkuenfte": list(self.herkuenfte),
            "nur_von_aussen": self.nur_von_aussen(),
            "id": self.id,
            "adressen": list(self.adressen),
            "namen": list(self.namen),
            "unterscheidung": self.unterscheidung,
            "anzeige": self.anzeige or self.name,
            "rollen": dict(self.rollen),
            "offen_mit": list(self.offen_mit),
            "verweis": self.verweis(),
        }


def schluessel(name: str) -> str:
    """Woran zwei Nennungen als derselbe Mensch erkannt werden.

    `strip()` und Groß-/Kleinschreibung, sonst nichts. Die eine Stelle, an der
    diese Regel steht — wer sie ändern will, ändert sie hier und sieht dabei,
    was oben im Modulkopf dazu steht.
    """
    return name.strip().casefold()


def wartet_auf(aufgabe: Any, name: str) -> bool:
    """Nur die ausdrückliche Zuordnung belegt, bei wem eine Aufgabe liegt."""
    zugesagt = getattr(aufgabe, "wartet_auf", None)
    if zugesagt:
        return schluessel(str(zugesagt)) == schluessel(name)

    return False


def _datum(zeit: datetime, jetzt: datetime) -> str:
    """»am 7. August« — und mit Jahr, wenn es ein anderes ist."""
    jahr = "" if zeit.year == jetzt.year else f" {zeit.year}"
    return f"am {zeit.day}. {MONATE[zeit.month - 1]}{jahr}"


def _kontakt_text(tage: int | None, zeitpunkt: datetime | None,
                  jetzt: datetime) -> str:
    """Wann zuletzt — als Satzteil, nie als Zahl."""
    if tage is None or zeitpunkt is None:
        return ""
    if tage <= 0:
        return "heute"
    if tage == 1:
        return "gestern"
    if tage == 2:
        return "vorgestern"
    if tage in ZAHLWORT:
        return f"vor {ZAHLWORT[tage]} Tagen"
    return _datum(zeitpunkt, jetzt)


def _tage_her(zeitpunkt: datetime, jetzt: datetime) -> int:
    """Ganze Kalendertage dazwischen.

    Nach Kalendertagen und nicht nach 24-Stunden-Schritten: Wer gestern Abend
    geschrieben hat, hat gestern geschrieben, auch wenn erst zwanzig Stunden
    vergangen sind.
    """
    a, b = zeitpunkt, jetzt
    if (a.tzinfo is None) != (b.tzinfo is None):
        a = a.replace(tzinfo=None)
        b = b.replace(tzinfo=None)
    return max(0, (b.date() - a.date()).days)


def ist_kontakt(episode: Any, nennung: Nennung) -> bool:
    """War dieser Mensch an der Quelle selbst beteiligt (Fremdprobe 2, Befund 21)?

    Ja bei Mails und Terminen (Absender, Empfänger, Gäste), bei Mitschriften und Besprechungsnotizen (Teilnehmer).
    Nein, wenn der Nutzer im Gespräch mit Kingfisher, in einer eigenen Angabe oder Korrektur nur über ihn spricht,
    und bei dem, was Kingfisher selbst abgeleitet hat: Das ist kein Kontakt, auch wenn der Name darin steht.
    """
    from .episodes import EIGENE_HERKUNFT
    return episode.provenance.source_type.value not in EIGENE_HERKUNFT or nennung.rolle in ("von", "an", "cc")


def _ist_fremd(herkunft: dict[str, Any] | None) -> bool:
    if not herkunft:
        return False
    return herkunft.get("source_type") in FREMDE_HERKUNFT


@dataclass
class _Rohbau:
    """Was sich beim Durchgang durch die Episoden für einen Anker ansammelt."""

    schreibweisen: Counter = field(default_factory=Counter)
    themen: Counter = field(default_factory=Counter)
    rollen: Counter = field(default_factory=Counter)
    herkuenfte: set[str] = field(default_factory=set)
    anzahl: int = 0
    kontakte: int = 0
    """Quellen, an denen dieser Mensch selbst beteiligt war (Absender, Empfänger, Teilnehmer)."""
    letzter: datetime | None = None
    """Der jüngste solche Kontakt; ein Gespräch, in dem der Nutzer nur über ihn spricht, zählt nicht."""
    adresse: str = ""
    offen_mit: tuple[str, ...] = ()
    episoden: list[str] = field(default_factory=list)
    """Kennungen der Quellen, in denen dieser Mensch vorkommt (für Profile)."""
    kontakt_episoden: set[str] = field(default_factory=set)
    """Quellen, an denen dieser Mensch selbst beteiligt war."""

    def zaehlen(self, nennung: Nennung, wann: datetime | None, herkunft: str,
                themen: list[str], episode_id: str = "", kontakt: bool = True) -> None:
        if episode_id:
            self.episoden.append(episode_id)
        if nennung.name:
            self.schreibweisen[nennung.name] += 1
        self.rollen[nennung.rolle] += 1
        self.anzahl += 1
        self.herkuenfte.add(herkunft)
        for marke in themen:
            self.themen[marke] += 1
        if not kontakt:
            return
        self.kontakte += 1
        if episode_id:
            self.kontakt_episoden.add(episode_id)
        if wann is not None and (self.letzter is None or wann > self.letzter):
            self.letzter = wann


@dataclass
class _Bestand:
    """Alle Anker mit ihrem Rohbau, dazu das Verzeichnis, aus dem sie entstanden."""

    rohbauten: dict[str, _Rohbau]
    verzeichnis: Verzeichnis


def _graph_person_id(anker: str) -> str:
    """Stabile Graph-Kennung derselben Adresse oder Namensnennung."""
    from .graph import person_id_fuer
    return person_id_fuer(anker)


def _sammeln(episodes: Any, *, workspace: Any = None, eigene: Any = (),
             bestaetigte_mitglieder: set[str] | None = None,
             jetzt: datetime | None = None) -> _Bestand:
    """Geht das Rohmaterial einmal durch und legt die Menschen nach Anker zusammen.

    Nennungen mit Adresse werden sofort dem Anker zugeschlagen. Namen ohne
    Adresse warten, bis alle Adressen bekannt sind: Erst dann lässt sich
    sagen, ob genau ein Mensch diesen Namen trägt. Mit `jetzt` zählt ein Termin,
    der noch bevorsteht, nicht als Kontakt; seine Gäste bleiben als Anker und
    Aliasse im Verzeichnis, denn eine Adresse ist auch dort eine Adresse.
    """
    projektnamen: dict[str, str] = {}
    if workspace is not None:
        # Nur den Namen, nie die Kennung: „p-3f9a1c“ ist kein Thema, das ein
        # Mensch wiedererkennt.
        for projekt in workspace.projects(include_closed=True):
            projektnamen[projekt.id] = projekt.name

    eigene = list(eigene)
    bestaetigte_mitglieder = bestaetigte_mitglieder or set()
    verzeichnis = Verzeichnis()
    rohbauten: dict[str, _Rohbau] = {}
    wartende: list[tuple[Nennung, datetime | None, str, list[str], str, bool]] = []
    # Der ganze Bestand: Wer zuletzt vor zwei Jahren schrieb, gehört trotzdem
    # ins Verzeichnis. Seitenweise gelesen, damit der Speicher begrenzt bleibt.
    for episode in episodes.each_episode():
        if episode.state is EpisodeState.IGNORED:
            continue
        # Ein Importzeitpunkt belegt keinen Kontaktzeitpunkt.
        wann = episode.occurred_at
        # Ein Termin, der noch bevorsteht, ist noch kein Kontakt: Er darf weder
        # den „letzten Kontakt“ in die Zukunft schieben noch mitzählen.
        bevorstehend = (episode.kind is EpisodeKind.EVENT and jetzt is not None
                        and (wann is None or _als_zeitpunkt(wann, jetzt) > jetzt))
        herkunft = episode.provenance.source_type.value
        themen = list(episode.tags)
        if episode.project_id and episode.project_id in projektnamen:
            themen.append(projektnamen[episode.project_id])
        gezaehlt: set[str] = set()
        for nennung in identitaet.nennungen(episode, eigene):
            if nennung.ich:
                continue
            # A service mailbox can display a real person's name, but the
            # address does not prove that person. Keep the source untouched and
            # omit this claim from both the person view and its alias directory.
            if (nennung.adresse and ist_sammelpostfach(lokalteil(nennung.adresse))
                    and _graph_person_id("a:" + nennung.adresse) not in bestaetigte_mitglieder):
                continue
            verzeichnis.aufnehmen(nennung)
            if bevorstehend:
                continue
            if nennung.adresse:
                anker = "a:" + nennung.adresse
                # Jeder Mensch zählt je Quelle einmal, auch wenn er in An und Cc steht.
                if anker in gezaehlt:
                    continue
                gezaehlt.add(anker)
                eintrag = rohbauten.setdefault(anker, _Rohbau(adresse=nennung.adresse))
                eintrag.zaehlen(nennung, wann, herkunft, themen, episode.id, ist_kontakt(episode, nennung))
            elif nennung.name:
                wartende.append((nennung, wann, herkunft, themen, episode.id, ist_kontakt(episode, nennung)))

    for nennung, wann, herkunft, themen, episode_id, kontakt in wartende:
        aufloesung = verzeichnis.aufloesen(nennung)
        eintrag = rohbauten.setdefault(aufloesung.schluessel, _Rohbau())
        if not eintrag.adresse:
            eintrag.offen_mit = aufloesung.offen
        # Je Quelle einmal: Ein Name, der zweimal im selben Transkript oder
        # zusätzlich zur Adresse in derselben Mail steht, zählt einmal.
        if episode_id not in eintrag.episoden:
            eintrag.zaehlen(nennung, wann, herkunft, themen, episode_id, kontakt)
    return _Bestand(rohbauten, verzeichnis)


def _als_zeitpunkt(wann: datetime, jetzt: datetime) -> datetime:
    """`wann` mit derselben Zeitzonenart wie `jetzt`, damit beide vergleichbar sind."""
    if (wann.tzinfo is None) != (jetzt.tzinfo is None):
        return wann.replace(tzinfo=jetzt.tzinfo)
    return wann


def _haeufigste(zaehler: Counter, wieviele: int) -> list[str]:
    """Die häufigsten Einträge, bei Gleichstand alphabetisch.

    Die zweite Bedingung ist kein Schönheitsfehler: Ohne sie hängt die
    Reihenfolge an der Einlesereihenfolge, und dieselbe Person sieht bei jedem
    Aufruf anders aus.
    """
    posten = sorted(zaehler.items(), key=lambda p: (-p[1], p[0].casefold()))
    return [name for name, _ in posten[:wieviele]]


def _bauen(anker: str, rohbau: _Rohbau, *, verzeichnis: Verzeichnis, mehrdeutige_namen: set[str],
           tasks: Any, store: Any, jetzt: datetime) -> Person:
    namen = verzeichnis.namen(rohbau.adresse) if rohbau.adresse else []
    for name in _haeufigste(rohbau.schreibweisen, len(rohbau.schreibweisen)):
        if name not in namen:
            namen.append(name)
    name = namen[0] if namen else rohbau.adresse

    tage = _tage_her(rohbau.letzter, jetzt) if rohbau.letzter else None

    # Was an den Namen hängt (Aufgaben, „wartet auf“, Aussagen), gehört nur dem,
    # der ihn allein trägt. Bei zwei gleichnamigen Menschen wäre jede Zuordnung
    # geraten — und eine Zusage der einen der anderen zugeschrieben.
    eindeutig = (not rohbau.offen_mit
                 and not any(name_schluessel(n) in mehrdeutige_namen for n in namen))
    aufgaben: list[dict[str, Any]] = []
    if tasks is not None and eindeutig:
        aufgaben = [
            a.to_dict() for a in tasks.open_tasks(limit=300)
            if any(wartet_auf(a, alias) for alias in (namen or [name]))
        ]

    aussagen: list[dict[str, Any]] = []
    if store is not None and eindeutig and name:
        # `recall`, nicht `search`: siehe Modulkopf.
        for aussage in store.recall(name, limit=MAX_AUSSAGEN):
            daten = aussage.to_dict()
            daten["fremd"] = _ist_fremd(daten.get("provenance"))
            aussagen.append(daten)

    domaene = identitaet.unterscheidung(rohbau.adresse)
    return Person(
        name=name,
        episoden_anzahl=rohbau.anzahl,
        kontakte=rohbau.kontakte,
        letzter_kontakt=rohbau.letzter,
        tage_her=tage,
        kontakt_text=_kontakt_text(tage, rohbau.letzter, jetzt),
        themen=_haeufigste(rohbau.themen, MAX_THEMEN),
        offene_aufgaben=aufgaben,
        aussagen=aussagen,
        herkuenfte=sorted(rohbau.herkuenfte),
        id=anker,
        adressen=[rohbau.adresse] if rohbau.adresse else [],
        namen=namen,
        unterscheidung=domaene,
        anzeige=name if eindeutig or not domaene else f"{name} ({domaene})",
        rollen=dict(rohbau.rollen),
        offen_mit=list(rohbau.offen_mit),
    )


def _mehrdeutige_namen(bestand: _Bestand) -> set[str]:
    """Namen, die mehr als einem Menschen gehören (nach Anker, nicht nach Schreibweise).

    Nur Menschen mit Adresse zählen: Ein Name ohne Adresse, der sich nicht
    zuordnen ließ, ist eine offene Erwähnung und kein zweiter Träger.
    """
    traeger: dict[str, set[str]] = {}
    for anker, rohbau in bestand.rohbauten.items():
        if not rohbau.adresse:
            continue
        for name in bestand.verzeichnis.namen(rohbau.adresse):
            traeger.setdefault(name_schluessel(name), set()).add(anker)
    return {name for name, menschen in traeger.items() if len(menschen) > 1}


def _aktive_zusammenfuehrungen(merges: Any) -> list[dict[str, Any]]:
    return [record for record in (merges or ())
            if isinstance(record, dict) and not record.get("undone_at")
            and isinstance(record.get("id"), str)
            and isinstance(record.get("label"), str)
            and isinstance(record.get("members"), list)]


def _zusammengefuehrte_personen(menschen: list[Person], bestand: _Bestand,
                                merges: list[dict[str, Any]], *, tasks: Any,
                                store: Any, jetzt: datetime) -> list[Person]:
    """Apply explicit groups to this projection, without restoring absent sources."""
    verbleibend = {person.id: person for person in menschen}
    gruppen: list[Person] = []
    for record in merges:
        ids = {member.get("id") for member in record["members"]
               if isinstance(member, dict) and isinstance(member.get("id"), str)}
        mitglieder = [person for person in verbleibend.values()
                      if _graph_person_id(person.id) in ids]
        if not mitglieder:
            continue
        rohbauten = [bestand.rohbauten[person.id] for person in mitglieder
                     if person.id in bestand.rohbauten]
        if not rohbauten:
            continue
        rohbau = _Rohbau()
        adressen = set()
        for person, quelle in zip(mitglieder, rohbauten):
            rohbau.schreibweisen.update(quelle.schreibweisen)
            rohbau.themen.update(quelle.themen)
            rohbau.rollen.update(quelle.rollen)
            rohbau.herkuenfte.update(quelle.herkuenfte)
            rohbau.episoden.extend(quelle.episoden)
            rohbau.kontakt_episoden.update(quelle.kontakt_episoden)
            adressen.update(person.adressen)
            if quelle.letzter is not None and (rohbau.letzter is None or quelle.letzter > rohbau.letzter):
                rohbau.letzter = quelle.letzter
        rohbau.episoden = list(dict.fromkeys(rohbau.episoden))
        rohbau.anzahl = len(rohbau.episoden)
        rohbau.kontakte = len(rohbau.kontakt_episoden)
        person = _bauen(record["id"], rohbau, verzeichnis=bestand.verzeichnis,
                        mehrdeutige_namen=_mehrdeutige_namen(bestand), tasks=tasks,
                        store=store, jetzt=jetzt)
        label = record["label"].strip() or person.name
        gruppen.append(replace(
            person,
            name=label,
            id=record["id"],
            adressen=sorted(adressen),
            namen=list(dict.fromkeys([*person.namen, label])),
            unterscheidung="",
            anzeige=label,
            offen_mit=[],
        ))
        for member in mitglieder:
            verbleibend.pop(member.id, None)
    return [*verbleibend.values(), *gruppen]


class Mehrdeutig(Exception):
    """Ein Name gehört mehreren Menschen; `kandidaten` sind alle, ohne Auswahl."""

    def __init__(self, name: str, kandidaten: list[Person]) -> None:
        super().__init__(f"„{name}“ ist mehrdeutig")
        self.name = name
        self.kandidaten = kandidaten


def alle(
    *,
    episodes: Any,
    tasks: Any = None,
    store: Any = None,
    jetzt: datetime,
    workspace: Any = None,
    eigene: Any = (),
    confirmed_merges: Any = (),
) -> list[Person]:
    """Alle Menschen aus dem Rohmaterial, jüngster Kontakt zuerst.

    Die Sortierung ist die Aussage der Liste: Wen ich gestern gesprochen habe,
    ist wahrscheinlicher gemeint als wer vor zwei Jahren einmal vorkam. Eine
    alphabetische Liste wäre ein Telefonbuch, und ein Telefonbuch hilft nur
    dem, der den Namen schon kennt.

    `eigene` sind die Adressen des Nutzers; sie zählen nie als Kontakt, auch
    in Quellen, die vor der Rollenangabe aufgenommen wurden.
    """
    merges = _aktive_zusammenfuehrungen(confirmed_merges)
    bestaetigte_mitglieder = {member["id"] for record in merges for member in record["members"]
                              if isinstance(member, dict) and isinstance(member.get("id"), str)}
    bestand = _sammeln(episodes, workspace=workspace, eigene=eigene,
                       bestaetigte_mitglieder=bestaetigte_mitglieder, jetzt=jetzt)
    mehrdeutig = _mehrdeutige_namen(bestand)
    menschen = [
        _bauen(anker, rohbau, verzeichnis=bestand.verzeichnis, mehrdeutige_namen=mehrdeutig,
               tasks=tasks, store=store, jetzt=jetzt)
        for anker, rohbau in bestand.rohbauten.items()
    ]
    menschen = _zusammengefuehrte_personen(menschen, bestand, merges, tasks=tasks,
                                           store=store, jetzt=jetzt)
    # Ohne Zeitangabe ganz nach hinten, sonst stünde ein Mensch ohne
    # Kontaktdatum vor dem, mit dem gerade gesprochen wurde.
    menschen.sort(
        key=lambda p: (p.letzter_kontakt is None, -(p.letzter_kontakt.timestamp()
                                                    if p.letzter_kontakt else 0),
                       p.name.casefold(), p.id)
    )
    return menschen


def _anker_zu(bestand: _Bestand, angabe: str) -> list[str]:
    """Die Anker, zu denen eine Angabe passt; Regeln siehe `finden_mit_quellen`."""
    adresse = identitaet.mail_address(angabe)
    gesucht = name_schluessel(angabe) if not adresse else ""
    if not adresse and not gesucht:
        return []
    if adresse:
        return ["a:" + adresse] if "a:" + adresse in bestand.rohbauten else []
    gefunden = []
    for anker, rohbau in bestand.rohbauten.items():
        alias = list(rohbau.schreibweisen)
        if rohbau.adresse:
            alias += bestand.verzeichnis.namen(rohbau.adresse)
        if gesucht in {name_schluessel(n) for n in alias}:
            gefunden.append(anker)
    mit_adresse = [a for a in gefunden if a.startswith("a:")]
    return mit_adresse or gefunden


def finden_mit_quellen(
    angabe: str,
    *,
    episodes: Any,
    tasks: Any = None,
    store: Any = None,
    jetzt: datetime,
    workspace: Any = None,
    eigene: Any = (),
) -> list[tuple[Person, list[str]]]:
    """Alle Menschen, die zu einer Angabe passen, je mit den Kennungen ihrer Quellen.

    Die Angabe ist eine Adresse, ein Name oder „Name <adresse>“. Eine Adresse
    trifft genau einen Menschen. Ein Name trifft jeden, der ihn als Alias
    trägt — auch mehrere. Namen ohne Adresse, die sich nicht zuordnen ließen
    (`offen_mit`), zählen nur, wenn sonst niemand passt: Sie sind Erwähnungen,
    keine eigene Person neben den Adressträgern.
    """
    bestand = _sammeln(episodes, workspace=workspace, eigene=eigene, jetzt=jetzt)
    mehrdeutig = _mehrdeutige_namen(bestand)
    return [
        (_bauen(anker, bestand.rohbauten[anker], verzeichnis=bestand.verzeichnis,
                mehrdeutige_namen=mehrdeutig, tasks=tasks, store=store, jetzt=jetzt),
         list(bestand.rohbauten[anker].episoden))
        for anker in _anker_zu(bestand, angabe)
    ]


def finden(angabe: str, **kwargs: Any) -> list[Person]:
    """Wie `finden_mit_quellen`, nur die Menschen."""
    return [person for person, _ in finden_mit_quellen(angabe, **kwargs)]


def eine(
    name: str,
    *,
    episodes: Any,
    tasks: Any = None,
    store: Any = None,
    jetzt: datetime,
    workspace: Any = None,
    eigene: Any = (),
    confirmed_merges: Any = (),
) -> Person | None:
    """Ein Mensch, oder nichts.

    Nichts heißt: Der Name kommt in keiner Episode vor. Eine leere Person
    zurückzugeben wäre schlimmer — dann sähe die Oberfläche eine Seite über
    jemanden, von dem Icarus nichts weiß, und der Nutzer hielte die Leere für
    eine Auskunft.

    Passt der Name auf mehrere Menschen, ist keiner der richtige: Es wird
    `Mehrdeutig` ausgelöst, mit allen Kandidaten. Die Adresse wählt aus.
    """
    if confirmed_merges:
        adresse = identitaet.mail_address(name)
        gesucht = name_schluessel(name) if not adresse else ""
        kandidaten = [person for person in alle(
            episodes=episodes, tasks=tasks, store=store, jetzt=jetzt,
            workspace=workspace, eigene=eigene, confirmed_merges=confirmed_merges,
        ) if (adresse and adresse in person.adressen) or
            (gesucht and gesucht in {name_schluessel(alias) for alias in [person.name, *person.namen]})]
    else:
        kandidaten = finden(name, episodes=episodes, tasks=tasks, store=store, jetzt=jetzt,
                            workspace=workspace, eigene=eigene)
    if not kandidaten:
        return None
    if len(kandidaten) > 1:
        raise Mehrdeutig(name, kandidaten)
    return kandidaten[0]


__all__ = ["MAX_THEMEN", "Mehrdeutig", "Person", "alle", "eine", "finden", "finden_mit_quellen",
           "schluessel", "wartet_auf"]
