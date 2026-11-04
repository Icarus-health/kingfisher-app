"""Konservative Inhaltsgrenzen für automatisch gelernte Verfahren, ohne Modellarbeit."""
import json
import re

from .lexical import terms_v1

# Enger Zusatz zur Modellprüfung: konkrete Werte bleiben im Korrektur-/Faktenweg.
# Keine allgemeine Entitätserkennung; unklare Fälle werden nicht automatisch gelernt.
_FACT_DETAIL = re.compile(
    r'@|https?://|\b\d{4}-\d{1,2}-\d{1,2}\b|'
    r'\b\d{1,2}\.\d{1,2}\.(?:\d{2,4})?(?!\d)|'
    r'\b\d{1,2}\.\s*(?:januar|februar|märz|maerz|april|mai|juni|juli|'
    r'august|september|oktober|november|dezember)\b|\b\d{1,2}(?::\d{2}|\s*Uhr)\b|'
    r'\b(?:morgen|heute|gestern|übermorgen|vorgestern)\b|'
    r'\b(?:ist|liegt|endet|beginnt)\s+(?:am|morgen|heute|gestern)\b|'
    r'\b(?:heißt|heisst|lautet|beträgt)\s+\S+', re.I)
_BOILERPLATE = frozenset(('bitte zuerst danach dann erst immer jedes jeden jede vorher nachher '
    'bevor beim schreiben mail mails email emails entwurf entwerfen erstellen prüfen prüfe '
    'künftig zukünftig nochmals erneut unbedingt sollte sollen muss müssen '
    'derzeit mindestens allem klären kläre suchen suche zuordnen vergleichen vergleiche '
    'zusammenfassen auflisten öffnen lesen gegenlesen festhalten nachfragen bestätigen '
    'sortieren verknüpfen abgleichen').split())


def subjects(record):
    correction = record['correction']
    if _FACT_DETAIL.search(correction):
        return set()
    # Ein gemeinsames „prüfe“ oder derselbe Vereinsname belegt noch keinen
    # wiederholten Prüfschritt. Ein Bezug aus der Korrektur muss wiederkehren.
    return terms_v1(correction) - _BOILERPLATE - terms_v1(record['request'])


def has_concrete_values(spec):
    return bool(_FACT_DETAIL.search(json.dumps(spec, ensure_ascii=False)))

