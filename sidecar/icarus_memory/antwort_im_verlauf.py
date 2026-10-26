"""Wer im selben Mailverlauf schon geantwortet hat, und was keine Zusage ist (Persona-Prüfung, Befund A3).

„Worauf warte ich noch?“ nannte eine Bitte als offen, auf die längst die Antwort im selben Verlauf lag („hiermit erteile
ich die Freigabe“), und eine Einladung („Über eine Zusage würde ich mich sehr freuen“) als Zusage des Einladenden.
Dieses Modul liefert die beiden Prüfungen, ohne Modell und nur aus genauen Kopfzeilen:

* **Antwort im Verlauf** (`antworten`): die späteren Mails desselben Verlaufs zu einer Mail, über Message-ID und
  Antwortbezug (`episode_mail_headers`, wie `akten._faeden`), nie über Betreff oder Namen. Je Mail: Absender, Zeit,
  ob sie automatisch ist (Abwesenheitsnotiz, Zustellfehler) und ob sie eine Verzögerung meldet.
* **Einladung** (`einladung`): Ein Text, der einlädt oder um Zusage bittet, ist keine Zusage seines Absenders, sondern
  eine Bitte an den Empfänger. Wer im selben Text zusagt („Ich sage gern zu“), sagt weiter zu.

Die Akte (`akten.Akten.akte`) legt damit fest, was vermutlich erledigt ist; „Worauf warte ich noch?“
(`offene_punkte.py`), die Abschnitte der Akte und die Karte „Worauf ich warte“ der Person lesen dasselbe Ergebnis.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .episodes import mail_address

#: Betreffzeilen automatischer Mails: Abwesenheit, Zustellfehler, Lesebestätigung. Sie beantworten nichts.
_AUTOMATISCH_BETREFF = re.compile(
    r'^\s*(?:(?:re|aw|wg|fw|fwd)\s*:\s*)*(?:automatische\s+antwort|automatic\s+reply|auto(?:matic)?[- ]?reply|'
    r'autoreply|abwesenheit|abwesend|out\s+of\s+(?:the\s+)?office|nicht\s+im\s+büro|urlaubsantwort|'
    r'unzustellbar|undeliver|delivery\s+status|mail\s+delivery|zustellung\s+fehlgeschlagen|lesebestätigung|'
    r'gelesen:|read:)', re.I)
_AUTOMATISCH_TEXT = re.compile(r'\b(?:automatisch(?:e|en)?\s+(?:antwort|generiert|erstellt)|'
                               r'diese\s+(?:nachricht|e-?mail)\s+wurde\s+automatisch|this\s+is\s+an\s+automatic)', re.I)
#: Eine Antwort, die nur eine Verzögerung meldet, liefert das Zugesagte nicht.
_VERZOEGERT = re.compile(r'\b(?:noch\s+nicht|verzöger\w*|verzoeger\w*|vertagt\w*|verschob\w*|verschieb\w*|'
                         r'später|spaeter|dauert\s+(?:noch|länger|laenger)|leider\s+(?:erst|noch)|krank\w*|'
                         r'eingeschränkt\s+erreichbar|nachreichen|nachliefern)\b', re.I)
#: Eine Antwort, die das Zugesagte mitbringt („hiermit erteile ich die Freigabe“, „anbei das Layout“).
_LIEFERUNG = re.compile(r'\b(?:anbei|beiliegend|im\s+anhang|hiermit|hier\s+(?:ist|sind|kommt|kommen|das|die|der|den)|'
                        r'wie\s+(?:versprochen|zugesagt|besprochen\s+anbei)|erhalten\s+sie\s+(?:anbei|hiermit|nun|jetzt)|'
                        r'sende\s+ich\s+ihnen|schicke\s+ich\s+(?:ihnen|dir)\s+(?:hiermit|anbei|jetzt|nun))\b', re.I)
#: Einladen oder um Zusage bitten: eine Bitte an den Empfänger, keine Zusage des Absenders.
_EINLADUNG = re.compile(
    r'\b(?:einladen|einzuladen|lade\s+(?:ich\s+|wir\s+)?(?:sie|dich|euch)\b[^.!?\n]{0,80}\bein\b|laden\s+(?:wir\s+)?'
    r'(?:sie|dich|euch)\b[^.!?\n]{0,80}\bein\b|eingeladen|einladung)\b'
    r'|\büber\s+(?:eine|ihre|deine|eure)\s+(?:zusage|teilnahme|rückmeldung)\b'
    r'|\bum\s+(?:eine\s+|ihre\s+|deine\s+|kurze\s+)?(?:zusage|rückmeldung)\b[^.!?\n]{0,30}\bbitten\b'
    r'|\bzusagen\s*[|/·•-]\s*(?:vielleicht\s*[|/·•-]\s*)?absagen\b', re.I)
_EINLADUNG_BETREFF = re.compile(r'^\s*(?:(?:re|aw|wg|fw|fwd)\s*:\s*)*(?:einladung|aktualisierte\s+einladung|'
                                r'invitation|updated\s+invitation)\b', re.I)
#: Wer im Text selbst zusagt, sagt zu, auch in einer Antwort auf eine Einladung.
_ANNAHME = re.compile(r'\b(?:(?:ich|wir)\s+(?:sage|sagen)\b[^.!?\n]{0,40}\bzu\b|sage\s+(?:ich|wir)\b[^.!?\n]{0,40}\bzu\b|'
                      r'(?:ich|wir)\s+(?:nehme|nehmen)\b[^.!?\n]{0,40}\b(?:teil|an)\b|'
                      r'(?:ich|wir)\s+(?:komme|kommen)\s+(?:gern|gerne|sehr\s+gern)|bin\s+(?:gern\s+|gerne\s+)?dabei|'
                      r'sind\s+(?:gern\s+|gerne\s+)?dabei)', re.I)


def automatisch(titel: str, text: str = '') -> bool:
    """Eine automatische Mail (Abwesenheitsnotiz, Zustellfehler, Lesebestätigung): keine Antwort eines Menschen."""
    return bool(_AUTOMATISCH_BETREFF.search(titel or '') or _AUTOMATISCH_TEXT.search((text or '')[:1500]))


def verzoegert(text: str) -> bool:
    """Meldet der Text nur, dass sich etwas verzögert („noch nicht“, „vertagt“, „später“)?"""
    return bool(_VERZOEGERT.search(text or ''))


def liefert(text: str) -> bool:
    """Bringt der Text das Zugesagte mit („anbei“, „hiermit“, „wie versprochen“)?"""
    return bool(_LIEFERUNG.search(text or ''))


def einladung(text: str, titel: str = '') -> bool:
    """Lädt der Text ein oder bittet um Zusage, ohne selbst zuzusagen? Dann ist er keine Zusage seines Absenders."""
    if _ANNAHME.search(text or ''):
        return False
    return bool(_EINLADUNG.search(text or '') or _EINLADUNG_BETREFF.search(titel or ''))


@dataclass(frozen=True)
class Mail:
    """Eine Mail eines Verlaufs, nur mit dem, was die Prüfung braucht."""

    episode_id: str
    zeit: datetime
    absender: str
    """Mailadresse des Absenders, klein geschrieben; leer, wenn unbekannt."""
    empfaenger: tuple[str, ...]
    automatisch: bool
    verzoegert: bool
    liefert: bool = False


def _zeit(wert: Any) -> datetime:
    try:
        moment = datetime.fromisoformat(str(wert))
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


#: Höchstens so viele Mails je Verlauf (eine Rundmail mit hundert Antworten wird nicht ganz gelesen).
MAX_JE_VERLAUF = 200


def verlaeufe(episodes: Any, ids: Iterable[str]) -> dict[str, list[Mail]]:
    """Je Mail alle Mails ihres Verlaufs im ganzen Bestand (auch außerhalb der Akte), älteste zuerst.

    Verbunden sind zwei Mails, wenn die eine die Message-ID der anderen als Antwortbezug trägt oder beide auf
    dieselbe Mail antworten (wie `akten._faeden`, aber über den ganzen Bestand). Mails ohne Kopfzeilen bilden
    keinen Verlauf und fehlen im Ergebnis.
    """
    from .episodes import sql_aktuell
    start = [i for i in dict.fromkeys(ids) if isinstance(i, str)]
    if not start:
        return {}
    with episodes._lock:
        conn = episodes._conn
        kennungen_von: dict[str, set[str]] = {}
        offen = list(start)
        gesehen: set[str] = set()
        bekannte_kennungen: set[str] = set()
        while offen and len(gesehen) < 5000:
            teil, offen = offen[:400], offen[400:]
            gesehen.update(teil)
            neue_kennungen: set[str] = set()
            for wert, episode_id in conn.execute(
                    'SELECT value, episode_id FROM episode_mail_headers WHERE episode_id IN ('
                    + ','.join('?' for _ in teil) + ')', teil):
                kennung = str(wert).split(':', 2)[-1]
                kennungen_von.setdefault(episode_id, set()).add(kennung)
                if kennung not in bekannte_kennungen:
                    neue_kennungen.add(kennung)
            bekannte_kennungen |= neue_kennungen
            liste = sorted(neue_kennungen)
            for anfang in range(0, len(liste), 200):
                stueck = liste[anfang:anfang + 200]
                werte = [p + k for k in stueck for p in ('mail:message:', 'mail:reply:')]
                for (episode_id,) in conn.execute(
                        'SELECT DISTINCT episode_id FROM episode_mail_headers WHERE value IN ('
                        + ','.join('?' for _ in werte) + ')', werte):
                    if episode_id not in gesehen and episode_id not in offen:
                        offen.append(episode_id)
        # Verläufe aus den Kennungen (Vereinigung über gemeinsame Kennungen).
        eltern = {i: i for i in kennungen_von}

        def wurzel(x: str) -> str:
            while eltern[x] != x:
                eltern[x] = eltern[eltern[x]]
                x = eltern[x]
            return x

        je_kennung: dict[str, list[str]] = {}
        for episode_id, kennungen in kennungen_von.items():
            for k in kennungen:
                je_kennung.setdefault(k, []).append(episode_id)
        for gruppe in je_kennung.values():
            for andere in gruppe[1:]:
                a, b = wurzel(gruppe[0]), wurzel(andere)
                if a != b:
                    eltern[b] = a
        alle = list(kennungen_von)
        kopf: dict[str, Mail] = {}
        for anfang in range(0, len(alle), 400):
            teil = alle[anfang:anfang + 400]
            for zeile in conn.execute(
                    "SELECT id, COALESCE(occurred_at, recorded_at), json_extract(document, '$.participants'), "
                    "title, substr(body, 1, 2000) FROM episodes WHERE id IN (" + ','.join('?' for _ in teil)
                    + f") AND kind = 'message' AND {sql_aktuell()}", teil):
                try:
                    beteiligte = [str(p) for p in json.loads(zeile[2] or '[]')]
                except ValueError:
                    beteiligte = []
                adressen = tuple(mail_address(p) for p in beteiligte)
                text = zeile[4] or ''
                kopf[zeile[0]] = Mail(zeile[0], _zeit(zeile[1]), adressen[0] if adressen else '',
                                      tuple(a for a in adressen[1:] if a), automatisch(zeile[3] or '', text),
                                      verzoegert(text), liefert(text))
    gruppen: dict[str, list[Mail]] = {}
    for episode_id in alle:
        if episode_id in kopf:
            gruppen.setdefault(wurzel(episode_id), []).append(kopf[episode_id])
    for liste in gruppen.values():
        liste.sort(key=lambda m: (m.zeit, m.episode_id))
        del liste[MAX_JE_VERLAUF:]
    return {i: gruppen[wurzel(i)] for i in start if i in kennungen_von and wurzel(i) in gruppen}


def beantwortet(mail_id: str, verlauf: list[Mail], *, eigene: set[str], art: str) -> Mail | None:
    """Die spätere Antwort im Verlauf, die einen Punkt des Wartens beantwortet; sonst None.

    * Deine Bitte (`art` `bitte_von_mir`): beantwortet, sobald ein anderer als du im selben Verlauf später schreibt,
      nicht automatisch. Was er dabei zusagt, ist ein eigener neuer Punkt (seine Zusage).
    * Eine Zusage an dich (`art` `zusage_an_mich`): eingelöst, wenn der Zusagende im selben Verlauf später schreibt
      und dabei etwas mitbringt („hiermit erteile ich die Freigabe“, „anbei“), nicht automatisch und ohne bloße
      Verzögerung („noch nicht“, „vertagt“). Eine bloße weitere Mail des Zusagenden (etwa eine Absage des Termins)
      löst die Zusage nicht ein; dafür fragt die Akte „Gilt das noch?“ (`akten._nach_absage`).

    Eine Antwort, die nur eine Verzögerung meldet, beantwortet auch deine Bitte nicht.
    """
    quelle = next((m for m in verlauf if m.episode_id == mail_id), None)
    if quelle is None:
        return None
    for spaeter in verlauf:
        if spaeter.zeit <= quelle.zeit or spaeter.episode_id == mail_id or spaeter.automatisch or not spaeter.absender:
            continue
        if spaeter.verzoegert:
            continue
        if art == 'bitte_von_mir':
            if spaeter.absender not in eigene:
                return spaeter
        elif art == 'zusage_an_mich':
            if spaeter.absender == quelle.absender and spaeter.absender not in eigene and spaeter.liefert:
                return spaeter
    return None


__all__ = ['Mail', 'automatisch', 'beantwortet', 'einladung', 'liefert', 'verlaeufe', 'verzoegert']
