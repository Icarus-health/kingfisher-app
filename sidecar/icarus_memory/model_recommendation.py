"""Modellempfehlung je Rolle nach Gerät: reine Funktionen, kein Netz, keine Datei.

Ziel: Der Nutzer muss keine Modellnamen kennen. Aus Plattform, Chip und
Arbeitsspeicher wird je Rolle ein passendes lokales Modell vorgeschlagen.

Das ist eine **Vorauswahl, keine Messung.** Was auf dem Zielgerät wirklich
taugt, entscheidet die Messlatte
(`python -m messlatte lauf --modell ollama:NAME`), nicht diese Tabelle.

Die Tabelle `KATALOG` ist die einzige Stelle, die Modellnamen kennt. Sie ist
datiert (`KATALOG_STAND`): Modelle veralten schnell, und ein Katalog ohne Datum
wird geglaubt, lange nachdem er stimmt. Zum Pflegen genügt es, Zeilen zu
ändern; keine Logik hängt an einem Namen.
"""
from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field, replace
from typing import Any
from .device_profile import memory_plan_gb

# Wann die Tabelle zuletzt gegen die Ollama-Bibliothek und die Messlatte geprüft
# wurde. Bei jeder Änderung an KATALOG mitziehen.
KATALOG_STAND = "2026-10-06"

# Aufgaben des Stabschefs. Die Reihenfolge ist die der Anzeige.
ROLLEN = ("frage", "antwort", "pruefung", "hintergrund", "einbettung")

# Speicherstufen in GB. Ein Gerät fällt auf die höchste Stufe, die es erreicht.
STUFEN = (8, 16, 24, 32, 64, 128)

# Separater Grafikspeicher gehört nicht zum RAM-Budget anderer Programme.
_GPU_NUTZBARER_ANTEIL = 0.85


@dataclass(frozen=True)
class KatalogEintrag:
    """Eine Zeile der Modelltabelle: dieses Modell für diese Rolle auf diesen Stufen."""

    rolle: str
    stufen: tuple[int, ...]
    name: str  # Ollama-Name, wie er bei `ollama pull` steht
    groesse_gb: float  # Platz auf der Festplatte
    speicher_gb: float  # Arbeitsspeicher im Betrieb einschließlich Kontext (Schätzung)
    art: str  # "moe" | "dicht" | "klein" | "einbettung"
    begruendung: str  # ein Satz in Alltagssprache
    alternative: bool = False  # Ausweichmöglichkeit statt Vorauswahl


def _e(rolle, stufen, name, groesse, speicher, art, begruendung, alternative=False):
    return KatalogEintrag(rolle, tuple(stufen), name, groesse, speicher, art, begruendung, alternative)


