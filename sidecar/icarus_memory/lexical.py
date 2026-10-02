"""Version 1 lexical contract. Semantic changes require an index migration/rebuild."""
import re

_WORDS = re.compile(r"[0-9A-Za-zÀ-ÖØ-öø-ÿ]{3,}")
_STOP_WORDS = {
    "aber", "alle", "alles", "auch", "auf", "aus", "bei", "bin", "bis",
    "das", "dass", "dein", "deine", "dem", "den", "der", "des", "die",
    "dies", "dir", "doch", "durch", "ein", "eine", "einer", "eines",
    "für", "hat", "hier", "ich", "ihm", "ihn", "ist", "kann", "kannst",
    "machen", "mein", "meine", "mich", "mit", "nicht", "noch", "oder",
    "sein", "sich", "sind", "soll", "und", "uns", "von", "vor", "was",
    "welche", "wie", "wir", "wird", "zum", "zur", "über",
}

def terms_v1(value: str) -> set[str]:
    return {
        word.casefold()
        for word in _WORDS.findall(value)
        if word.casefold() not in _STOP_WORDS
    }


def tokens_v1(value: str) -> str:
    return " ".join(sorted(terms_v1(value)))
