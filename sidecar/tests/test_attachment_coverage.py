"""Real bounded PDF parsing and durable coverage; no models or private mail."""
from dataclasses import replace
from datetime import datetime, timezone

import pytest

from icarus_memory import anhaenge
from icarus_memory.connectors.mail import Message
from icarus_memory.mail_ingestion import remember
from tests.test_anhaenge import pdf, mail_mit
from tests.test_context_identity import core  # noqa: F401
from tests.test_kreis import api  # noqa: F401


def test_mixed_pdf_keeps_readable_page_but_exposes_gap():
    item, = anhaenge.aus_mail(mail_mit(('Vertrag.pdf', pdf([['Deckblatt lesbar']], scan=1), 'application/pdf')))
    info = anhaenge.als_dict(item)
    assert info['vollstaendig'] is False
    assert info['ungelesene_seiten'] == [2]
    body = anhaenge.text(item, 'Vertrag', None)
    assert 'Deckblatt lesbar' in body
    assert 'Seite 2' in body and 'nicht vollständig' in body


def test_ocr_resolves_only_the_pages_it_actually_read():
    answers = iter(['Erkannte Seite', ''])
    item, = anhaenge.aus_mail(mail_mit(('Vertrag.pdf', pdf([['Deckblatt']], scan=2), 'application/pdf')),
                              ocr=lambda _: next(answers))
    assert anhaenge.als_dict(item)['vollstaendig'] is False
    assert anhaenge.als_dict(item)['ungelesene_seiten'] == [3]


def test_successful_ocr_leaves_no_unread_page_warning():
    item, = anhaenge.aus_mail(mail_mit(('Vertrag.pdf', pdf([['Deckblatt']], scan=1), 'application/pdf')),
                              ocr=lambda _: 'Erkannte Seite')
    assert anhaenge.als_dict(item)['vollstaendig'] is True
    assert anhaenge.als_dict(item)['ungelesene_seiten'] == []
    assert 'nicht vollständig' not in item.hinweis


def test_long_single_line_retains_beginning_and_never_spends_negative_budget():
    marker = 'ANFANG_DES_VERTRAGS '
    item = anhaenge.Anhang('Vertrag.pdf', 'pdf', anhaenge.GELESEN,
                          (marker + 'x' * anhaenge.MAX_ZEICHEN, 'y' * 190_000), 2)
    body = anhaenge.text(item, 'Vertrag', None)
    assert marker in body
    assert len(body) < anhaenge.MAX_ZEICHEN + 400
    assert 'y' * 20 not in body
    assert anhaenge.als_dict(item)['vollstaendig'] is False


def test_exact_first_page_budget_does_not_leak_second_page():
    item = anhaenge.Anhang('Vertrag.pdf', 'pdf', anhaenge.GELESEN,
                          ('x' * (anhaenge.MAX_ZEICHEN - len('Seite 1\n')), 'y\n' * 100_000), 2)
    body = anhaenge.text(item, '', None)
    assert len(body) < anhaenge.MAX_ZEICHEN + 400
    assert 'y\ny\ny' not in body
    assert 'Gekürzt' in body


def test_mail_report_counts_omitted_and_unsupported_files():
    report = {}
    files = [(f'Rechnung-{n}.pdf', pdf([[f'Beleg {n}']]), 'application/pdf') for n in range(6)]
    files.append(('Daten.csv', b'name,value\na,b', 'text/csv'))
    items = anhaenge.aus_mail(mail_mit(*files), bericht=report)
    assert len(items) == 5
    assert report['geprueft'] is True and report['vollstaendig'] is False
    assert report['ausgelassen'] == 1 and report['nicht_unterstuetzt'] == 1
    assert report['gefunden'] == 7 and report['gelesen'] == 5
    assert 'nicht vollständig' in report['hinweis']


def test_truncated_wire_cannot_report_complete_even_without_visible_part():
    report = {}
    anhaenge.aus_mail(mail_mit(), abgeschnitten=True, bericht=report)
    assert report['vollstaendig'] is False
    assert 'unvollständig' in report['hinweis']


def test_unnamed_attachment_is_never_proof_of_absence():
    from email.message import EmailMessage
    raw = mail_mit()
    part = EmailMessage()
    part.set_content(pdf([['Anlage ohne Dateiname']]), maintype='application', subtype='pdf')
    part['Content-Disposition'] = 'attachment'
    raw.make_mixed()
    raw.attach(part)
    report = {}
    anhaenge.aus_mail(raw, bericht=report)
    assert report['gefunden'] == 1 and report['unbenannt'] == 1
    assert report['vollstaendig'] is False and report['zuordnung_vollstaendig'] is False