# Die Tabelle. Stand: KATALOG_STAND (Recherche September und Messwerte Oktober 2026).
# Mixture-of-Experts-Modelle (MoE, wenige aktive Parameter) sind auf
# Apple Silicon mit viel gemeinsamem Speicher das beste Allround-Modell:
# Qualität eines großen Modells bei der Geschwindigkeit eines kleinen.
KATALOG: tuple[KatalogEintrag, ...] = (
    # -- frage: klein und schnell, strukturierte Ausgabe (3–8B-Klasse) --
    _e("frage", (8,), "qwen3.5:2b", 2.7, 4, "klein",
       "Sehr klein und schnell; genügt, um eine Frage in Stichworte zu übersetzen."),
    _e("frage", (16, 24), "qwen3.5:4b", 3.4, 6, "klein",
       "Klein und schnell, antwortet in unter einer Sekunde und hält das Ausgabeformat."),
    _e("frage", (32, 64, 128), "qwen3.5:9b", 6.6, 10, "klein",
       "Schnell und zuverlässiger im Ausgabeformat als die kleinen Modelle."),
    _e("frage", (16, 24, 32, 64, 128), "lfm2.5:8b", 5.0, 7, "moe",
       "Für schnelles, verlässliches Ausgabeformat gebaut (8B, 1B aktiv); als Vergleich messen.", alternative=True),
    # -- antwort: belegt, kurz, wenige Sekunden --
    _e("antwort", (8,), "qwen3.5:4b", 3.4, 6, "klein",
       "Das größte Modell, das auf diesem Rechner noch flüssig läuft."),
    _e("antwort", (16, 24), "qwen3.5:9b", 6.6, 10, "dicht",
       "Ordentliche Antworten in wenigen Sekunden bei moderatem Speicherbedarf."),
    _e("antwort", (32, 64, 128), "qwen3.6:35b", 24.0, 27, "moe",
       "Mixture-of-Experts: Qualität eines großen Modells, dabei etwa so schnell wie ein kleines."),
    _e("antwort", (32, 64), "qwen3.5:27b", 17.0, 20, "dicht",
       "Dichtes Modell mit ähnlicher Qualität, aber deutlich langsamer.", alternative=True),
    _e("antwort", (16, 24, 32, 64, 128), "gemma4:12b", 8.0, 10, "dicht",
       "Kleiner und schneller; lässt tagsüber mehr Speicher frei. Ob die Sätze gleich gut sind, sagt die Messlatte.",
       alternative=True),
    # -- pruefung: zweites Tor der Satzprüfung, ein Urteil je Satz (ja, nein, unklar); klein, läuft bei jeder Antwort --
    # Größen sind Schätzungen nach der Modellseite, nicht gegen `ollama pull` geprüft (docs/40, Messlauf D).
    _e("pruefung", (8,), "tev1:0.8b", 0.6, 1.5, "klein",
       "Sehr kleines Entscheidungsmodell; sagt je Satz nur ja oder nein und kostet kaum Speicher."),
    _e("pruefung", (16, 24, 32, 64, 128), "bespoke-minicheck:7b", 4.7, 6, "klein",
       "Für Faktenprüfung gebaut: sagt, ob eine Textstelle einen Satz stützt."),
    _e("pruefung", (16, 24, 32, 64, 128), "tev1:4b", 4.5, 4.7, "klein",
       "Kleineres Entscheidungsmodell; bei rund 4,7 GB Betriebsspeicher im 2050er Kontext. Genauigkeit mit der Messlatte prüfen.", alternative=True),
    # -- hintergrund: gründlich, darf langsam sein, läuft nachts --
    _e("hintergrund", (8,), "qwen3.5:4b", 3.4, 6, "klein",
       "Das größte Modell, das hier noch Platz hat; ordnet langsamer und gröber ein."),
    _e("hintergrund", (16, 24, 32), "qwen3.5:9b", 6.6, 10, "dicht",
       "Sorgfältiger als die kleinen Modelle; die Einordnung darf ruhig dauern."),
    _e("hintergrund", (64,), "qwen3.6:35b", 24.0, 27, "moe",
       "Mixture-of-Experts: gründlich genug für Akten und Einordnung, in vertretbarer Zeit."),
    _e("hintergrund", (32, 64), "qwen3.5:27b", 17.0, 20, "dicht",
       "Dichtes größeres Modell als ausdrücklich wählbare Alternative; gründlich, aber langsam.", alternative=True),
    _e("hintergrund", (64, 128), "nemotron-3.5-lightning:30b", 25.5, 27, "moe",
       "Gemessen: 25,43 GB Gewichte und rund 26,7 GB Laufzeitspeicher ohne Kontextbegrenzung; für 32-GB-Macs zu knapp.",
       alternative=True),
    _e("hintergrund", (128,), "qwen3.5:122b", 81.0, 90, "moe",
       "Sehr großes Mixture-of-Experts-Modell; nachts die gründlichste Einordnung."),
    # -- einbettung: Suche nach Bedeutung, dauerhaft und lokal --
    _e("einbettung", STUFEN, "bge-m3", 1.2, 2, "einbettung",
       "Findet Sinnverwandtes auch auf Deutsch; klein genug für jeden Rechner."),
    _e("einbettung", STUFEN, "qwen3-embedding:0.6b", 0.7, 2, "einbettung",
       "Neuer und für Deutsch vermutlich treffsicherer als bge-m3; ein Wechsel baut den Bedeutungsindex neu.",
       alternative=True),
)


