"""Aufgaben von selbst (26.10.2026): Eindeutige Bitten an dich und eigene Zusagen werden Aufgaben, ohne Klick.

Die Entscheidung des Nutzers (docs/66-automatik.md): „Eindeutige Bitten an dich und eigene Zusagen werden automatisch
angelegt, mit ‚Von Kingfisher angelegt · Rückgängig‘. Projekt und Person werden dabei zugeordnet. Unsichere bleiben
Vorschläge, mit ‚Alle übernehmen‘.“ Eine Aufgabe ist Ablage, kein Fakt über einen Menschen; deshalb darf sie ohne
Annahme entstehen, aber nur so:

* **Nur eindeutig** (`pruefen`, jede Bedingung mit ihrem Satz): eine Mail; die Aufgabenerkennung hat den Auftrag in
  der ganzen Mail geprüft (Bitte an den Empfänger oder eigene Zusage, Titel von der Textstelle getragen); die Mail ist
  **neu** nach `neu_eingegangen` (heute bis vorgestern) und stammt nicht aus der Bestandsaufnahme eines Postfachs, im
  Verlauf steht noch keine Antwort; eine Bitte richtet sich direkt an dich (du stehst unter „An“, nicht nur in Kopie,
  höchstens `MAX_EMPFAENGER` Empfänger) und kommt nicht von einem Sammel- oder Absenderpostfach, keine Rundmail;
  eine Zusage ist deine eigene Mail an höchstens `MAX_EMPFAENGER` Empfänger; dieselbe Aufgabe gibt es noch nicht
  (Quelle und Titel oder Textstelle, oder ein offener gleichlautender Titel); du hast sie nicht schon einmal
  zurückgenommen (dann wird auch ein neuer Vorschlag dazu verworfen). Alles andere bleibt Vorschlag.
* **Wenige auf einmal.** Höchstens `JE_DURCHLAUF` je Durchlauf; was darüber liegt, bleibt Vorschlag. Jeder Vorschlag
  wird einmal geprüft (`aufgaben_auto_geprueft` in `tasks.sqlite3`), auch über einen Neustart.
* **Sichtbar, mit Grund und Rückgängig.** Die Aufgabe trägt `angelegt` (Satz „Von Kingfisher angelegt, weil …“, Mail,
  Grundsatz) und `person` (wer bittet bzw. wem du zugesagt hast, die Adresse führt zur Akte); das Projekt kommt aus
  der Quelle oder aus der Absenderregel (`task_project_hints.py`), die Frist nur, wenn die Textstelle genau eine
  eindeutige nennt (`fristen.py`). Zurücknehmen entfernt die Aufgabe, legt den Vorschlag als verworfen ab und merkt
  sich Quelle, Titel und Textstelle, damit sie nicht wiederkommt; „Rückgängig“ davon stellt sie unverändert wieder her.
* **Schalter.** „Aufgaben aus Mails selbst anlegen“ unter „Was Kingfisher darf“, Vorgabe an. Aus: nichts entsteht.

Läuft nach jedem Mail-Durchlauf und nach jeder Aufgabenerkennung (`schritt_fuer`), ohne Modell, deterministisch.
Logbuch: `aufgabe_post` mit `sorte` `angelegt`, `zurueckgenommen`, `wiederhergestellt` (nur Kennungen, kein Text).
"""
from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Callable, Iterable

from . import logbuch
from .datumstext import tag_und_monat
from .episodes import AUSGEBLENDETE_ZUSTAENDE, EpisodeError, mail_address
from .kontakte import anzeigename
from .model import Provenance, SourceType, user_timezone
from .neu_eingegangen import aus_bestandsaufnahme, fenster_beginn, ist_neu
from .people_quality import ist_sammelpostfach, lokalteil
from .proposals import ProposalError, ProposalKind, ProposalState
from .task_review import REVIEW_MARKER, hard_details_supported, task_context_matches
from .tasks import Task, TaskStatus
from .word_forms import umschrift_gleich

logger = logging.getLogger(__name__)