def test_malformed_mime_is_never_proof_of_absence():
    from email import message_from_bytes
    raw = message_from_bytes(b'MIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary="missing"\r\n\r\nbroken structure')
    report = {}
    assert anhaenge.aus_mail(raw, bericht=report) == ()
    assert report['abruf_vollstaendig'] is True
    assert report['mime_fehler'] > 0
    assert report['vollstaendig'] is False and report['zuordnung_vollstaendig'] is False


def test_partial_attachments_and_mail_report_survive_recapture(api):
    app, client = api
    report = {}
    items = anhaenge.aus_mail(mail_mit(('Vertrag.pdf', pdf([['Text']], scan=1), 'application/pdf')), bericht=report)
    message = Message('qa:1', 'Vertrag', 'QA <qa@example.test>', datetime.now(timezone.utc), '', False,
                      body='Anbei.', account_id='qa', anhaenge=items, anhang_bericht=report)
    first = remember(app.state.episodes, message, claims=app.state.claims)
    parent = first['episode']['id']
    child, = first['anhaenge']
    assert 'source:truncated' in app.state.episodes.get(child).tags
    saved = client.get(f'/api/v1/episodes/{parent}').json()
    assert saved['attachment_coverage']['vollstaendig'] is False
    assert saved['body'] == 'Anbei.'
    # A regular message view does not fetch attachments and must not erase its coverage.
    again = remember(app.state.episodes, replace(message, anhaenge=(), anhang_bericht=None), claims=app.state.claims)
    assert again['episode']['id'] == parent and not again['new']
    assert client.get(f'/api/v1/episodes/{parent}').json()['attachment_coverage'] == saved['attachment_coverage']
    assert saved['attachment_sources'] == [{'id': child, 'title': app.state.episodes.get(child).title}]


def test_observed_absence_requires_complete_mime_without_count_limit(api):
    app, _ = api
    item = anhaenge.Anhang('Vertrag.pdf', 'pdf', anhaenge.GELESEN, ('Quelle 4711',), 1)
    original = Message('qa:2', 'Vertrag', 'QA <qa@example.test>', datetime.now(timezone.utc), '', False,
                       body='Anbei.', account_id='qa', anhaenge=(item,))
    result = remember(app.state.episodes, original, claims=app.state.claims)
    child, = result['anhaenge']
    for report in (None, {'geprueft': True, 'abruf_vollstaendig': False, 'zuordnung_vollstaendig': True, 'ausgelassen': 0},
                   {'geprueft': True, 'abruf_vollstaendig': True, 'zuordnung_vollstaendig': True, 'ausgelassen': 1},
                   {'geprueft': True, 'abruf_vollstaendig': True, 'zuordnung_vollstaendig': False, 'ausgelassen': 0}):
        remember(app.state.episodes, replace(original, anhaenge=(), anhang_bericht=report), claims=app.state.claims)
        assert app.state.episodes.support_snapshot(child).current()
    remember(app.state.episodes, replace(original, anhaenge=(),
             anhang_bericht={'geprueft': True, 'abruf_vollstaendig': True, 'zuordnung_vollstaendig': True, 'ausgelassen': 0}), claims=app.state.claims)
    assert app.state.episodes.get(child).state.value == 'ignored'
    assert not app.state.episodes.support_snapshot(child).current()
    assert 'Quelle 4711' in app.state.episodes.get(child).body


@pytest.mark.parametrize('legacy_report', [False, True])
def test_partial_wire_refresh_preserves_previous_complete_source_and_child_support(api, legacy_report):
    app, client = api
    item = anhaenge.Anhang('Vertrag.pdf', 'pdf', anhaenge.GELESEN, ('Vollständiger Text 4711',), 1)
    original = Message('qa:3', 'Vertrag', 'QA <qa@example.test>', datetime.now(timezone.utc), '', False,
                       body='Vollständige Mail', account_id='qa', anhaenge=(item,))
    result = remember(app.state.episodes, original, claims=app.state.claims)
    parent = result['episode']['id']
    child, = result['anhaenge']
    before = app.state.episodes.support_snapshot(child).support_fingerprint()
    placeholder = anhaenge.Anhang('Vertrag.pdf', 'pdf', anhaenge.ZU_GROSS, hinweis='Abruf unvollständig')
    refresh = replace(original, body='Vollst', truncated=not legacy_report, anhaenge=(placeholder,),
                      anhang_bericht={'geprueft': True, 'abruf_vollstaendig': legacy_report, 'ausgelassen': 0,
                                      'hinweis': 'Abruf unvollständig'})
    after = remember(app.state.episodes, refresh, claims=app.state.claims)
    assert after['episode']['id'] == parent and after['episode']['body'] == original.body
    assert after['anhaenge'] == []
    assert app.state.episodes.support_snapshot(child).current()
    assert app.state.episodes.support_snapshot(child).support_fingerprint() == before
    saved = client.get(f'/api/v1/episodes/{parent}').json()
    assert saved['attachment_coverage']['vorherige_fassung_beibehalten'] is True
    assert saved['attachment_sources'][0]['id'] == child