@dataclass(frozen=True)
class Geraet:
    """Was über den Rechner bekannt ist. Fehlt etwas, ist es `None`, nie geraten."""

    plattform: str = "unbekannt"  # macos | windows | linux | unbekannt
    chip: str | None = None
    arbeitsspeicher_gb: float | None = None
    grafikspeicher_gb: float | None = None  # nur wo getrennt vom Arbeitsspeicher (Windows/Linux)
    festplatte_frei_gb: float | None = None  # freier Platz dort, wo Ollama seine Modelle ablegt

    @property
    def bekannt(self) -> bool:
        return self.arbeitsspeicher_gb is not None

    @property
    def modellspeicher_gb(self) -> float | None:
        """Speicher, den ein Modell bekommen kann (einheitlicher Speicher am Mac).

        Mit getrenntem Grafikspeicher zählt dieser, sonst der Arbeitsspeicher.
        """
        if self.grafikspeicher_gb is not None and self.plattform != "macos":
            return self.grafikspeicher_gb
        return self.arbeitsspeicher_gb

    @property
    def modellbudget_gb(self) -> float | None:
        """Dieselbe RAM-Reserve wie die Gerätehilfe; separate GPUs haben ihr eigenes Budget."""
        if self.grafikspeicher_gb is not None and self.plattform != "macos":
            return self.grafikspeicher_gb * _GPU_NUTZBARER_ANTEIL
        return None if self.arbeitsspeicher_gb is None else memory_plan_gb(self.arbeitsspeicher_gb)[1]


def geraet_aus_profil(profil: dict) -> Geraet:
    """Baut ein `Geraet` aus der Antwort von `load_device_profile`."""
    speicher = profil.get("memory_gb")
    plattform = profil.get("platform")
    return Geraet(
        plattform=plattform if plattform in {"macos", "windows", "linux"} else "unbekannt",
        chip=profil.get("chip"),
        arbeitsspeicher_gb=float(speicher) if isinstance(speicher, (int, float)) else None,
        grafikspeicher_gb=(float(profil["gpu_memory_gb"])
                           if isinstance(profil.get("gpu_memory_gb"), (int, float)) else None),
        festplatte_frei_gb=(float(profil["disk_free_gb"])
                            if isinstance(profil.get("disk_free_gb"), (int, float))
                            and not isinstance(profil.get("disk_free_gb"), bool) else None),
    )


def stufe_fuer(geraet: Geraet) -> int:
    """Höchste Stufe, die der Speicher erreicht. Unbekannt: die kleinste, sichere."""
    gb = geraet.modellspeicher_gb
    if gb is None:
        return STUFEN[0]
    erreicht = [s for s in STUFEN if gb >= s * 0.95]  # 31,9 GB gelten als 32
    return erreicht[-1] if erreicht else STUFEN[0]


@dataclass(frozen=True)
class Empfehlung:
    rolle: str
    modell: KatalogEintrag
    alternativen: tuple[KatalogEintrag, ...] = field(default_factory=tuple)
    stufe: int = STUFEN[0]
    passt_vermutlich: bool = True
    orchester_hinweis: str = ""  # ein Satz, wenn ein kleineres Modell gewählt wurde, damit alles zusammen passt


def _passt(eintrag: KatalogEintrag, geraet: Geraet) -> bool:
    budget = geraet.modellbudget_gb
    return True if budget is None else eintrag.speicher_gb <= budget