#: Mehr Empfänger (An und Cc zusammen, du eingeschlossen) machen eine Mail zur Rundmail: dann nur ein Vorschlag.
MAX_EMPFAENGER = 3
#: Höchstens so viele Aufgaben legt ein Durchlauf an; der Rest bleibt Vorschlag.
JE_DURCHLAUF = 10
#: Höchstens so viele Vorschläge auf einmal übernimmt „Alle übernehmen“.
ALLE_HOECHSTENS = 100
EXTRACTED_BY = 'aufgaben_von_selbst'
_RUNDMAIL = re.compile(r'\b(?:abbestellen|abmelden|unsubscribe|newsletter|nicht mehr erhalten)\b', re.I)


# -- Kleine Bausteine ---------------------------------------------------------------


def schluessel(text: str) -> str:
    """Woran zwei Titel oder Textstellen als dieselbe Aufgabe gelten: Wörter in Umschrift, ohne Satzzeichen."""
    return ' '.join(umschrift_gleich(w) for w in re.findall(r'[0-9A-Za-zÀ-ÖØ-öø-ÿß]+', str(text or '')))


def _ort(zeit: datetime) -> datetime:
    zone = user_timezone()
    return zeit.astimezone(zone) if zone and zeit.tzinfo else zeit


def _name(person: dict[str, str] | None) -> str:
    return (person or {}).get('name') or (person or {}).get('adresse') or ''


@dataclass
class Beteiligte:
    """Wer an einer Mail beteiligt ist, aus den Kontakten der Episode (Rolle je Adresse)."""
    von: dict[str, str]
    von_mir: bool
    an: list[dict[str, str]]
    cc: list[dict[str, str]]
    ich_an: bool
    """Ob eine eigene Adresse unter „An“ steht (nicht nur in Kopie)."""
    rollen_bekannt: bool

    @property
    def fremde(self) -> list[dict[str, str]]:
        return [p for p in self.an + self.cc if not p.get('ich')]

    @property
    def anzahl(self) -> int:
        return len(self.an) + len(self.cc)


def beteiligte(episode: Any, eigene: Iterable[str]) -> Beteiligte | None:
    eigene_adressen = {mail_address(a) for a in eigene if mail_address(a)}
    kontakte = list(getattr(episode, 'contacts', None) or [])

    def eintrag(k: dict[str, Any]) -> dict[str, str]:
        adresse = str(k.get('adresse') or '').casefold()
        return {'adresse': adresse, 'name': str(k.get('name') or ''),
                'ich': bool(k.get('ich')) or adresse in eigene_adressen}

    von = next((k for k in kontakte if k.get('rolle') == 'von'), None)
    if von is None:
        if not episode.participants:
            return None
        adresse = mail_address(episode.participants[0])
        absender = {'adresse': adresse, 'name': anzeigename(episode.participants[0]), 'ich': adresse in eigene_adressen}
        return Beteiligte(absender, absender['ich'], [], [], False, rollen_bekannt=False)
    absender = eintrag(von)
    an = [eintrag(k) for k in kontakte if k.get('rolle') == 'an' and k.get('adresse')]
    cc = [eintrag(k) for k in kontakte if k.get('rolle') in ('cc', 'bcc') and k.get('adresse')]
    return Beteiligte(absender, absender['ich'], an, cc, any(p['ich'] for p in an), rollen_bekannt=True)


def person_der_quelle(episode: Any, eigene: Iterable[str]) -> tuple[str | None, dict[str, str] | None]:
    """Die Richtung (`bitte`, `zusage`) und die Person: wer bittet, oder wem du zugesagt hast (erster fremder
    Empfänger unter „An“). Ohne Mail oder ohne erkennbare Person: (None, None) bzw. die Richtung ohne Person."""
    if getattr(episode.provenance, 'source_type', None) is not SourceType.EMAIL:
        return None, None
    b = beteiligte(episode, eigene)
    if b is None:
        return None, None
    if b.von_mir:
        ziel = next((p for p in b.an if not p['ich']), None) or next((p for p in b.cc if not p['ich']), None)
        return 'zusage', ({'adresse': ziel['adresse'], 'name': ziel['name'] or ziel['adresse']} if ziel else None)
    if not b.von.get('adresse') or ist_sammelpostfach(lokalteil(b.von['adresse'])):
        return 'bitte', None
    return 'bitte', {'adresse': b.von['adresse'], 'name': b.von['name'] or b.von['adresse']}


