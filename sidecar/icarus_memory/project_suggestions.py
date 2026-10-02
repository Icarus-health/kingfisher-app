"""Projektvorschläge aus den eigenen Zuordnungen des Nutzers, ohne Modell.

Ein Vorschlag entsteht nur, wenn die bisherigen Mails desselben Absenders
im selben Konto alle demselben Projekt zugeordnet sind (mindestens zwei).
Er wird angezeigt, nie selbst angewendet: Zuordnen tut der Nutzer mit einem
Klick. Eine Zuordnung ist Ablage, kein Beleg, und jederzeit umkehrbar.
"""
from email.utils import parseaddr

from .kontakte import absender_text
from .model import SourceType

MIN_AGREEING = 2
MAX_PEERS = 500


def _identity(episode):
    """(Konto, Adresse) einer Mail mit genau einem Absender, sonst None."""
    ref = episode.provenance.source_ref
    # Der Absender ist der Beteiligte mit Rolle `von`; Empfänger zählen nicht.
    sender = absender_text(episode.participants, episode.contacts)
    if (episode.provenance.source_type is not SourceType.EMAIL or not isinstance(ref, str)
            or ':' not in ref or not sender):
        return None
    address = parseaddr(sender)[1].strip().casefold()
    if not address or any(ch in address for ch in '%_\\'):
        return None
    return ref.split(':', 1)[0], address


def same_sender(episodes, episode):
    """Andere, nicht ausgeschlossene Mails desselben Absenders im selben Konto."""
    identity = _identity(episode)
    if identity is None:
        return []
    account, address = identity
    rows = episodes.nachrichten_mit_text(address, ausser=episode.id, limit=MAX_PEERS * 2)
    peers = []
    for other in rows:
        if _identity(other) == identity:
            peers.append(other)
            if len(peers) >= MAX_PEERS:
                break
    return peers


def sender_label(episode):
    name, address = parseaddr(absender_text(episode.participants, episode.contacts))
    return (name or address)[:120]


def for_episode(episodes, episode, names):
    """Vorschlag und Zahl der übrigen Mails dieses Absenders ohne Projekt."""
    peers = same_sender(episodes, episode)
    assigned = [peer.project_id for peer in peers if peer.project_id]
    suggestion = None
    if (episode.project_id is None and len(assigned) >= MIN_AGREEING
            and len(set(assigned)) == 1 and names.get(assigned[0])):
        suggestion = {'project_id': assigned[0], 'name': names[assigned[0]], 'count': len(assigned)}
    return {'suggestion': suggestion,
            'unassigned_peers': sum(peer.project_id is None for peer in peers),
            'sender': sender_label(episode) if peers else None}