def empfehle(geraet: Geraet, rolle: str) -> Empfehlung:
    """Die Vorauswahl für eine Rolle. Wirft `KeyError` bei unbekannter Rolle."""
    if rolle not in ROLLEN:
        raise KeyError(rolle)
    stufe = stufe_fuer(geraet)
    zeilen = [e for e in KATALOG if e.rolle == rolle and stufe in e.stufen]
    if not zeilen:  # Tabellenlücke: nächstkleinere Stufe, sonst die kleinste Zeile der Rolle
        zeilen = [e for e in KATALOG if e.rolle == rolle and min(e.stufen) <= stufe] \
            or [e for e in KATALOG if e.rolle == rolle]
    erste = [e for e in zeilen if not e.alternative]
    wahl = erste[0]
    return Empfehlung(rolle=rolle, modell=wahl,
                      alternativen=tuple(e for e in zeilen if e.alternative),
                      stufe=stufe, passt_vermutlich=_passt(wahl, geraet))


def ausweichwahl(rolle: str, geraet: Geraet, ausser: Collection[str] = ()) -> tuple[KatalogEintrag, ...]:
    """Was „Anderes Modell nehmen“ als Nächstes versucht (Fremdprobe, Befund 11), in dieser Reihenfolge.

    Zuerst die Alternativen dieser Stufe, dann die Vorauswahl kleinerer Stufen (größte zuerst), zuletzt die übrigen
    Modelle der Aufgabe, kleinste zuerst; jeweils nur, was in den Speicher passt, jedes Modell einmal. `ausser`: schon
    versuchte oder empfohlene Namen.
    """
    stufe = stufe_fuer(geraet)
    eigene = [e for e in KATALOG if e.rolle == rolle and stufe in e.stufen and e.alternative]
    kleinere = sorted((e for e in KATALOG if e.rolle == rolle and not e.alternative and max(e.stufen) < stufe),
                      key=lambda e: -max(e.stufen))
    uebrige = sorted((e for e in KATALOG if e.rolle == rolle), key=lambda e: e.speicher_gb)
    gesehen = {normalisiere(n) for n in ausser}
    wahl = []
    for eintrag in (*eigene, *kleinere, *uebrige):
        if normalisiere(eintrag.name) in gesehen or not _passt(eintrag, geraet):
            continue
        gesehen.add(normalisiere(eintrag.name))
        wahl.append(eintrag)
    return tuple(wahl)


def empfehle_alle(geraet: Geraet) -> dict[str, Empfehlung]:
    """Die Vorauswahl für alle Rollen, die tagsüber und nachts zusammen auf das Gerät passt.

    Jede Rolle für sich (`empfehle`) kann passen und alle zusammen doch nicht: Antwort, Frage, Prüfung und
    Einbettung sind tagsüber gleichzeitig geladen, nachts Hintergrund und Einbettung. Passt eine
    Summe nicht, wird das größte Modell der beteiligten Rollen gegen die nächstkleinere Wahl
    getauscht, bis es passt (tagsüber die Prüfung zuerst, wenn das reicht, sonst Antwort oder Frage;
    nachts der Hintergrund, `_verkleinere_tag`); jede getauschte
    Rolle trägt dazu einen Satz (`orchester_hinweis`). Die Einbettung bleibt, wie sie ist.
    """
    basis = {rolle: empfehle(geraet, rolle) for rolle in ROLLEN}
    eintraege = {rolle: rec.modell for rolle, rec in basis.items()}
    neu, tag = _verkleinere_tag(eintraege, geraet, lambda b: b["passt_tag"] is not False)
    neu, nacht = _verkleinere(neu, geraet, ("hintergrund",), "speicher_gb", lambda b: b["passt_nacht"] is not False)
    if not (tag or nacht):
        return basis
    bedarf = orchester_bedarf(neu, geraet)
    grund = {"tag": f"Antworten, Fragen, Prüfung und Suche tagsüber zusammen in den Arbeitsspeicher passen "
                    f"(etwa {gb_text(bedarf['tag_gb'])} von {gb_text(bedarf['nutzbar_gb'])} GB)",
             "nacht": f"das Ordnen im Hintergrund und die Suche nachts zusammen in den Arbeitsspeicher passen "
                      f"(etwa {gb_text(bedarf['nacht_gb'])} von {gb_text(bedarf['nutzbar_gb'])} GB)"}
    ergebnis = dict(basis)
    for tageszeit, getauscht in (("tag", tag), ("nacht", nacht)):
        for rolle, urspruenglich, ersatz in _zusammengefasst(getauscht):
            rec = basis[rolle]
            andere = tuple(e for e in (rec.modell, *rec.alternativen)
                           if normalisiere(e.name) != normalisiere(ersatz.name))
            ergebnis[rolle] = replace(
                rec, modell=ersatz, alternativen=andere, passt_vermutlich=_passt(ersatz, geraet),
                orchester_hinweis=f"{ersatz.name} statt {urspruenglich.name}: kleiner gewählt, damit {grund[tageszeit]}.")
    return ergebnis


