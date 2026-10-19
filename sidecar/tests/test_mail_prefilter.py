"""Synthetic metadata-only screening never removes mail or calls a model."""
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from icarus_memory import mail_filter
from icarus_memory.connectors.mail import Message, _decode
from icarus_memory.episodes import Episode, EpisodeKind, EpisodeState
from icarus_memory.model import Provenance, SourceType


def message(**changes):
    return Message(**{'uid': '1.1', 'subject': 'Termin', 'sender': 'Lea <lea@example.org>',
                      'date': None, 'preview': 'Synthetic source', 'unread': True,
                      'body': 'Synthetic source', **changes})


def episode(**changes):
    return Episode(**{'id': 'synthetic-source', 'kind': EpisodeKind.MESSAGE,
                      'title': 'Termin', 'body': 'Synthetic source',
                      'provenance': Provenance(SourceType.EMAIL, source_ref='work:imap:1.1'),
                      'recorded_at': datetime(2026, 10, 19, tzinfo=timezone.utc),
                      'participants': ['Lea <lea@example.org>'], **changes})


@pytest.mark.parametrize(('sender', 'subject'), [
    ('Facebook <friendupdates@facebookmail.com>', 'People you may know'),
    ('LinkedIn <notifications-noreply@linkedin.com>', 'Neue Kontaktvorschläge für dich'),
    ('Shop <newsletter@shop.example>', 'Nur heute: 30 % Rabatt auf alles'),
    ('Deals <deals@shop.example>', 'Save 25% in our sale'),
])
def test_clear_sender_subject_combinations_skip_before_any_model(sender, subject):
    class NeverCall:
        is_local = True
        def complete_json(self, *args):
            pytest.fail('Obvious marketing must be held before a model call')

    result = mail_filter.classify(message(sender=sender, subject=subject), {'ai_enabled': True}, NeverCall())
    assert not result.include and result.category == 'newsletter'
    assert result.reason == 'sender_subject_marketing'


def test_explicit_newsletter_opt_in_and_whitelist_override_heuristics():
    promo = message(sender='newsletter@shop.example', subject='Heute: 30% Rabatt', list_mail=True)
    assert mail_filter.classify(promo, {'block_newsletters': False}).include
    assert mail_filter.classify(promo, {'allowed': ['newsletter@shop.example'], 'ai_enabled': True}).include
    assert mail_filter.classify(promo, {'allowed': ['@shop.example'], 'ai_enabled': True}).include
    assert not mail_filter.classify(promo, {'allowed': ['@shop.example'], 'blocked': ['newsletter@shop.example']}).include
    assert mail_filter.classify(message(sender=promo.sender, spam_flag=True), {'allowed': ['@shop.example']}).category == 'spam'


def test_existing_exact_rules_continue_to_match_international_mailboxes():
    candidate = message(sender='Sören <sören@example.org>')
    assert mail_filter.classify(candidate, {'blocked': ['sören@example.org']}).category == 'blocked'
    assert mail_filter.classify(candidate, {'allowed': ['sören@example.org'], 'ai_enabled': True}).include


@pytest.mark.parametrize('whitespace', [' ', '\t', ' \t'])
def test_folded_from_headers_keep_explicit_allow_and_block_rules(whitespace):
    # The connector decodes MIME but preserves legal folding in a plain From.
    candidate = message(sender=_decode('Shop\r\n' + whitespace + '<newsletter@shop.example>'),
                        subject='30% Rabatt')
    assert mail_filter.classify(candidate, {'allowed': ['@shop.example'], 'ai_enabled': True}).include
    blocked = mail_filter.classify(candidate, {'blocked': ['@shop.example']})
    assert not blocked.include and blocked.category == 'blocked'
    source = episode(title=candidate.subject, participants=[candidate.sender])
    assert mail_filter.classify_episode(source, {'allowed': ['@shop.example'], 'ai_enabled': True}).include


