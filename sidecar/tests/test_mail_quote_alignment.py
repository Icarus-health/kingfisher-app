"""Darstellungsabgleich bleibt eindeutig und liefert ausschließlich Originaltext."""
import json

import pytest

from icarus_memory.memory_analysis import interpret
from icarus_memory.providers import ProviderError, Reply


class Reader:
    is_local = True

    def __init__(self, quote):
        self.quote = quote

    def complete_json(self, messages, **kwargs):
        return Reply(text=json.dumps({'items': [{'title': 'Selbstauskunft übersenden', 'quote': self.quote}]}))


def extract(body, quote, context=None):
    return interpret(Reader(quote), 'Neue Nachricht', body, source_context=context)


@pytest.mark.parametrize('encoded', ['&Uuml;', '&#220;', '&#xDC;'])
def test_display_quote_maps_uniquely_back_to_raw_mail_span(encoded):
    raw = 'bitten wir\r\n> vorab um ' + encoded + 'bersendung Ihrer Selbstauskunft'
    body = 'Portalhinweis\r\n\r\n> Aufgrund der Nachfrage ' + raw + '.\r\n> Freundliche Grüße'
    found = extract(body, 'bitten wir vorab um Übersendung Ihrer Selbstauskunft', {'source_type': 'email'})
    assert found == [{'title': 'Selbstauskunft übersenden', 'quote': raw}]
    assert body[body.index(raw):body.index(raw) + len(raw)] == found[0]['quote']


def test_literal_path_is_unchanged_even_when_literal_quote_is_repeated():
    quote = 'Bitte die Selbstauskunft übersenden.'
    assert extract(quote + '\n\n' + quote, quote) == [
        {'title': 'Selbstauskunft übersenden', 'quote': quote}]


@pytest.mark.parametrize('context', [None, {}, {'source_type': 'document'}, {'source_type': 'chat'}])
def test_non_mail_and_unknown_context_keep_strict_original_evidence(context):
    with pytest.raises(ProviderError):
        extract('Bitte um &Uuml;bersendung Ihrer Selbstauskunft.',
                'Bitte um Übersendung Ihrer Selbstauskunft.', context)


@pytest.mark.parametrize('body,quote', [
    ('Bitte um &Uuml;bersendung.\nBitte um Übersendung.', 'Bitte  um Übersendung.'),
    ('Bitte nicht um &Uuml;bersendung.', 'Bitte um Übersendung.'),
    ('Bitte bis 01.01.2027 um &Uuml;bersendung.', 'Bitte bis 1.1.2027 um Übersendung.'),
    ('Bitte um &Uuml;bersendung von 100 Euro.', 'Bitte um Übersendung von 10 Euro.'),
    ('Bitte um &Uuml;bersendung.', 'bitte um Übersendung.'),
    ('Bitte &unknown; &Uuml;bersendung.', 'Bitte unknown Übersendung.'),
    ('Bitte &#x110000; &Uuml;bersendung.', 'Bitte � Übersendung.'),
    ('Bitte &#0; &Uuml;bersendung.', 'Bitte � Übersendung.'),
    ('Bitte &notanentity; &Uuml;bersendung.', 'Bitte ¬anentity; Übersendung.'),
    ('Bitte um &amp;Uuml;bersendung.', 'Bitte um Übersendung.'),
    ('Bitte &fjlig; Zahlungsdaten\nverwenden.', 'j Zahlungsdaten verwenden.'),
    ('Bitte Betrag\n> 10 Euro &uuml;berweisen.', 'Bitte Betrag 10 Euro überweisen.'),
    ('Bitte Betrag\n> Mindestbetrag &uuml;berweisen.', 'Bitte Betrag Mindestbetrag überweisen.'),
    ('Bitte Betrag\n> beliebiger benannter Wert &uuml;berweisen.',
     'Bitte Betrag beliebiger benannter Wert überweisen.'),
    ('Bitte Wert\n> x &uuml;bernehmen.', 'Bitte Wert x übernehmen.'),
    ('Bitte Wert\n>= Grenze &uuml;bernehmen.', 'Bitte Wert Grenze übernehmen.'),
    ('Bitte Wert\n>> vorab &uuml;bernehmen.', 'Bitte Wert vorab übernehmen.'),
    ('Bitte Betrag &gt; 10 Euro &uuml;berweisen.', 'Bitte Betrag 10 Euro überweisen.'),
    ('Bitte um\n>vorab &Uuml;bersendung.', 'Bitte um vorab Übersendung.'),
    ('Bitte um<br>&Uuml;bersendung.', 'Bitte um Übersendung.'),
    ('```\n> Bitte um &Uuml;bersendung.\n```', 'Bitte um Übersendung.'),
    ('> ```\n> Bitte um &Uuml;bersendung.\n> ```', 'Bitte um Übersendung.'),
])
def test_ambiguous_or_semantically_changed_quotes_are_rejected(body, quote):
    with pytest.raises(ProviderError):
        extract(body, quote, {'source_type': 'email'})