def _zusammengefasst(getauscht: list[_Tausch]) -> list[_Tausch]:
    """Mehrere Tauschschritte derselben Rolle zu einem: von der ersten Wahl zur letzten."""
    je_rolle: dict[str, _Tausch] = {}
    for rolle, alt, neu in getauscht:
        je_rolle[rolle] = (rolle, je_rolle[rolle][1], neu) if rolle in je_rolle else (rolle, alt, neu)
    return list(je_rolle.values())


def eintrag_fuer(rolle: str, name: str) -> KatalogEintrag | None:
    """Katalogzeile zu Rolle und Ollama-Name (`:latest` wird nicht unterschieden)."""
    ziel = normalisiere(name)
    for e in KATALOG:
        if e.rolle == rolle and normalisiere(e.name) == ziel:
            return e
    return None


def model_memory_gb(name: str) -> float | None:
    """Known model size across roles; a role switch does not reduce its footprint."""
    sizes = [e.speicher_gb for e in KATALOG if normalisiere(e.name) == normalisiere(name)]
    return max(sizes) if sizes else None


def normalisiere(name: str) -> str:
    """`bge-m3` und `bge-m3:latest` sind für Ollama dasselbe Modell."""
    name = (name or "").strip()
    return name[: -len(":latest")] if name.endswith(":latest") else name




# -- Speicherbedarf des Orchesters ------------------------------------------------------------
#
# Ein Modell je Rolle genügt nicht als Prüfung: Tagsüber sind Antwort, Frage, Prüfung und Einbettung
# gleichzeitig geladen (die Prüfung läuft bei jeder Antwort), nachts Hintergrund und Einbettung. Und jedes
# Modell liegt auf der Festplatte.

TAG_ROLLEN = ("antwort", "frage", "pruefung", "einbettung")
NACHT_ROLLEN = ("hintergrund", "einbettung")
# Diese Rollen dürfen für einen Tausch kleiner werden. Die Einbettung nicht: ein Wechsel baut den
# Bedeutungsindex neu, das nimmt man nicht für ein paar hundert Megabyte in Kauf.
TAG_TAUSCHBAR = ("antwort", "frage", "pruefung")
TAUSCHBAR = (*TAG_TAUSCHBAR, "hintergrund")

# So viel Festplatte bleibt frei, wenn alles geladen ist (Ollama schreibt beim Laden erst, dann prüft es).
FESTPLATTE_RESERVE_GB = 2.0


def _modell_von(rolle: str, angabe) -> tuple[KatalogEintrag | None, str]:
    """Katalogzeile und Name zu einer Angabe: Empfehlung, Katalogzeile, Rollenwahl oder bloßer Name.

    Eine leere Angabe ergibt `(None, "")` und zählt nicht; ein Name außerhalb des Katalogs
    `(None, name)`: seine Größe ist unbekannt und wird nie geraten.
    """
    if isinstance(angabe, Empfehlung):
        return angabe.modell, angabe.modell.name
    if isinstance(angabe, KatalogEintrag):
        return angabe, angabe.name
    name = angabe if isinstance(angabe, str) else getattr(angabe, "modell", "")
    name = name.strip() if isinstance(name, str) else ""
    return (eintrag_fuer(rolle, name) if name else None), name


def _nutzbar_gb(geraet: Geraet) -> float | None:
    return geraet.modellbudget_gb