@pytest.mark.parametrize('sender', [
    'Shop\r\nBcc: newsletter@shop.example',
    'Shop\n <newsletter@shop.example>',
    'Shop\r <newsletter@shop.example>',
    'Shop\r\n <newsletter@shop.example>,\r\n Lea <lea@example.org>',
    'Shop\r\n Bcc: victim@example.org\r\n <newsletter@shop.example>',
])
def test_unfolding_does_not_accept_header_injection_or_multiple_senders(sender):
    result = mail_filter.classify(message(sender=sender), {'allowed': ['@shop.example'], 'ai_enabled': True})
    assert not result.include and result.category == 'unclear'


def test_reference_only_reply_is_not_a_marketing_newsletter():
    candidate = message(sender='marketing@firma.example', subject='30% Rabatt wie besprochen',
                        references=('<synthetic-earlier-message@firma.example>',))
    assert mail_filter.classify(candidate, {}).include
    result = mail_filter.classify(candidate, {'ai_enabled': True})
    assert not result.include and result.category == 'unclear'


def test_facebook_tagged_updates_need_the_narrow_friend_suggestion_shape():
    candidate = message(sender='Facebook <update+opaque-token@facebookmail.com>',
                        subject='Kennst du Ada Beispiel, Ben Example und Cara Muster?')
    result = mail_filter.classify(candidate, {})
    assert not result.include and result.reason == 'sender_subject_marketing'
    assert mail_filter.classify(candidate, {'allowed': ['@facebookmail.com']}).include
    assert mail_filter.classify(candidate, {'block_newsletters': False}).include
    source = episode(title=candidate.subject, participants=[candidate.sender])
    assert not mail_filter.classify_episode(source, {}).include
    for changes in [
        {'sender': 'Facebook <update+opaque-token@notfacebookmail.com>'},
        {'sender': 'Facebook <update+opaque-token@linkedin.com>'},
        {'sender': 'Lea <lea@facebookmail.com>'},
        {'subject': 'Re: ' + candidate.subject},
        {'subject': 'Kennst du die Rechnung für 20% Rabatt?'},
        {'in_reply_to': '<synthetic-project-reply@example.org>'},
    ]:
        data = {'sender': candidate.sender, 'subject': candidate.subject, **changes}
        assert mail_filter.classify(message(**data), {}).include


@pytest.mark.parametrize(('sender', 'subject'), [
    ('noreply@service.example', 'Your invoice and receipt'),
    ('info@shared.example', 'Projektangebot: 20% Rabatt besprechen'),
    ('Anna Rabatt <anna@personal.example>', '30% Rabatt: bitte im Angebot prüfen'),
    ('Lea <lea@linkedin.com>', 'People you may know'),
    ('notifications-noreply@notlinkedin.com', 'People you may know'),
    ('notifications-noreply@linkedin.com.attacker.example', 'People you may know'),
    ('newsletter.shop@personal.example', '30% Rabatt'),
    ('sales@company.example', 'Work offer with 20% discount'),
])
def test_names_domain_fragments_and_shared_inboxes_are_not_marketing(sender, subject):
    assert mail_filter.classify(message(sender=sender, subject=subject), {}).include


@pytest.mark.parametrize('subject', [
    'Re: Nur heute: 30% Rabatt', 'AW: Nur heute: 30% Rabatt',
    'Fwd: Nur heute: 30% Rabatt', 'WG: Nur heute: 30% Rabatt',
    'Rechnung mit 30% Rabatt', 'Invoice: 30% discount', 'Receipt: 30% discount',
    'Booking confirmation: 30% discount', 'Buchung: 30% Rabatt',
    'Auftragsbestätigung: 30% Rabatt', 'Job offer: 30% discount',
    'Projektangebot mit 30% Rabatt',
])
def test_replies_transactions_and_work_are_preserved_even_from_marketing_mailboxes(subject):
    assert mail_filter.classify(message(sender='newsletter@shop.example', subject=subject), {}).include


def test_rfc2047_subjects_are_decoded_without_classifying_display_names():
    encoded = message(sender='=?utf-8?q?Shop?= <newsletter@shop.example>',
                      subject='=?utf-8?q?Heute=3A_30_=25_Rabatt?=')
    assert not mail_filter.classify(encoded, {}).include
    assert mail_filter.classify(message(sender='=?utf-8?q?Newsletter?= <lea@example.org>',
                                       subject=encoded.subject), {}).include


