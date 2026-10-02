"""Begrenzte Semantik für Beziehungen und zeitliche Gültigkeiten.

Diese Funktionen entscheiden keine Aussagen über die Welt. Sie beschreiben
nur, wann zwei Kandidaten dieselbe Beziehung betreffen und wann zwei
Gültigkeitsintervalle sich überschneiden. Unbekannte Prädikate bleiben dabei
konservativ: unterschiedliche Werte gelten als möglicher Widerspruch.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TypeAlias


# Die Liste ist absichtlich klein und explizit. Ein neues Prädikat darf nicht
# durch eine ähnliche Schreibweise versehentlich mehrwertig werden.
_PREDICATE_ALIASES = {
    "works_on": "works_on",
    "arbeitet_an": "works_on",
    "knows": "knows",
    "kennt": "knows",
    "friend_of": "friend_of",
    "befreundet_mit": "friend_of",
    "interested_in": "interested_in",
    "interessiert_sich_fuer": "interested_in",
    "has_email": "has_email",
    "hat_kontaktadresse": "has_email",
    "has_role": "has_role",
    "hat_rolle": "has_role",
    "status": "status",
    "hat_status": "status",
    "aussage": "aussage",
    "wiederkehrend": "wiederkehrend",
}

_MULTIVALUED_PREDICATES = frozenset(
    {
        "works_on",
        "knows",
        "friend_of",
        "interested_in",
        "has_email",
        "has_role",
        # Übernommene Sätze einer Antwort (`uebernehmen.py`): Eine Akte kann viele Aussagen tragen, und zwei
        # verschiedene Sätze sind kein Widerspruch. Ein Widerspruch entsteht erst durch eine neuere Quelle.
        "aussage",
        # Wiederkehrendes einer Akte (`wiederkehrendes.py`): Abschlag und Kündigungsfrist derselben Versicherung stehen
        # nebeneinander. Der Geburtstag (`geburtstag`) bleibt einwertig: Zwei verschiedene sind ein Widerspruch.
        "wiederkehrend",
    }
)

_Bound: TypeAlias = datetime | str | None


def _predicate_key(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Das Prädikat muss eine Zeichenkette sein.")
    # casefold sorgt für stabile Alias-Erkennung; der unbekannte Originalname
    # wird von ``canonical_predicate`` dennoch bytegenau zurückgegeben.
    return " ".join(value.strip().casefold().split())


def canonical_predicate(predicate: str) -> str:
    """Gibt den stabilen englischen Namen eines bekannten Prädikats zurück."""

    key = _predicate_key(predicate)
    # Unbekannte Namen bleiben bytegenau erhalten. Das hält die bisherige
    # konservative Behandlung offen für künftige Prädikate, statt sie durch
    # eine neue Normalisierungsregel still zusammenzulegen.
    return _PREDICATE_ALIASES.get(key, predicate)


def predicates_equivalent(left: str, right: str) -> bool:
    """Prüft bekannte Aliase; unbekannte Namen bleiben bytegenau."""

    return canonical_predicate(left) == canonical_predicate(right)


def _value_key(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Der Beziehungswert muss eine Zeichenkette sein.")
    return " ".join(value.strip().casefold().split())


def _target_key(target_ref: str | None) -> str | None:
    if target_ref is None:
        return None
    if not isinstance(target_ref, str):
        raise TypeError("Die Zielreferenz muss eine Zeichenkette oder None sein.")
    target = target_ref.strip()
    return target or None


def values_conflict(
    predicate: str,
    left_value: str,
    right_value: str,
    left_target_ref: str | None = None,
    right_target_ref: str | None = None,
) -> bool:
    """Prüft, ob zwei Werte desselben Prädikats einander widersprechen.

    Bekannte Beziehungen sind mehrwertig, sodass etwa zwei Projekte oder zwei
    Rollen nebeneinander bestehen können. Eine vorhandene Zielreferenz ist die
    Identität; eine bloße Umbenennung desselben Ziels ist deshalb kein Konflikt.
    Für unbekannte und ausdrücklich einwertige Prädikate bleibt die bisherige
    konservative Regel erhalten.
    """

    canonical = canonical_predicate(predicate)
    left = _value_key(left_value)
    right = _value_key(right_value)
    left_target = _target_key(left_target_ref)
    right_target = _target_key(right_target_ref)

    # Sobald beide Referenzen vorhanden sind, ist die Zielidentität stärker
    # als das sichtbare Label. Zwei verschiedene Ziele bleiben daher für
    # einwertige und unbekannte Prädikate ein Konflikt, auch bei gleichem
    # Label. Mehrwertige Beziehungen dürfen beide Ziele enthalten.
    if left_target is not None and right_target is not None:
        if left_target == right_target:
            return False
        if canonical in _MULTIVALUED_PREDICATES:
            return False
        return True
    if left == right:
        return False
    if canonical in _MULTIVALUED_PREDICATES:
        return False
    return True


def _parse_bound(value: _Bound, name: str) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            raise ValueError(f"{name} darf nicht leer sein.")
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"{name} ist kein gültiger ISO-Zeitpunkt.") from exc
    else:
        raise TypeError(f"{name} muss ein ISO-Zeitpunkt, datetime oder None sein.")

    # Naive Zeitpunkte wären von der lokalen Laufzeitzeitzone abhängig und
    # dürfen deshalb nicht in diesem vergleichsorientierten Kern landen.
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} muss eine Zeitzone enthalten.")
    return parsed.astimezone(timezone.utc)


def _validated_interval(
    valid_from: _Bound,
    valid_until: _Bound,
) -> tuple[datetime | None, datetime | None]:
    start = _parse_bound(valid_from, "from")
    end = _parse_bound(valid_until, "until")
    if start is not None and end is not None and start >= end:
        raise ValueError("from muss vor until liegen (halb-offenes Intervall).")
    return start, end


def validate_interval(valid_from: _Bound, valid_until: _Bound) -> None:
    """Validiert ein halb-offenes Intervall ``[from, until)``.

    Beide Grenzen dürfen offen sein. Grenzen müssen entweder ISO-Zeitpunkte
    mit Zeitzone oder bereits zeitzonenbehaftete ``datetime``-Werte sein.
    """

    _validated_interval(valid_from, valid_until)


def intervals_overlap(
    left_from: _Bound,
    left_until: _Bound,
    right_from: _Bound,
    right_until: _Bound,
) -> bool:
    """Prüft die Überschneidung zweier halb-offener Zeitintervalle.

    ``None`` bedeutet eine offene Grenze. Das Ende eines Intervalls zählt
    nicht mehr zum Intervall, daher berühren sich ``[a, b)`` und ``[b, c)``
    nur und überschneiden sich nicht.
    """

    left_start, left_end = _validated_interval(left_from, left_until)
    right_start, right_end = _validated_interval(right_from, right_until)

    # Keine Überschneidung, wenn das linke Ende vor oder genau am rechten
    # Anfang liegt; das gilt symmetrisch für die andere Richtung. Offene
    # Grenzen sind jeweils unendlich und können die Bedingung nicht verletzen.
    if left_end is not None and right_start is not None and left_end <= right_start:
        return False
    if right_end is not None and left_start is not None and right_end <= left_start:
        return False
    return True


__all__ = [
    "canonical_predicate",
    "intervals_overlap",
    "predicates_equivalent",
    "validate_interval",
    "values_conflict",
]