def _summe(eintraege: dict[str, KatalogEintrag], rollen: tuple[str, ...], feld: str,
           ausser: frozenset[str] = frozenset()) -> float:
    """Summe je **verschiedenem** Modell der genannten Rollen; ein Modell in zwei Rollen wird einmal geladen."""
    gesehen: dict[str, float] = {}
    for rolle in rollen:
        e = eintraege.get(rolle)
        if e is not None and normalisiere(e.name) not in ausser:
            gesehen[normalisiere(e.name)] = getattr(e, feld)
    return sum(gesehen.values())


def _passt_summe(summe: float, grenze: float | None, unvollstaendig: bool) -> bool | None:
    """Ja nur, wenn es sicher passt; Nein, sobald schon das Bekannte zu viel ist; sonst unbekannt."""
    if grenze is None:
        return None
    if summe > grenze:
        return False
    return None if unvollstaendig else True


def orchester_bedarf(auswahl: Mapping[str, Any], geraet: Geraet, vorhanden: Collection[str] = ()) -> dict[str, Any]:
    """Was das Orchester zusammen braucht, und ob es auf dieses Gerät passt.

    `auswahl` ordnet Rollen ihrem Modell zu (Empfehlungen, Katalogzeilen, Rollenwahlen oder Namen).
    `vorhanden` sind Namen, die schon auf der Festplatte liegen: Sie belegen Platz, brauchen aber keinen neuen.

    * `tag_gb`     Arbeitsspeicher, wenn Antwort, Frage, Prüfung und Einbettung gleichzeitig geladen sind
    * `nacht_gb`   Arbeitsspeicher für Hintergrund und Einbettung
    * `festplatte_gb` Platz aller Modelle; `festplatte_noch_gb` davon, was noch zu laden ist
    * `passt_*`    `True`/`False`, oder `None`, wenn es sich nicht sagen lässt (Gerät oder Modell
                   unbekannt). Nie geraten.
    """
    eintraege: dict[str, KatalogEintrag] = {}
    unbekannte: list[str] = []
    for rolle in ROLLEN:
        if rolle not in auswahl:
            continue
        eintrag, name = _modell_von(rolle, auswahl[rolle])
        if eintrag is not None:
            eintraege[rolle] = eintrag
        elif name:
            unbekannte.append(name)
    unvollstaendig = bool(unbekannte)
    nutzbar = _nutzbar_gb(geraet)
    da = frozenset(normalisiere(n) for n in vorhanden)
    tag = _summe(eintraege, TAG_ROLLEN, "speicher_gb")
    nacht = _summe(eintraege, NACHT_ROLLEN, "speicher_gb")
    platte = _summe(eintraege, ROLLEN, "groesse_gb")
    noch = _summe(eintraege, ROLLEN, "groesse_gb", ausser=da)
    frei = geraet.festplatte_frei_gb
    return {
        "tag_gb": tag, "nacht_gb": nacht, "festplatte_gb": platte, "festplatte_noch_gb": noch,
        "nutzbar_gb": nutzbar, "festplatte_frei_gb": frei,
        "passt_tag": _passt_summe(tag, nutzbar, unvollstaendig),
        "passt_nacht": _passt_summe(nacht, nutzbar, unvollstaendig),
        "passt_festplatte": _passt_summe(noch + FESTPLATTE_RESERVE_GB, frei, unvollstaendig),
        "unbekannte_modelle": unbekannte,
    }


def festplatte_reicht(groesse_gb: float, geraet: Geraet) -> bool | None:
    """Reicht der freie Platz für ein Modell dieser Größe (mit Reserve)? `None`, wenn der Platz unbekannt ist."""
    frei = geraet.festplatte_frei_gb
    return None if frei is None else groesse_gb + FESTPLATTE_RESERVE_GB <= frei


_Tausch = tuple[str, KatalogEintrag, KatalogEintrag]  # Rolle, statt dieses, dieses