def test_long_or_defective_headers_are_not_partially_used_as_marketing_proof():
    candidate = message(sender='newsletter@shop.example',
                        subject='30% Rabatt ' + 'x' * 2100 + ' Rechnung')
    assert mail_filter.classify(candidate, {}).include
    for subject in (None, '', '=?unknown-codec?b?MzAlIFJhYmF0dA==?=', '30% Rabatt\0'):
        assert mail_filter.classify(message(sender=candidate.sender, subject=subject), {}).include


@pytest.mark.parametrize('sender', ['', None, 'not an address', 'newsletter@',
                                    'newsletter@shop..example', 'newsletter@shop.example, lea@example.org'])
def test_invalid_or_ambiguous_sender_never_proves_marketing(sender):
    candidate = message(sender=sender, subject='Heute: 30% Rabatt')
    assert mail_filter.classify(candidate, {}).include
    result = mail_filter.classify(candidate, {'ai_enabled': True})
    assert not result.include and result.category == 'unclear'


def test_stored_mail_uses_role_aware_sender_and_has_no_source_side_effects():
    source = episode(title='Heute: 30% Rabatt', participants=['Lea <lea@example.org>', 'newsletter@shop.example'],
                     contacts=[{'name': 'Lea', 'adresse': 'lea@example.org', 'rolle': 'an', 'ich': True},
                               {'name': 'Shop', 'adresse': 'newsletter@shop.example', 'rolle': 'von', 'ich': False}])
    before = deepcopy(source.to_dict())
    result = mail_filter.classify_episode(source, {})
    assert not result.include and result.category == 'newsletter'
    assert source.to_dict() == before
    # A recipient's newsletter address is never guessed to be the sender.
    source.contacts[1]['rolle'] = 'cc'
    assert mail_filter.classify_episode(source, {}).include


def test_stored_mail_respects_current_rules_and_does_not_infer_sender_from_source_ref():
    source = episode(title='Heute: 30% Rabatt', participants=['newsletter@shop.example'])
    assert not mail_filter.classify_episode(source, {}).include
    assert mail_filter.classify_episode(source, {'block_newsletters': False}).include
    assert mail_filter.classify_episode(source, {'allowed': ['@shop.example'], 'ai_enabled': True}).include
    assert mail_filter.classify_episode(source, {'blocked': ['@shop.example']}).category == 'blocked'
    # source_ref is an opaque account/message identity, not a sender address.
    source.participants = []
    source.provenance.source_ref = 'newsletter@shop.example'
    assert mail_filter.classify_episode(source, {}).include


def test_unknown_stored_mail_keeps_legacy_default_and_holds_when_ai_required():
    source = episode(participants=[])
    assert mail_filter.classify_episode(source, {}).include
    result = mail_filter.classify_episode(source, {'ai_enabled': True})
    assert not result.include and result.category == 'unclear' and result.reason == 'ai_unavailable'


def test_stored_mail_reply_tags_prevent_marketing_heuristic():
    source = episode(title='Heute: 30% Rabatt', participants=['newsletter@shop.example'],
                     tags=['mail:reply:' + 'a' * 64])
    assert mail_filter.classify_episode(source, {}).include


def test_explicit_source_rejection_cannot_be_overridden_by_allowed_sender():
    source = episode(state=EpisodeState.IGNORED)
    result = mail_filter.classify_episode(source, {'allowed': ['@example.org']})
    assert not result.include and result.reason == 'source_ignored'


def test_non_mail_source_is_not_filtered_by_email_subject_rules():
    source = episode(title='Heute: 30% Rabatt', participants=['newsletter@shop.example'],
                     provenance=Provenance(SourceType.DOCUMENT, source_ref='synthetic-document'))
    assert mail_filter.classify_episode(source, {'blocked': ['@shop.example'], 'ai_enabled': True}).include