def frist_aus(zitat: str, bezug: datetime | None) -> datetime | None:
    """Die Frist der Textstelle: nur, wenn genau eine eindeutige Datumsangabe darin steht und keine unklare (dann
    23:59 Uhr dieses Tages in der Zeitzone des Nutzers); sonst keine. Eine falsche Frist ist schlimmer als keine."""
    if bezug is None:
        return None
    from .fristen import fristen_in
    suche = fristen_in(zitat or '', bezug)
    if len(suche.fristen) != 1 or suche.ohne_datum:
        return None
    zone = user_timezone() or timezone.utc
    return datetime.combine(suche.fristen[0].datum, time(23, 59), tzinfo=zone)


# -- Was eindeutig ist ----------------------------------------------------------------


@dataclass
class Urteil:
    eindeutig: bool
    kuerzel: str
    """Kurz, für die Merkliste: `angelegt`, `keine_mail`, `ungeprueft`, `titel`, `zurueckgenommen`, `nicht_neu`,
    `bestand`, `verlauf`, `rundmail`, `absender`, `kopie`, `rollen`, `ohne_empfaenger`, `dublette`."""
    satz: str
    """Ein Satz, warum: bei eindeutig der Grundsatz, sonst, warum es Vorschlag bleibt."""
    richtung: str | None = None
    person: dict[str, str] | None = None


def pruefen(proposal: Any, episode: Any, *, eigene: Iterable[str], jetzt: datetime, zeitstatus: str | None,
            aus_bestand: bool, dublette: bool, zurueckgenommen: bool, text: str | None = None) -> Urteil:
    """Ob Kingfisher diese Aufgabe selbst anlegen darf. Reine Regel ohne Speicher; die Fakten gibt der Aufrufer.

    `zeitstatus` ist die zeitliche Einordnung der Quelle (`mail_timeline.timings`: `recent`, `followup`, `history`,
    `old`, …); `aus_bestand`, ob nur die Bestandsaufnahme eines Postfachs die Mail geholt hat; `dublette`, ob es die
    Aufgabe schon gibt; `zurueckgenommen`, ob der Nutzer sie schon einmal zurückgenommen hat."""
    def nein(kuerzel: str, satz: str) -> Urteil:
        return Urteil(False, kuerzel, satz)

    if getattr(episode.provenance, 'source_type', None) is not SourceType.EMAIL:
        return nein('keine_mail', 'Nur Bitten und Zusagen aus Mails legt Kingfisher selbst an.')
    zitat = proposal.evidence[0].quote if proposal.evidence else ''
    if proposal.task_context is None or not str(proposal.proposed_by or '').endswith(REVIEW_MARKER):
        return nein('ungeprueft', 'Der Auftrag ist in der ganzen Mail noch nicht geprüft.')
    if not hard_details_supported(proposal.statement, zitat):
        return nein('titel', 'Der Titel nennt etwas, das so nicht in der Mail steht.')
    if zurueckgenommen:
        return nein('zurueckgenommen', 'Du hast diese Aufgabe schon einmal zurückgenommen.')
    if aus_bestand:
        return nein('bestand', 'Die Mail stammt aus dem ersten Einlesen des Postfachs, nicht aus neuer Post.')
    if not ist_neu(episode.occurred_at, episode.recorded_at, jetzt=jetzt):
        return nein('nicht_neu', 'Die Mail ist älter als vorgestern.')
    if zeitstatus != 'recent':
        return nein('verlauf', 'Im Verlauf steht schon eine weitere Mail, oder die Zeit der Mail ist unklar.')
    b = beteiligte(episode, eigene)
    if b is None or not b.rollen_bekannt:
        return nein('rollen', 'Wer die Mail bekam, ist nicht bekannt.')
    if b.anzahl > MAX_EMPFAENGER or _RUNDMAIL.search(text if text is not None else (episode.body or '')):
        return nein('rundmail', 'Eine Rundmail oder ein Newsletter.')
    richtung, person = person_der_quelle(episode, eigene)
    if b.von_mir:
        if not b.fremde:
            return nein('ohne_empfaenger', 'Die Mail ging an niemanden außer dir.')
        satz = f'Deine Zusage an {_name(person) or "die Gegenseite"}, aus einer neuen Mail.'
    else:
        if ist_sammelpostfach(lokalteil(b.von.get('adresse') or '')):
            return nein('absender', 'Die Mail kommt von einem automatischen Absender.')
        if not b.ich_an:
            return nein('kopie', 'Du stehst nur in Kopie.')
        satz = f'Eine Bitte von {_name(person)} direkt an dich, aus einer neuen Mail.'
    if dublette:
        return nein('dublette', 'Diese Aufgabe gibt es schon.')
    return Urteil(True, 'angelegt', satz, richtung, person)