def kleinere_wahl(rolle: str, aktuell: KatalogEintrag, geraet: Geraet, feld: str) -> KatalogEintrag | None:
    """Die nächstkleinere Wahl für die Rolle: zuerst eine ausdrückliche Alternative, sonst ein Modell einer kleineren Stufe."""
    stufe = stufe_fuer(geraet)
    kleiner = [e for e in KATALOG if e.rolle == rolle and min(e.stufen) <= stufe
               and normalisiere(e.name) != normalisiere(aktuell.name) and getattr(e, feld) < getattr(aktuell, feld)]
    for zeilen in ([e for e in kleiner if e.alternative], [e for e in kleiner if not e.alternative]):
        if zeilen:
            return max(zeilen, key=lambda e: (getattr(e, feld), e.groesse_gb, e.speicher_gb))
    return None


def _verkleinere(eintraege: dict[str, KatalogEintrag], geraet: Geraet, rollen: tuple[str, ...], feld: str,
                 fertig: Callable[[dict[str, Any]], bool],
                 vorhanden: Collection[str] = ()) -> tuple[dict[str, KatalogEintrag], list[_Tausch]]:
    """Tauscht das größte Modell gegen das nächstkleinere, bis `fertig` gilt oder nichts Kleineres übrig ist."""
    neu = dict(eintraege)
    getauscht: list[_Tausch] = []
    while not fertig(orchester_bedarf(neu, geraet, vorhanden)):
        kandidaten = [(getattr(neu[r], feld), r) for r in rollen if r in neu
                      and kleinere_wahl(r, neu[r], geraet, feld) is not None]
        if not kandidaten:
            break
        rolle = max(kandidaten)[1]
        ersatz = kleinere_wahl(rolle, neu[rolle], geraet, feld)
        getauscht.append((rolle, neu[rolle], ersatz))
        neu[rolle] = ersatz
    return neu, getauscht


def _verkleinere_tag(eintraege: dict[str, KatalogEintrag], geraet: Geraet, fertig: Callable[[dict[str, Any]], bool],
                     vorhanden: Collection[str] = ()) -> tuple[dict[str, KatalogEintrag], list[_Tausch]]:
    """Tagsüber: zuerst die Prüfung kleiner, wenn das allein reicht; sonst das größte Modell von Antwort, Frage, Prüfung.

    Ein kleineres Prüfmodell verwirft im Zweifel (fail closed); ein kleineres Antwortmodell schreibt mehr falsche
    Sätze. Deshalb gibt die Prüfung zuerst Speicher her, aber nur so weit, wie es nötig ist: Reicht es auch mit dem
    kleinsten Prüfmodell nicht, wird zuerst das größte Modell kleiner (meist die Antwort), und die Prüfung erst danach.
    """
    neu = dict(eintraege)
    getauscht: list[_Tausch] = []
    while not fertig(orchester_bedarf(neu, geraet, vorhanden)):
        rolle = None
        if "pruefung" in neu and kleinere_wahl("pruefung", neu["pruefung"], geraet, "speicher_gb") is not None:
            kleinste, _ = _verkleinere(neu, geraet, ("pruefung",), "speicher_gb", lambda b: False, vorhanden)
            if fertig(orchester_bedarf(kleinste, geraet, vorhanden)):
                rolle = "pruefung"
        if rolle is None:
            kandidaten = [(neu[r].speicher_gb, r) for r in TAG_TAUSCHBAR if r in neu
                          and kleinere_wahl(r, neu[r], geraet, "speicher_gb") is not None]
            if not kandidaten:
                break
            rolle = max(kandidaten)[1]
        ersatz = kleinere_wahl(rolle, neu[rolle], geraet, "speicher_gb")
        # Equal-size alternatives can have different total costs: reuse an
        # already loaded model before shrinking unrelated roles further.
        loaded = {normalisiere(neu[r].name) for r in TAG_ROLLEN if r in neu and r != rolle}
        shared = [e for e in KATALOG if e.rolle == rolle and min(e.stufen) <= stufe_fuer(geraet)
                  and e.speicher_gb == ersatz.speicher_gb and normalisiere(e.name) in loaded]
        for candidate in shared:
            if fertig(orchester_bedarf({**neu, rolle: candidate}, geraet, vorhanden)):
                ersatz = candidate
                break
        getauscht.append((rolle, neu[rolle], ersatz))
        neu[rolle] = ersatz
    return neu, getauscht