def test_comparison_operator_is_retained_while_entities_and_spaces_align():
    raw = 'Bitte Betrag &gt; 10\r\nEuro &uuml;berweisen.'
    assert extract(raw, 'Bitte Betrag > 10 Euro überweisen.', {'source_type': 'email'})[0]['quote'] == raw


def test_normalized_date_suffix_cannot_start_inside_a_numeric_token():
    with pytest.raises(ProviderError):
        extract('Termin 01.01.2027 &uuml;bernehmen.', '1.01.2027 übernehmen.', {'source_type': 'email'})


def test_alignment_exposes_original_offsets_and_requires_whole_entity():
    from icarus_memory.mail_quote_alignment import align
    body = 'Vorspann: Bitte um &Uuml;bersendung. Nachsatz.'
    assert align(body, 'Bitte um Übersendung.') == ('Bitte um &Uuml;bersendung.', 10, 36)
    assert align('Bitte &fjlig; Zahlungsdaten\nverwenden.', 'j Zahlungsdaten verwenden.') is None


def test_midline_quote_uses_prefix_proof_from_complete_original_paragraph():
    from icarus_memory.mail_quote_alignment import align
    raw = 'bitten wir \r\n> vorab um &Uuml;bersendung Ihrer Selbstauskunft'
    body = ('Portalhinweis\r\n\r\n> Viele Details stehen davor.\r\n'
            '> Aufgrund hoher Nachfrage ' + raw + '.\r\n> Freundliche Grüße\r\n\r\nNachsatz.')
    result = align(body, 'bitten wir vorab um Übersendung Ihrer Selbstauskunft')
    assert result == (raw, body.index('bitten wir'), body.index('bitten wir') + len(raw))


@pytest.mark.parametrize('body', [
    'Unmarkierte erste Zeile\n> Bitte um &Uuml;bersendung.',
    '> Bitte um &Uuml;bersendung.',
    '> Erste Zeile\nNicht zitiert\n> Bitte um &Uuml;bersendung.',
])
def test_single_or_mixed_quote_paragraph_has_no_prefix_proof(body):
    with pytest.raises(ProviderError):
        extract(body, 'Bitte um Übersendung.', {'source_type': 'email'})


@pytest.mark.parametrize('comparison', ['10 Euro', 'Mindestbetrag', 'x'])
def test_uniform_quote_paragraph_removes_only_outer_markup_not_inner_operator(comparison):
    body = '> Bitte Betrag\n> > ' + comparison + ' &uuml;berweisen.\n> Grüße'
    assert extract(body, 'Bitte Betrag > ' + comparison + ' überweisen.',
                   {'source_type': 'email'})[0]['quote'] == (
                       'Bitte Betrag\n> > ' + comparison + ' &uuml;berweisen.')
    with pytest.raises(ProviderError):
        extract(body, 'Bitte Betrag ' + comparison + ' überweisen.', {'source_type': 'email'})