# -- Der Durchlauf ---------------------------------------------------------------------


class Durchlauf:
    """Prüft offene Aufgabenvorschläge aus neuen Mails und legt eindeutige selbst an; Rückgängig und „Alle übernehmen“."""

    def __init__(self, tasks: Any, episodes: Any, proposals: Any, *, workspace: Any = None, views: Any = None,
                 lock: Any = None, eigene: Callable[[], Iterable[str]] = lambda: (),
                 jetzt: Callable[[], datetime] | None = None) -> None:
        self.tasks, self.episodes, self.proposals = tasks, episodes, proposals
        self.workspace, self.views, self.lock = workspace, views, lock
        self._eigene = eigene
        self._jetzt = jetzt or (lambda: datetime.now(timezone.utc))

    # -- Zuordnung: Projekt und Person --

    def projekt(self, proposal: Any, episode: Any) -> dict[str, Any] | None:
        """Das Projekt der Quelle, sonst die Absenderregel, sonst ein gemerkter lokaler Hinweis; nur vorhandene, offene
        Projekte (ein neues Projekt legt hier niemand an)."""
        if self.workspace is None:
            return None
        offen = {p.id: p.name for p in self.workspace.projects() if p.is_open()}
        if episode.project_id:
            return {'project_id': episode.project_id, 'name': offen[episode.project_id], 'origin': 'user_source'} \
                if episode.project_id in offen else None
        hinweis = None
        if self.views is not None:
            from .task_project_hints import TaskProjectHints
            hinweis = TaskProjectHints(self.episodes, self.proposals, self.workspace, self.views, self.lock).visible(proposal)
        else:
            from .project_suggestions import for_episode
            regel = for_episode(self.episodes, episode, offen)['suggestion']
            hinweis = {**regel, 'origin': 'sender_rule'} if regel else None
        if hinweis and hinweis.get('project_id') in offen:
            return {'project_id': hinweis['project_id'], 'name': offen[hinweis['project_id']], 'origin': hinweis.get('origin')}
        return None

    def person(self, episode: Any) -> dict[str, str] | None:
        return person_der_quelle(episode, self._eigene())[1]

    # -- Prüfen und anlegen --

    def _gueltig(self, proposal: Any) -> Any | None:
        """Die Quelle eines Vorschlags, wenn der Beleg noch trägt (wie `task_detection.candidate_batches`)."""
        if len(proposal.evidence) != 1:
            return None
        beleg = proposal.evidence[0]
        try:
            episode = self.episodes.get(beleg.episode_id)
        except EpisodeError:
            return None
        if (episode.state in AUSGEBLENDETE_ZUSTAENDE or episode.digest != beleg.digest or not beleg.quote
                or beleg.quote not in episode.body or not task_context_matches(proposal, self.episodes)):
            return None
        return episode

    def _dublette(self, proposal: Any, episode: Any, offene_titel: set[str]) -> bool:
        titel, zitat = schluessel(proposal.statement), schluessel(proposal.evidence[0].quote)
        if self.tasks.get(f't-suggestion-{proposal.id}') is not None or titel in offene_titel:
            return True
        return any(schluessel(t.title) == titel or schluessel(t.provenance.verbatim or '') == zitat
                   for t in self.tasks.mit_quelle(f'episode:{episode.id}'))

    def _kandidaten(self, jetzt: datetime) -> list[tuple[Any, Any]]:
        beginn = fenster_beginn(jetzt)
        geprueft = self.tasks.auto_geprueft()
        ergebnis = []
        for batch in self.proposals.pending_batches(ProposalKind.TASK):
            for proposal in batch:
                # Vor dem Fenster erkannt heißt: Die Mail ist vor dem Fenster gekommen, also nicht neu.
                if proposal.id in geprueft or proposal.created_at < beginn:
                    continue
                episode = self._gueltig(proposal)
                if episode is not None:
                    ergebnis.append((proposal, episode))
        return ergebnis

    def urteile(self, paare: list[tuple[Any, Any]], jetzt: datetime) -> list[Urteil]:
        from .mail_timeline import timings
        quellen = list({e.id: e for _, e in paare}.values())
        zeiten = timings(self.episodes, quellen, now=jetzt) if quellen else {}
        bestand = aus_bestandsaufnahme(self.episodes, [e.id for e in quellen])
        offene_titel = {schluessel(t.title) for t in self.tasks.open_tasks(limit=None)}
        eigene = list(self._eigene())
        urteile = []
        for proposal, episode in paare:
            zitat = proposal.evidence[0].quote
            urteile.append(pruefen(
                proposal, episode, eigene=eigene, jetzt=jetzt,
                zeitstatus=(zeiten.get(episode.id) or {}).get('temporal_status'),
                aus_bestand=episode.id in bestand, dublette=self._dublette(proposal, episode, offene_titel),
                zurueckgenommen=self.tasks.auto_zurueckgenommen(episode.id, schluessel(proposal.statement), schluessel(zitat))))
        return urteile

    def schritt(self, limit: int = JE_DURCHLAUF) -> dict[str, int]:
        """Ein Durchlauf; jeder Vorschlag einmal. Mit ausgeschaltetem Schalter geschieht nichts."""
        bericht = {'geprueft': 0, 'angelegt': 0, 'vorschlaege': 0}
        if not self.tasks.auto_an():
            return bericht
        jetzt = self._jetzt()
        paare = self._kandidaten(jetzt)
        if not paare:
            return bericht
        for (proposal, episode), urteil in zip(paare, self.urteile(paare, jetzt)):
            bericht['geprueft'] += 1
            ergebnis = urteil.kuerzel
            if urteil.eindeutig and bericht['angelegt'] >= limit:
                ergebnis = 'obergrenze'
            elif urteil.eindeutig:
                try:
                    self._anlegen(proposal, episode, urteil, jetzt)
                    bericht['angelegt'] += 1
                except Exception:  # noqa: BLE001 - fail closed: bleibt Vorschlag, nichts halb angelegt
                    logger.exception('Aufgabe von selbst konnte nicht angelegt werden')
                    ergebnis = 'fehler'
            if ergebnis == 'zurueckgenommen':
                # Was der Nutzer zurückgenommen hat, kommt auch als Vorschlag nicht wieder (dieselbe Mail, neuer Lauf).
                try:
                    self.proposals.entscheidung_aendern(proposal.id, ProposalState.REJECTED, von=(ProposalState.PENDING,))
                except ProposalError:
                    pass
            elif ergebnis != 'angelegt':
                bericht['vorschlaege'] += 1
            self.tasks.auto_geprueft_merken(proposal.id, ergebnis)
        return bericht

    def _anlegen(self, proposal: Any, episode: Any, urteil: Urteil, jetzt: datetime) -> Task:
        zitat = proposal.evidence[0].quote
        zeit = episode.occurred_at or episode.recorded_at
        wer = _name(urteil.person) or ('die Gegenseite' if urteil.richtung == 'zusage' else 'jemand')
        tag = tag_und_monat(_ort(zeit))
        satz = (f'Von Kingfisher angelegt, weil du {wer} am {tag} zugesagt hast.' if urteil.richtung == 'zusage'
                else f'Von Kingfisher angelegt, weil {wer} dich am {tag} darum gebeten hat.')
        projekt = self.projekt(proposal, episode)
        angelegt = {'art': 'automatisch', 'satz': satz, 'grundsatz': urteil.satz, 'richtung': urteil.richtung,
                    'episode_id': episode.id, 'mail_titel': (episode.title or '')[:120], 'wer': wer,
                    'datum': zeit.isoformat() if zeit else None, 'am': jetzt.astimezone(timezone.utc).isoformat(),
                    'proposal_id': proposal.id, 'projekt_herkunft': projekt.get('origin') if projekt else None}
        task = self.tasks.from_suggestion(
            proposal.id, proposal.statement,
            Provenance(source_type=SourceType.INFERENCE, source_ref=f'episode:{episode.id}', captured_at=jetzt,
                       extracted_by=EXTRACTED_BY, verbatim=zitat),
            due=frist_aus(zitat, episode.occurred_at), project_id=projekt['project_id'] if projekt else None,
            person=urteil.person, angelegt=angelegt)
        self.proposals.accept(proposal.id, produced=task.id)
        logbuch.vermerke('aufgabe_post', sorte='angelegt', aufgabe=task.id, mail=episode.id, wie=urteil.richtung or '')
        return task

    # -- Zurücknehmen und Wiederherstellen --

    def zuruecknehmen(self, task_id: str) -> Task:
        """Entfernt eine selbst angelegte Aufgabe, legt den Vorschlag als verworfen ab und merkt sich das.
        `KeyError` unbekannt, `LookupError`, wenn Kingfisher sie nicht selbst angelegt hat."""
        task = self.tasks.get(task_id)
        if task is None:
            raise KeyError(task_id)
        angelegt = task.angelegt or {}
        if angelegt.get('art') != 'automatisch':
            raise LookupError('Diese Aufgabe hat Kingfisher nicht selbst angelegt; sie bleibt.')
        proposal_id = str(angelegt.get('proposal_id') or '')
        episode_id = str(angelegt.get('episode_id') or '')
        entfernt = self.tasks.anlage_entfernen(task_id, merken={
            'proposal_id': proposal_id or task_id, 'episode_id': episode_id, 'titel_schluessel': schluessel(task.title),
            'zitat_schluessel': schluessel(task.provenance.verbatim or '')})
        if proposal_id:
            try:
                self.proposals.entscheidung_aendern(proposal_id, ProposalState.REJECTED, von=(ProposalState.ACCEPTED,))
            except ProposalError:
                pass  # Die Merkliste der Aufgaben hält es trotzdem fest.
        logbuch.vermerke('aufgabe_post', sorte='zurueckgenommen', aufgabe=task_id, mail=episode_id, wie='automatisch')
        return entfernt

    def wiederherstellen(self, task_id: str) -> Task:
        """„Rückgängig“ des Zurücknehmens: dieselbe Aufgabe wie vorher, der Vorschlag wieder angenommen."""
        task, proposal_id = self.tasks.anlage_wiederherstellen(task_id)
        try:
            self.proposals.entscheidung_aendern(proposal_id, ProposalState.ACCEPTED, von=(ProposalState.REJECTED,),
                                                produced=task.id)
        except ProposalError:
            pass
        logbuch.vermerke('aufgabe_post', sorte='wiederhergestellt', aufgabe=task.id,
                         mail=str((task.angelegt or {}).get('episode_id') or ''), wie='automatisch')
        return task

    # -- Heute --

    def heute(self) -> dict[str, Any]:
        """Was Kingfisher heute (Kalendertag des Nutzers) selbst angelegt hat: ein Satz und die Aufgaben, offen oder nicht."""
        ort = _ort(self._jetzt())
        beginn = ort.replace(hour=0, minute=0, second=0, microsecond=0)
        aufgaben = self.tasks.angelegt_seit(beginn)
        anzahl = len(aufgaben)
        satz = ('' if anzahl == 0 else '1 Aufgabe aus der Post angelegt.' if anzahl == 1
                else f'{anzahl} Aufgaben aus der Post angelegt.')
        return {'anzahl': anzahl, 'satz': satz,
                'aufgaben': [{'id': t.id, 'title': t.title, 'status': t.status.value,
                              'satz': (t.angelegt or {}).get('satz', '')} for t in aufgaben]}

    # -- Vorschläge: Projekt, Person, Frist vorbefüllt; „Alle übernehmen“ --

    def vorbefuellt(self, proposal: Any) -> dict[str, Any]:
        """Was eine Vorschlagszeile vorbefüllt: Person und erkannte Frist (das Projekt kommt aus `task_project_hints`)."""
        episode = self._gueltig(proposal)
        if episode is None:
            return {'person_vorschlag': None, 'frist_vorschlag': None}
        frist = frist_aus(proposal.evidence[0].quote, episode.occurred_at)
        return {'person_vorschlag': self.person(episode), 'frist_vorschlag': frist.isoformat() if frist else None}

    def alle_uebernehmen(self, proposal_ids: list[str], *, annehmen: Callable[..., Task]) -> dict[str, Any]:
        """Übernimmt die Vorschläge mit vorbefülltem Projekt (nur vorhandene), Person und Frist, als eine Gruppe.
        `annehmen` ist `TaskCandidates.accept` (prüft jede Quelle erneut). Was scheitert, bleibt Vorschlag."""
        gruppe = 'g-' + uuid.uuid4().hex[:16]
        jetzt = self._jetzt()
        angelegt, fehler = [], []
        for proposal_id in list(dict.fromkeys(proposal_ids))[:ALLE_HOECHSTENS]:
            try:
                proposal = self.proposals.get(proposal_id)
                episode = self._gueltig(proposal) if proposal.state is ProposalState.PENDING else None
                if proposal.kind is not ProposalKind.TASK or episode is None:
                    raise ProposalError('Der Vorschlag oder seine Quelle ist nicht mehr gültig.')
                projekt = self.projekt(proposal, episode)
                task = annehmen(proposal_id, title=proposal.statement,
                                project_id=projekt['project_id'] if projekt else None,
                                due=frist_aus(proposal.evidence[0].quote, episode.occurred_at),
                                person=self.person(episode),
                                angelegt={'art': 'alle_uebernehmen', 'gruppe': gruppe,
                                          'am': jetzt.astimezone(timezone.utc).isoformat()})
                angelegt.append(task)
            except (ProposalError, EpisodeError, ValueError, LookupError) as exc:
                fehler.append({'id': proposal_id, 'grund': str(exc)})
        return {'gruppe': gruppe, 'aufgaben': [t.to_dict() for t in angelegt], 'fehler': fehler}

    def gruppe_zuruecknehmen(self, gruppe: str) -> dict[str, Any]:
        """Nimmt eine gemeinsame Übernahme ganz zurück: Die Aufgaben gehen, die Vorschläge stehen wieder offen da.
        Eine Aufgabe, die inzwischen erledigt oder geändert wurde, bleibt (sie gehört jetzt dem Nutzer)."""
        zurueck, geblieben = 0, 0
        for task in self.tasks.gruppe(gruppe):
            if task.status is not TaskStatus.OPEN or not task.id.startswith('t-suggestion-'):
                geblieben += 1
                continue
            self.tasks.anlage_entfernen(task.id)
            try:
                self.proposals.entscheidung_aendern(task.id[len('t-suggestion-'):], ProposalState.PENDING,
                                                    von=(ProposalState.ACCEPTED,))
            except ProposalError:
                pass
            zurueck += 1
        return {'zurueckgenommen': zurueck, 'geblieben': geblieben}