def gb_text(zahl: float) -> str:
    """Eine Größe in GB, wie man sie liest: `13`, `6,6`."""
    return f"{zahl:.0f}" if abs(zahl - round(zahl)) < 0.05 else f"{zahl:.1f}".replace(".", ",")


def orchester_hinweise(auswahl: Mapping[str, Any], geraet: Geraet, titel: Mapping[str, str],
                       vorhanden: Collection[str] = ()) -> list[str]:
    """Ruhige Sätze in Alltagssprache für alles, was nicht passt, mit dem Vorschlag, was stattdessen.

    Leer, wenn alles passt oder sich nichts sagen lässt. `titel` übersetzt Rollen in Alltagsnamen.
    """
    eintraege = {r: e for r in ROLLEN if r in auswahl and (e := _modell_von(r, auswahl[r])[0]) is not None}
    bedarf = orchester_bedarf(auswahl, geraet, vorhanden)
    saetze: list[str] = []

    def stattdessen(rollen: tuple[str, ...], feld: str, schluessel: str) -> str:
        fertig = lambda b: b[schluessel] is not False  # noqa: E731
        _, tausche = (_verkleinere_tag(eintraege, geraet, fertig, vorhanden) if rollen == TAG_TAUSCHBAR
                      else _verkleinere(eintraege, geraet, rollen, feld, fertig, vorhanden))
        if not tausche:
            return " Im Katalog gibt es dafür nichts Kleineres; bitte Platz schaffen."
        return "".join(f" Kleiner: {neu.name} statt {alt.name} für „{titel.get(rolle, rolle)}“."
                       for rolle, alt, neu in _zusammengefasst(tausche))  # eine Rolle, ein Satz, auch nach mehreren Schritten

    if bedarf["passt_tag"] is False:
        saetze.append(f"Tagsüber brauchen Antworten, Fragen, Prüfung und Suche zusammen etwa {gb_text(bedarf['tag_gb'])} GB "
                      f"Arbeitsspeicher, nutzbar sind etwa {gb_text(bedarf['nutzbar_gb'])} GB."
                      + stattdessen(TAG_TAUSCHBAR, "speicher_gb", "passt_tag"))
    if bedarf["passt_nacht"] is False:
        saetze.append(f"Nachts brauchen das Ordnen im Hintergrund und die Suche zusammen etwa {gb_text(bedarf['nacht_gb'])} GB "
                      f"Arbeitsspeicher, nutzbar sind etwa {gb_text(bedarf['nutzbar_gb'])} GB."
                      + stattdessen(("hintergrund",), "speicher_gb", "passt_nacht"))
    if bedarf["passt_festplatte"] is False:
        saetze.append(f"Die noch zu ladenden Modelle brauchen etwa {gb_text(bedarf['festplatte_noch_gb'])} GB Festplatte, "
                      f"frei sind etwa {gb_text(bedarf['festplatte_frei_gb'])} GB (zwei bleiben für das System frei)."
                      + stattdessen(TAUSCHBAR, "groesse_gb", "passt_festplatte"))
    return saetze


__all__ = [
    "FESTPLATTE_RESERVE_GB", "KATALOG", "KATALOG_STAND", "NACHT_ROLLEN", "ROLLEN", "STUFEN", "TAG_ROLLEN", "TAG_TAUSCHBAR", "Empfehlung",
    "Geraet", "KatalogEintrag", "empfehle", "empfehle_alle", "eintrag_fuer", "festplatte_reicht", "gb_text", "geraet_aus_profil",
    "ausweichwahl", "kleinere_wahl", "model_memory_gb", "normalisiere", "orchester_bedarf", "orchester_hinweise", "stufe_fuer",
]
