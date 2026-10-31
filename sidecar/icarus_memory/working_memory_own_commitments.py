"""Enger Ausschluss fremder Ich-Zusagen bei einer ausdrücklich eigenen Zusage.

Dies ist keine positive Urheberprüfung. Nur die geschlossene Form einer direkt
geschriebenen Ich-Zukunftsaussage wird ausgeschlossen, wenn die Mailrollen einen
fremden Absender und einen bekannten eigenen Empfänger belegen. Berichte,
Zitate, weitere Sprecher und unbekannte Rollen bleiben beim bisherigen Weg.
Es werden nur Antwortbelege eingeschränkt, niemals Originale oder Einordnungen.
"""
import re

from .episodes import mail_address
from .model import SourceType
from .working_memory_store import WorkingMemoryStore

_EIGENE_FRAGE = re.compile(
    r'(?:(?:was|wem|wann|bis\s+wann|welche\s+zusagen?)\s+)?(?:habe|hatte)\s+ich\b'
    r'(?P<gegenstand>[^?!.,;:\r\n]{0,300})\b(?:zugesagt|versprochen)\s*\??', re.I)
_OFFENE_FRAGE = re.compile(
    r'\b(?:und|oder|nicht|kein\w*|sondern|beide\w*|vergleiche?\w*)\b', re.I)
_WEITERE_FRAGE = re.compile(r'\b(?:was|wer|wem|wann|wie|welch\w*|hat|haben|hatte|hatten|habe)\b', re.I)
# Punkte in ausgeschriebenen Datumsangaben gehören zum selben Satz. Andere
# Sätze, Zeilen, Zitate und Nebensätze dürfen keinen Sprecherwechsel verbergen.
_SATZTEIL = r'(?:[^.!?\r\n]|(?<=\d)\.(?=[ \t]+\w))'
_DIREKT = re.compile(
    r'Ich\s+werde\s+(?P<handlung>' + _SATZTEIL + r'+?\b[a-zäöüß]+(?:en|eln|ern))\.'
    r'(?:\s+(?:Das|Dies)\s+ist\s+meine\s+Zusage(?:,\s*keine\s+Bitte\s+an\s+dich)?\.)?\s*', re.I)
_BERICHT = re.compile(
    r'[\'"„“«»<>;,()\[\]{}]|(?<!\d):(?!\d)|\b(?:du|dein\w*|dass|daß|ob|weil|laut|von|zitiert\w*|'
    r'gesagt|zugesagt\w*|zusage\w*|versprochen\w*|versprach\w*|schrieb\w*|wrote|'
    r'berichten|weiterleiten|zitieren|erinnern|weitergeleitet\w*|forward\w*)\b', re.I)
_WEITERLEITUNG = re.compile(r'^\s*(?:fw|fwd|wg)\s*:|\b(?:weitergeleitet\w*|weiterleitung|forwarded)\b', re.I)


def ausgeschlossen(frage, refs, episodes):
    """Kennungen eindeutig fremder direkter Zusagen; keine geratenen Urheber.

    Jede Referenz wird frisch aufgelöst. Rollen stammen aus den strukturierten
    Mailkontakten, nicht aus Namen, Betreff, Gesendet-Ordner oder Modellprosa.
    Die Prüfung ist auf die übergebenen Belege begrenzt, ohne Bestandsdurchlauf.
    """
    eigene_frage = _EIGENE_FRAGE.fullmatch(frage.strip())
    if (eigene_frage is None or _OFFENE_FRAGE.search(frage)
            or _WEITERE_FRAGE.search(eigene_frage['gegenstand'])):
        return set()
    store = WorkingMemoryStore(episodes)
    ausgeschlossen_ = set()
    for ref in refs:
        if not isinstance(ref, dict) or ref.get('kind') != 'commitment':
            continue
        snapshot = store.resolve(ref)
        if snapshot is None:
            continue
        episode = snapshot.episode
        if episode.provenance.source_type is not SourceType.EMAIL or _WEITERLEITUNG.search(episode.title):
            continue
        kontakte = episode.contacts or []
        absender = [k for k in kontakte if k.get('rolle') == 'von']
        if len(absender) != 1 or absender[0].get('ich') is not False:
            continue
        adresse = mail_address(absender[0].get('adresse', ''))
        eigene = {mail_address(k.get('adresse', '')) for k in kontakte if k.get('ich') is True}
        if not adresse or not eigene - {''} or adresse in eigene:
            continue
        if not any(k.get('rolle') in {'an', 'cc', 'bcc'} and k.get('ich') is True for k in kontakte):
            continue
        text = episode.body.strip()
        direkt = _DIREKT.fullmatch(text)
        if direkt is not None and not _BERICHT.search(direkt['handlung']):
            ausgeschlossen_.add(episode.id)
    return ausgeschlossen_