# -- Für den Server ---------------------------------------------------------------------


def durchlauf_fuer(app: Any) -> Durchlauf:
    from . import identitaet
    return Durchlauf(app.state.tasks, app.state.episodes, app.state.proposals,
                     workspace=getattr(app.state, 'workspace', None), views=getattr(app.state, 'workspace_views', None),
                     lock=app.state.conversation_lock,
                     eigene=lambda: identitaet.eigene_adressen(getattr(app.state, 'settings', None)))


def schritt_fuer(app: Any) -> dict[str, int]:
    """Nach der Mailaufnahme und nach der Aufgabenerkennung; ein Fehler hier hält nichts auf."""
    try:
        with app.state.conversation_lock:
            return durchlauf_fuer(app).schritt()
    except Exception:  # noqa: BLE001
        logger.exception('Aufgaben von selbst: Durchlauf gescheitert')
        return {'geprueft': 0, 'angelegt': 0, 'vorschlaege': 0}


def zuordnung_fuer_quelle(app: Any, episode_id: str) -> tuple[str | None, dict[str, str] | None]:
    """Projekt (Quelle oder Absenderregel, nur offene) und Person einer Mail, für die Übernahme aus dem Mail-Briefing."""
    lauf = durchlauf_fuer(app)
    try:
        episode = app.state.episodes.get(episode_id)
    except EpisodeError:
        return None, None
    from types import SimpleNamespace
    projekt = Durchlauf(lauf.tasks, lauf.episodes, lauf.proposals, workspace=lauf.workspace).projekt(
        SimpleNamespace(), episode)
    return (projekt['project_id'] if projekt else None), lauf.person(episode)


__all__ = ['ALLE_HOECHSTENS', 'Beteiligte', 'Durchlauf', 'JE_DURCHLAUF', 'MAX_EMPFAENGER', 'Urteil', 'beteiligte',
           'durchlauf_fuer', 'frist_aus', 'person_der_quelle', 'pruefen', 'schluessel', 'schritt_fuer',
           'zuordnung_fuer_quelle']
