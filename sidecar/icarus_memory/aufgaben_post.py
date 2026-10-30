"""Aufgaben folgen der Post: Mailbezug schlägt vor, er beweist keine Erfüllung.

Eigene Mails liefern nur den bestehenden Bestätigungsvorschlag „Erledigt?“.
Wörter in Betreff, Text oder Anhang ordnen die Mail zu; sie belegen weder Versand
bestimmter Unterlagen noch Erfüllung der Aufgabe. Der Erledigungsgrund nennt
entsprechend die Bestätigung des Nutzers.

Ein Wartestatus geht nur automatisch zurück zu „bei dir“, wenn eine bekannte
exakte Gegenseitenadresse und Verlauf oder tragende Wörter zusammenpassen.
Bloße Namensgleichheit liefert höchstens einen Vorschlag; eine widersprechende
bekannte Adresse schließt den Treffer aus. Mehrdeutige Empfänger, Rundmails,
über 90 Tage überfällige Aufgaben und Gleichstände ändern nichts automatisch.

Jede neue Mail wird einmal geprüft, auch nach Neustart; der Erstbestand bleibt
unberührt. Bestätigung prüft die geltenden Quellen erneut. Rückgängig stellt den
vorigen Zustand her und trennt Aufgabe und Mail dauerhaft. Logbuch und Geschichte
enthalten den Änderungsgrund; keine zusätzliche Wissensablage und kein Modell.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable

from . import logbuch
from .akten import _FUELLWOERTER, verlaeufe
from .datumstext import tag_und_monat
from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeError, EpisodeKind, mail_address
from .kontakte import anzeigename
from .lexical import _STOP_WORDS
from .model import SourceType, user_timezone
from .personen import schluessel
from .proposals import Evidence, ProposalError, ProposalKind, ProposalState
from .tasks import Task, TaskStatus
from .word_forms import umschrift_gleich

logger = logging.getLogger(__name__)

PROPOSED_BY = 'aufgaben_post'
#: Mehr Empfänger sind eine Rundmail: nur ein Vorschlag, nie automatisch.
MAX_EMPFAENGER = 5
#: Eine seit so vielen Tagen überfällige Aufgabe erledigt die Post nie von selbst.
ALT_TAGE = 90
#: So lange steht eine Änderung durch die Post in der Akte unter „Braucht dich“ (mit Rückgängig).
SICHTBAR_TAGE = 14
#: Höchstens so viele Mails je Takt.
JE_TAKT = 200

_TOKEN = re.compile(r'[0-9A-Za-zÀ-ÖØ-öø-ÿ]+')
#: Wörter, die in Aufgabentiteln sagen, was zu tun ist, nicht worum es geht. Ein Treffer darauf trägt nichts.
_HANDLUNGSWOERTER = frozenset({
    'schicken', 'senden', 'schreiben', 'anrufen', 'antworten', 'prüfen', 'pruefen', 'klären', 'klaeren', 'erledigen',
    'nachfassen', 'nachhaken', 'fragen', 'nachfragen', 'besorgen', 'machen', 'bezahlen', 'überweisen', 'ueberweisen',
    'freigeben', 'buchen', 'melden', 'rückmelden', 'zusagen', 'absagen', 'vereinbaren', 'organisieren', 'erinnern',
    'kontaktieren', 'zurückrufen', 'erstellen', 'einreichen', 'abgeben', 'weiterleiten', 'bestellen', 'zahlen',
    'holen', 'bringen', 'liefern', 'mitnehmen', 'vorbereiten', 'lesen', 'teilen', 'bestätigen', 'bestaetigen',
    'besprechen', 'telefonieren', 'sagen', 'geben', 'bitten', 'checken', 'übernehmen', 'uebernehmen', 'anfragen',
    'termin', 'mail', 'email', 'nachricht', 'antwort', 'rückmeldung', 'rueckmeldung', 'info', 'infos', 'frage',
    'thema', 'sache', 'aufgabe', 'dinge', 'wegen', 'noch', 'heute', 'morgen', 'woche', 'montag', 'dienstag',
    'mittwoch', 'donnerstag', 'freitag', 'samstag', 'sonntag'})


# -- Tragende Wörter ---------------------------------------------------------------


def tragende_woerter(titel: str, *, namen: Iterable[str] = ()) -> list[str]:
    """Die Wörter eines Aufgabentitels, die sagen, worum es geht: Substantive und Zahlen, ohne Füll-, Handlungs- und
    Stoppwörter und ohne die Namen der Beteiligten (die stehen in jeder Mail an sie)."""
    ausgeschlossen = {t.casefold() for name in namen for t in _TOKEN.findall(str(name or ''))}
    ergebnis: list[str] = []
    gesehen: set[str] = set()
    for wort in _TOKEN.findall(str(titel or '')):
        klein = wort.casefold()
        if klein in gesehen:
            continue
        if wort.isdigit():
            if len(wort) >= 2:
                ergebnis.append(wort)
                gesehen.add(klein)
            continue
        if (len(klein) < 4 or klein in _STOP_WORDS or klein in _FUELLWOERTER or klein in _HANDLUNGSWOERTER
                or klein in ausgeschlossen):
            continue
        ergebnis.append(wort)
        gesehen.add(klein)
    return ergebnis


def _gleich(a: str, b: str) -> bool:
    """Dasselbe Wort in Umschrift, auch gebeugt: „Rechnung“ und „Rechnungen“, „Vertraege“ und „Verträge“."""
    a, b = umschrift_gleich(a), umschrift_gleich(b)
    if a == b:
        return True
    if a.isdigit() or b.isdigit():
        return False
    kurz, lang = sorted((a, b), key=len)
    return len(kurz) >= 5 and lang.startswith(kurz) and len(lang) - len(kurz) <= 3


def woerter_in(woerter: Iterable[str], texte: Iterable[str]) -> list[str]:
    """Welche der Wörter in den Texten vorkommen (Betreff, Text, Namen der Anhänge), in der Reihenfolge der Wörter."""
    tokens = {t.casefold() for text in texte for t in _TOKEN.findall(str(text or ''))}
    return [wort for wort in woerter if any(_gleich(wort, t) for t in tokens)]


# -- Die Mail und ihre Treffer ------------------------------------------------------


@dataclass
class _Mail:
    episode: Any
    richtung: str
    """`von_mir` oder `an_mich`."""
    absender: dict[str, str]
    empfaenger: list[dict[str, str]]
    """An, Cc und Bcc ohne die eigenen Adressen."""
    zeit: datetime
    texte: list[str]


@dataclass
class Treffer:
    aufgabe: Task
    art: str
    """`erledigt` (Bestätigungsvorschlag zur eigenen Mail) oder `zurueck` (Antwort löst das Warten auf)."""
    verlauf: bool
    woerter: list[str]
    wer: dict[str, str]
    sicher: bool
    """Wahr, wenn die Zuordnung sicher genug ist, um selbst zu handeln; sonst nur ein Vorschlag."""

    @property
    def rang(self) -> tuple[int, int]:
        return (int(self.verlauf), len(self.woerter))


def _person(eintrag: dict[str, Any] | None) -> dict[str, str] | None:
    if not eintrag:
        return None
    return {'adresse': str(eintrag.get('adresse') or ''), 'name': str(eintrag.get('name') or '')}


def _aus_text(text: str) -> dict[str, str]:
    return {'adresse': mail_address(text), 'name': anzeigename(text)}


def _name(wer: dict[str, str] | None) -> str:
    if not wer:
        return ''
    return wer.get('name') or wer.get('adresse') or ''


def _ort(zeit: datetime) -> datetime:
    zone = user_timezone()
    return zeit.astimezone(zone) if zone and zeit.tzinfo else zeit


def _aufzaehlung(woerter: list[str]) -> str:
    teile = [f'„{w}“' for w in woerter[:3]]
    return teile[0] if len(teile) == 1 else ', '.join(teile[:-1]) + ' und ' + teile[-1]


class Lauf:
    """Prüft neue Mails gegen die offenen Aufgaben; wendet sichere Zuordnungen an, legt unsichere als Vorschlag vor."""

    def __init__(self, tasks: Any, episodes: Any, proposals: Any, *, eigene: Callable[[], Iterable[str]],
                 jetzt: Callable[[], datetime] | None = None) -> None:
        self.tasks, self.episodes, self.proposals = tasks, episodes, proposals
        self._eigene = eigene
        self._jetzt = jetzt or (lambda: datetime.now(timezone.utc))

    # -- Durchlauf --

    def schritt(self, limit: int = JE_TAKT) -> dict[str, int]:
        """Ein Takt: die nächsten neuen Mails, jede einmal. Der erste Durchlauf setzt nur den Stand (kein Rückblick)."""
        bericht = {'geprueft': 0, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
        stand = self.tasks.post_stand()
        if stand is None:
            self.tasks.post_stand_setzen(self.episodes.letzte_zeile())
            return bericht
        letzte = stand
        for zeile, episode in self.episodes.mails_ab(stand, limit):
            letzte = zeile
            if self.tasks.post_mail_verarbeitet(episode.id, episode.digest):
                continue
            bericht['geprueft'] += 1
            try:
                ergebnis = self.verarbeiten(episode)
            except Exception:  # noqa: BLE001 - fail closed: keine Änderung, die Mail gilt als geprüft, nichts hängt
                logger.exception('Aufgaben nach der Post: Mail konnte nicht geprüft werden')
                ergebnis = {}
            finally:
                self.tasks.post_mail_merken(episode.id, episode.digest)
            for name in ('erledigt', 'zurueck', 'vorschlaege'):
                bericht[name] += int(ergebnis.get(name, 0))
        if letzte != stand:
            self.tasks.post_stand_setzen(letzte)
        return bericht

    def verarbeiten(self, episode: Any) -> dict[str, int]:
        """Eine Mail gegen die offenen Aufgaben: höchstens eine Änderung, der Rest Vorschläge."""
        ergebnis = {'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
        mail = self._mail(episode)
        if mail is None:
            return ergebnis
        treffer = self._treffer(mail, self.tasks.open_tasks(limit=None))
        if not treffer:
            return ergebnis
        sichere = sorted((t for t in treffer if t.sicher), key=lambda t: t.rang, reverse=True)
        automatisch = sichere[0] if sichere and (len(sichere) == 1 or sichere[0].rang > sichere[1].rang) else None
        for t in treffer:
            if t is automatisch:
                self._anwenden(t, mail, wie='verlauf' if t.verlauf else 'person')
                ergebnis[t.art] += 1
            elif self._vorschlagen(t, mail):
                ergebnis['vorschlaege'] += 1
        return ergebnis

    # -- Lesen der Mail --

    def _mail(self, episode: Any) -> _Mail | None:
        if (not self._geltend(episode) or getattr(episode.kind, 'value', episode.kind) != EpisodeKind.MESSAGE.value
                or episode.provenance.source_type is not SourceType.EMAIL
                or episode.state in AUSGEBLENDETE_ZUSTAENDE):
            return None
        eigene = {mail_address(a) for a in self._eigene() if mail_address(a)}
        kontakte = list(episode.contacts or [])
        von = next((k for k in kontakte if k.get('rolle') == 'von'), None)
        if von is None:
            if not episode.participants:
                return None
            von = {**_aus_text(episode.participants[0]), 'rolle': 'von'}
            von['ich'] = bool(von['adresse'] and von['adresse'] in eigene)
            empfaenger = [_aus_text(p) for p in episode.participants[1:]]
        else:
            empfaenger = [_person(k) or {} for k in kontakte if k.get('rolle') in ('an', 'cc', 'bcc') and not k.get('ich')]
        absender = _person(von) or {'adresse': '', 'name': ''}
        if not absender['adresse']:
            return None
        ich = bool(von.get('ich')) or absender['adresse'] in eigene
        empfaenger = [e for e in empfaenger if e.get('adresse') and e['adresse'] not in eigene]
        zeit = episode.occurred_at or episode.recorded_at
        texte = [episode.title or '', episode.body or '', *self.episodes.anhang_titel(episode.id)]
        return _Mail(episode, 'von_mir' if ich else 'an_mich', absender, empfaenger, zeit, texte)

    def _geltend(self, episode: Any) -> bool:
        """Nur der aktuelle, nicht entzogene Originalbeleg darf eine Aufgabe ändern."""
        try:
            stand = self.episodes.support_snapshot(episode.id)
            return bool(stand and stand.current())
        except (EpisodeError, ValueError):
            return False

    def _quelle(self, task: Task) -> Any | None:
        ref = task.provenance.source_ref or ''
        if not ref.startswith('episode:'):
            return None
        try:
            quelle = self.episodes.get(ref[len('episode:'):])
        except EpisodeError:
            return None
        return quelle if (self._geltend(quelle)
                          and getattr(quelle.kind, 'value', quelle.kind) == EpisodeKind.MESSAGE.value) else None

    def _gegenseite(self, quelle: Any | None, eigene: set[str]) -> dict[str, str] | None:
        """Die Person der Aufgabe: wer die Quellmail schrieb, bei einer eigenen Mail ihr einziger fremder Empfänger."""
        if quelle is None:
            return None
        kontakte = list(quelle.contacts or [])
        von = next((k for k in kontakte if k.get('rolle') == 'von'), None)
        if von is None:
            if not quelle.participants:
                return None
            absender = _aus_text(quelle.participants[0])
            andere = [_aus_text(p) for p in quelle.participants[1:]]
            von_ich = absender['adresse'] in eigene
        else:
            absender = _person(von) or {'adresse': '', 'name': ''}
            andere = [_person(k) or {} for k in kontakte if k.get('rolle') in ('an', 'cc', 'bcc') and not k.get('ich')]
            von_ich = bool(von.get('ich')) or absender['adresse'] in eigene
        if not von_ich:
            return absender if absender['adresse'] else None
        andere = [a for a in andere if a.get('adresse') and a['adresse'] not in eigene]
        return andere[0] if len(andere) == 1 else None

    @staticmethod
    def _name_passt(wartet_auf: str, absender: dict[str, str]) -> bool:
        """„Anna“ passt zu „Anna Berg“: der ganze Name, die Adresse oder ein Teil des Namens (Vor- oder Nachname)."""
        ziel = schluessel(str(wartet_auf or ''))
        if not ziel:
            return False
        name = str(absender.get('name') or '')
        kandidaten = {schluessel(name), schluessel(absender.get('adresse') or '')}
        kandidaten |= {schluessel(t) for t in name.replace(',', ' ').split()}
        return ziel in kandidaten - {''}

    def _alt(self, task: Task) -> bool:
        return task.due is not None and (self._jetzt() - task.due) > timedelta(days=ALT_TAGE)

    def _treffer(self, mail: _Mail, offen: Iterable[Task]) -> list[Treffer]:
        eigene = {mail_address(a) for a in self._eigene() if mail_address(a)}
        aufgaben = [t for t in offen if t.status is TaskStatus.OPEN
                    and not self.tasks.post_getrennt(t.id, mail.episode.id)]
        quellen = {t.id: self._quelle(t) for t in aufgaben}
        ids = list(dict.fromkeys([mail.episode.id, *(q.id for q in quellen.values() if q is not None)]))
        faeden = verlaeufe(self.episodes, ids)
        rundmail = len(mail.empfaenger) > MAX_EMPFAENGER
        treffer: list[Treffer] = []
        for task in aufgaben:
            quelle = quellen[task.id]
            if (task.provenance.source_ref or '').startswith('episode:') and quelle is None:
                continue  # eine entzogene/ersetzte Aufgabenquelle ist kein gültiger Bezug
            if quelle is not None and quelle.id == mail.episode.id:
                continue  # die Quelle der Aufgabe erledigt sie nicht
            bezug = (quelle.occurred_at or quelle.recorded_at) if quelle is not None else task.created_at
            if bezug is not None and mail.zeit <= bezug:
                continue  # eine Mail von vor der Bitte kann sie nicht erfüllen
            im_verlauf = quelle is not None and faeden.get(quelle.id) == faeden.get(mail.episode.id)
            person = self._gegenseite(quelle, eigene)
            if mail.richtung == 'von_mir':
                if task.wartet_auf is not None:
                    continue
                an_person = person is not None and any(e.get('adresse') == person['adresse'] for e in mail.empfaenger)
                if not (im_verlauf or an_person):
                    continue
                # Der Quellabsender muss nicht Empfänger dieser Antwort sein (Weiterleitung).
                wer = next((e for e in mail.empfaenger if person and e['adresse'] == person['adresse']),
                           mail.empfaenger[0] if mail.empfaenger else {'adresse': '', 'name': ''})
                woerter = woerter_in(tragende_woerter(task.title, namen=[wer['name'], wer['adresse'].split('@')[0]]), mail.texte)
                treffer.append(Treffer(task, 'erledigt', im_verlauf, woerter, wer,
                                       sicher=False))  # Zuordnung ist kein Erfüllungsnachweis
            else:
                if task.wartet_auf is None:
                    continue  # eine fremde Mail erledigt nie, was bei dir liegt
                bekannte_adresse = mail_address(task.wartet_auf)
                if not bekannte_adresse and person is not None and self._name_passt(task.wartet_auf, person):
                    bekannte_adresse = person['adresse']
                if bekannte_adresse and bekannte_adresse != mail.absender['adresse']:
                    continue  # die bekannte Adresse schlägt auch einen passenden Vornamen/Verlauf
                von_person = bool(bekannte_adresse and bekannte_adresse == mail.absender['adresse'])
                if not (von_person or self._name_passt(task.wartet_auf, mail.absender)):
                    continue
                woerter = woerter_in(tragende_woerter(task.title, namen=[task.wartet_auf, mail.absender['name']]), mail.texte)
                treffer.append(Treffer(task, 'zurueck', im_verlauf, woerter, mail.absender,
                                       sicher=von_person and (im_verlauf or bool(woerter))
                                       and not rundmail and not self._alt(task)))
        return treffer

    # -- Grund, Anwenden, Vorschlag --

    def _grund(self, t: Treffer, mail: _Mail) -> dict[str, Any]:
        wer, tag = _name(t.wer) or 'die Gegenseite', tag_und_monat(_ort(mail.zeit))
        if t.art == 'erledigt':
            satz = f'Erledigt nach deiner Bestätigung zur Mail an {wer} vom {tag}.'
        elif t.verlauf:
            satz = f'Wieder bei dir, weil {wer} am {tag} geantwortet hat.'
        elif t.woerter:
            satz = f'Wieder bei dir, weil {wer} am {tag} zu {_aufzaehlung(t.woerter)} geschrieben hat.'
        else:
            satz = f'Wieder bei dir, weil {wer} am {tag} geschrieben hat.'
        return {'art': t.art, 'satz': satz, 'episode_id': mail.episode.id, 'mail_titel': (mail.episode.title or '')[:120],
                'wer': wer, 'datum': mail.zeit.isoformat() if mail.zeit else None,
                'am': self._jetzt().astimezone(timezone.utc).isoformat(), 'verlauf': t.verlauf, 'woerter': list(t.woerter)}

    def _anwenden(self, t: Treffer, mail: _Mail, *, wie: str) -> Task:
        grund = self._grund(t, mail)
        if t.art == 'erledigt':
            task = self.tasks.post_erledigen(t.aufgabe.id, grund, at=mail.zeit)
        else:
            task = self.tasks.post_zurueckholen(t.aufgabe.id, grund, at=mail.zeit)
        logbuch.vermerke('aufgabe_post', sorte=t.art, aufgabe=task.id, mail=mail.episode.id, wie=wie)
        return task

    def _vorschlag_text(self, t: Treffer, mail: _Mail) -> tuple[ProposalKind, str, str]:
        wer, tag = _name(t.wer) or 'die Gegenseite', tag_und_monat(_ort(mail.zeit))
        titel = (mail.episode.title or '').strip() or '(kein Betreff)'
        if t.art == 'erledigt':
            kind, statement = ProposalKind.TASK_DONE, f'Erledigt? „{t.aufgabe.title}“'
            # Ein Verlauf kann weitergeleitet sein: Er beweist keine Antwort an diesen Empfänger.
            satz = f'Du hast am {tag} an {wer} geschrieben („{titel}“). Ist die Aufgabe damit erledigt?'
            if len(mail.empfaenger) > MAX_EMPFAENGER:
                satz = f'Du hast am {tag} an {len(mail.empfaenger)} Empfänger geschrieben („{titel}“), darunter {wer}. Ist die Aufgabe damit erledigt?'
        else:
            kind, statement = ProposalKind.TASK_WAITING_RESOLVED, f'Wieder bei dir? „{t.aufgabe.title}“'
            satz = f'{wer} hat dir am {tag} geschrieben („{titel}“). Liegt die Aufgabe damit wieder bei dir?'
        return kind, statement, satz

    def _vorschlagen(self, t: Treffer, mail: _Mail) -> bool:
        kind, statement, satz = self._vorschlag_text(t, mail)
        titel = (mail.episode.title or '').strip() or '(kein Betreff)'
        _, neu = self.proposals.propose(kind, statement, satz, evidence=[Evidence(mail.episode.id, titel[:200], mail.episode.digest)],
                                        target_ref=f'task:{t.aufgabe.id}', proposed_by=PROPOSED_BY)
        return bool(neu)

    # -- Vorschläge: Liste, Annehmen, Verwerfen --

    def _paar(self, proposal: Any) -> tuple[Task, Any] | None:
        """Aufgabe und Mail eines Vorschlags, oder None, wenn eines davon nicht mehr passt (dann ist er überholt)."""
        task = self.tasks.get(str(proposal.target_ref or '')[len('task:'):]) if (proposal.target_ref or '').startswith('task:') else None
        art = 'erledigt' if proposal.kind is ProposalKind.TASK_DONE else 'zurueck'
        if task is None or task.status is not TaskStatus.OPEN or (task.wartet_auf is None) != (art == 'erledigt'):
            return None
        if not proposal.evidence:
            return None
        try:
            mail = self.episodes.get(proposal.evidence[0].episode_id)
        except EpisodeError:
            return None
        if (mail.state in AUSGEBLENDETE_ZUSTAENDE or not self._geltend(mail)
                or mail.digest != proposal.evidence[0].digest):
            return None
        if (task.provenance.source_ref or '').startswith('episode:') and self._quelle(task) is None:
            return None
        return task, mail

    def vorschlaege(self) -> list[dict[str, Any]]:
        """Die offenen Vorschläge mit Aufgabe, Mail und Satz, älteste zuerst; überholte werden dabei abgelegt."""
        ergebnis = []
        for kind in (ProposalKind.TASK_DONE, ProposalKind.TASK_WAITING_RESOLVED):
            for proposal in self.proposals.pending(kind, limit=200):
                paar = self._paar(proposal)
                if paar is None:
                    self.proposals.supersede(proposal.id)
                    continue
                task, mail = paar
                gelesen = self._mail(mail)
                treffer = self._treffer(gelesen, [task]) if gelesen is not None else []
                if not treffer:
                    self.proposals.supersede(proposal.id)
                    continue
                # Auch ältere offene Vorschläge zeigen nur den heute belegten Bezug.
                _, statement, satz = self._vorschlag_text(treffer[0], gelesen)
                ergebnis.append({
                    'id': proposal.id, 'art': 'erledigt' if kind is ProposalKind.TASK_DONE else 'zurueck',
                    'statement': statement, 'satz': satz,
                    'aufgabe': {'id': task.id, 'title': task.title, 'wartet_auf': task.wartet_auf,
                                'due': task.due.isoformat() if task.due else None},
                    'mail': {'episode_id': mail.id, 'titel': mail.title,
                             'datum': (mail.occurred_at or mail.recorded_at).isoformat()},
                    'erstellt': proposal.created_at.isoformat()})
        ergebnis.sort(key=lambda v: v['erstellt'])
        return ergebnis

    def vorschlag_annehmen(self, proposal_id: str) -> Task:
        """Dieselbe Änderung wie der Durchlauf, nur auf Klick; `ProposalError`, wenn der Vorschlag nicht (mehr) passt."""
        proposal = self.proposals.get(proposal_id)
        if proposal.kind not in (ProposalKind.TASK_DONE, ProposalKind.TASK_WAITING_RESOLVED):
            raise ProposalError('Dies ist kein Vorschlag zu einer Aufgabe nach der Post.')
        if proposal.state is not ProposalState.PENDING:
            raise ProposalError('Der Vorschlag ist nicht mehr offen.')
        paar = self._paar(proposal)
        if paar is None:
            self.proposals.supersede(proposal.id)
            raise ProposalError('Die Aufgabe oder die Mail hat sich inzwischen geändert; der Vorschlag ist überholt.')
        task, episode = paar
        mail = self._mail(episode)
        treffer = [t for t in self._treffer(mail, [task])] if mail is not None else []
        if not treffer:
            self.proposals.supersede(proposal.id)
            raise ProposalError('Die Mail passt nicht mehr zu dieser Aufgabe; der Vorschlag ist überholt.')
        geaendert = self._anwenden(treffer[0], mail, wie='vorschlag')
        self.proposals.accept(proposal.id, produced=geaendert.id)
        return geaendert

    def vorschlag_verwerfen(self, proposal_id: str) -> Any:
        proposal = self.proposals.get(proposal_id)
        if proposal.kind not in (ProposalKind.TASK_DONE, ProposalKind.TASK_WAITING_RESOLVED):
            raise ProposalError('Dies ist kein Vorschlag zu einer Aufgabe nach der Post.')
        if proposal.state is not ProposalState.PENDING:
            raise ProposalError('Der Vorschlag ist nicht mehr offen.')
        abgelehnt = self.proposals.reject(proposal.id)
        if (proposal.target_ref or '').startswith('task:') and proposal.evidence:
            self.tasks.post_trennen(proposal.target_ref[len('task:'):], proposal.evidence[0].episode_id)
        return abgelehnt

    # -- Rückgängig --

    def rueckgaengig(self, task_id: str) -> Task:
        """Stellt den Zustand vor der Änderung her; `KeyError` unbekannt, `LookupError` nichts zurückzunehmen."""
        vorher = self.tasks.get(task_id)
        if vorher is None:
            raise KeyError(task_id)
        grund = vorher.erledigt_grund or vorher.geaendert_grund or {}
        task = self.tasks.post_rueckgaengig(task_id)
        logbuch.vermerke('aufgabe_post', sorte='rueckgaengig', aufgabe=task.id, mail=grund.get('episode_id', ''))
        return task


# -- Fürs Briefing und für den Server --------------------------------------------------


def heute(tasks: Any, jetzt: datetime) -> list[dict[str, Any]]:
    """Was die Post heute (Kalendertag des Nutzers) an Aufgaben geändert hat, jüngste zuerst; fürs Briefing."""
    ort = _ort(jetzt)
    beginn = ort.replace(hour=0, minute=0, second=0, microsecond=0)
    ergebnis = []
    for task in tasks.post_aenderungen(beginn):
        grund = task.erledigt_grund or task.geaendert_grund
        if not grund:
            continue
        am = grund.get('am')
        try:
            wann = _ort(datetime.fromisoformat(str(am)))
        except ValueError:
            continue
        if wann.date() != ort.date():
            continue
        ergebnis.append({'id': task.id, 'title': task.title, 'art': grund.get('art'), 'satz': grund.get('satz', ''),
                         'wer': grund.get('wer', ''), 'episode_id': grund.get('episode_id', ''), 'am': am})
    return ergebnis


def lauf_fuer(app: Any) -> Lauf:
    from . import identitaet
    return Lauf(app.state.tasks, app.state.episodes, app.state.proposals,
                eigene=lambda: identitaet.eigene_adressen(getattr(app.state, 'settings', None)))


def schritt_fuer(app: Any) -> dict[str, int]:
    """Ein Takt nach der Mailaufnahme (auch ohne Modell, auch in der Pause: nur neue Post, deterministisch)."""
    return lauf_fuer(app).schritt()


__all__ = ['ALT_TAGE', 'JE_TAKT', 'Lauf', 'MAX_EMPFAENGER', 'PROPOSED_BY', 'SICHTBAR_TAGE', 'Treffer', 'heute',
           'lauf_fuer', 'schritt_fuer', 'tragende_woerter', 'woerter_in']
