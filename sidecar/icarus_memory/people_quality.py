"""Read-only quality hints for the legacy participant projection.

An address is an inbox identifier, not proof of a human identity. No records,
labels, node IDs, relationships or evidence are merged or removed here.
"""
from collections import defaultdict
from dataclasses import replace
from email.utils import getaddresses
import re

AUTOMATED = re.compile(r'(?:^|[._-])(?:no[._-]?reply|notifications?|mailer[._-]?daemon|postmaster)(?:$|[._-])', re.I)
GENERIC = {'support', 'info', 'team', 'learn', 'newsletter', 'news', 'office', 'service', 'kontakt', 'mail', 'hello'}


def lokalteil(adresse):
    """Der Teil vor dem @ ohne „+Zusatz“, kleingeschrieben: `Info+x@firma.de` -> `info`."""
    return adresse.casefold().split('@', 1)[0].split('+', 1)[0]


def ist_sammelpostfach(lokal):
    """Allgemeines oder technisches Postfach (info@, noreply@ …): belegt keine Person.

    Die eine Stelle dieser Regel; Aufnahme, Kategorien und Personenansicht rufen sie.
    """
    return lokal in GENERIC or bool(AUTOMATED.search(lokal))


def _mailbox(label):
    parsed = getaddresses([label])
    if len(parsed) != 1:
        return None, None
    name, address = parsed[0]
    if not re.fullmatch(r'[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+', address):
        return None, None
    return name.strip(), address.casefold()


def annotate_people(nodes):
    metadata = {}
    addresses = defaultdict(list)
    names = defaultdict(list)
    for node in nodes:
        if node.kind != 'person':
            continue
        label = node.label.strip()
        name, address = _mailbox(label)
        local = lokalteil(address) if address else ''
        explicit = node.attributes.get('identity_resolution') == 'explicit_registry'
        category, reason = 'person', ''
        if re.search(r'\(Integrationstest\)', label, re.I):
            category, reason = 'review', 'Als Integrationstest bezeichnet; Herkunft vor Bereinigung prüfen.'
        elif not explicit and address and AUTOMATED.search(local):
            category, reason = 'automated', 'Technische Benachrichtigungsadresse; der Anzeigename belegt keine Personenidentität.'
        elif not explicit and address and local in GENERIC:
            category, reason = 'review', 'Allgemeines Postfach; Person oder Organisation noch ungeklärt.'
        elif not explicit and '@' in label and not address:
            category, reason = 'review', 'Keine eindeutige Mailadresse aus dem Absender lesbar.'
        metadata[node.id] = {
            'quality_category': category, 'quality_reason': reason,
            'duplicate_ids': [], 'duplicate_reason': '',
        }
        # Shared notification accounts and generic inboxes must never suggest
        # collapsing all of the humans named by that service into one person.
        if category == 'person':
            if address and not AUTOMATED.search(local) and local not in GENERIC:
                addresses[address].append(node.id)
            normalized = ' '.join((name if address else label).casefold().split())
            if normalized and '@' not in normalized:
                names[normalized].append(node.id)
    for groups, reason in [(addresses, 'same_mailbox'), (names, 'same_name')]:
        for group in groups.values():
            ids = [id for id in group if not metadata[id]['duplicate_ids']]
            if len(ids) < 2:
                continue
            for id in ids:
                # Exact mailbox groups take priority; only ungrouped names
                # receive weaker hints. Never create transitive identity groups.
                metadata[id]['duplicate_ids'] = sorted(other for other in ids if other != id)
                metadata[id]['duplicate_reason'] = reason
    return [replace(n, attributes={**n.attributes, **metadata[n.id]}) if n.id in metadata else n for n in nodes]
