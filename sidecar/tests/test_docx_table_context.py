"""Word-Zellen behalten zusammengehörige Absätze, Zeilen und leere Nachbarfelder."""
from html import escape
from io import BytesIO
from zipfile import ZipFile

import pytest

from icarus_memory import absatzauswahl, document_text as dt, satzantwort, satzpruefung, working_memory_answers as wma
from icarus_memory.akten_kontext import Kontext
from icarus_memory.mail_ingestion import remember
from icarus_memory.working_memory_analysis import _blocks
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_answer_source_boundaries import antwort, Auswahl, REGEL, stores  # noqa: F401
from tests.test_mail_docx_attachments import fetch, DOCX_MIME


def p(text):
    return '<w:p><w:r><w:t>' + escape(text) + '</w:t></w:r></w:p>'


def packed(body):
    stream = BytesIO()
    with ZipFile(stream, 'w') as archive:
        archive.writestr('word/document.xml',
            f'<w:document xmlns:w="{dt.NAMESPACE}"><w:body>{body}</w:body></w:document>')
    return stream.getvalue()


def formular(*, lange_felder=False):
    kontakt = (''.join(p(f'Kontaktfeld {i}: Verwaltung Musterwerk Nord Musterweg Musterstadt') for i in range(7))
               + p('Abschließende Formularinformation.') if lange_felder else
               ''.join(p(f'Anschrift und Kontaktinformation {i}: Musterweg, Musterstadt.') for i in range(20)))
    return packed(p(REGEL)
        + ''.join(p(f'Allgemeine Formularinformation {i}: Bitte prüfen Sie die Schreibweise der Stammdaten.')
                  for i in range(18))
        + '<w:tbl><w:tr><w:tc>' + p('Beschäftigungsbeginn:') + p('18.11.2026') + '</w:tc>'
        + '<w:tc>' + p('Rücksendedatum:') + p('') + '</w:tc></w:tr></w:tbl>'
        + kontakt)


def mime_antwort(stores, monkeypatch, *, lange_felder=False):
    episodes, claims = stores
    message = fetch(monkeypatch, ('Personalformular.docx', formular(lange_felder=lange_felder), DOCX_MIME))
    child_id, = remember(episodes, message, claims=claims)['anhaenge']
    episode = episodes.get(child_id)
    store = WorkingMemoryStore(episodes)
    assert store.commit(episodes.support_snapshot(child_id),
        [{'start': s, 'end': e, 'kind': 'fact'} for s, e in _blocks(episode.body)], model='synthetic')
    provider = Auswahl('Beschäftigungsbeginn:\n18.11.2026')
    question = 'Wann ist der Beschäftigungsbeginn?'
    saved = wma.prepare(question, episodes, claims, provider, saetze=True, semantic_search=None)
    belege, _ = satzantwort.belege_sammeln(saved['refs'], Kontext.aus_dict(saved.get('akten')) or Kontext(),
        episodes, claims, woerter=absatzauswahl.Suchwoerter.aus(question))
    rendered, _, _ = wma.render(saved, episodes, claims)
    assert episodes.get(child_id).body == episode.body
    return episode, saved, belege, rendered, provider


def test_echter_mime_anhang_tabellenfeld_ist_noch_keine_kurze_satzantwort(stores, monkeypatch):
    episode, saved, _, rendered, _ = mime_antwort(stores, monkeypatch)
    assert 'Beschäftigungsbeginn:\n18.11.2026\tRücksendedatum:' in episode.body
    assert episode.body.startswith('Anhang „Personalformular.docx“ der Mail „')
    # Bewusste Integrationsgrenze: Der erzeugte Header steht noch im Prüfvolltext.
    assert saved['satzantwort']['status'] == 'zitate'
    assert episode.body in rendered


def test_lange_originalkette_nur_durch_kurze_native_id_und_nie_ohne_aktives_tor(stores, monkeypatch):
    episode, saved, _, _, provider = mime_antwort(stores, monkeypatch, lange_felder=True)
    units = [t for _, _, t in satzpruefung.originalabschnitt_stellen(episode.body)
             if 'Beschäftigungsbeginn:\n18.11.2026' in t]
    assert len(units) == 1 and len(units[0]) > satzantwort.MAX_SATZ_ZEICHEN
    assert saved['satzantwort']['status'] == 'zitate'
    offered = [s['text'] for b in provider.satzanfragen[0]['belege'] for s in b['originalsaetze']]
    assert units[0] not in offered and all(len(t) <= satzantwort.MAX_SATZ_ZEICHEN for t in offered)
    assert 'Beschäftigungsbeginn:\n18.11.2026\tRücksendedatum:' in offered


def test_feldlabel_und_wert_aus_zwei_zellabsaetzen_bleiben_im_selben_quellenblock():
    text = dt.docx_text(formular())
    zeile = 'Beschäftigungsbeginn:\n18.11.2026\tRücksendedatum:'
    assert zeile in text
    blocks = [text[start:end] for start, end in _blocks(text)]
    assert zeile in blocks
    assert 'Beschäftigungsbeginn:' not in blocks and '18.11.2026' not in blocks
    assert REGEL in blocks


def test_word_tabellenfeld_erreicht_den_store_und_die_kurze_belegte_antwort(stores):
    text = dt.docx_text(formular())
    saved, _, rendered, _ = antwort(stores, text, 'Personalformular Beschäftigungsbeginn',
        'Wann ist der Beschäftigungsbeginn?', 'Beschäftigungsbeginn:\n18.11.2026')
    assert saved['satzantwort']['status'] == 'saetze'
    assert 'Beschäftigungsbeginn:\n18.11.2026' in rendered and len(rendered) < 500
    episodes, _ = stores
    refs = WorkingMemoryStore(episodes).source_refs(episode_ids=[saved['refs'][0]['episode_id']], limit=64)['refs']
    spans = [episodes.get(ref['episode_id']).body[ref['start']:ref['end']] for ref in refs]
    mit_label = [span for span in spans if 'Beschäftigungsbeginn:' in span]
    assert mit_label and all('18.11.2026' in span for span in mit_label)


def test_leeres_ruecksendedatum_wird_nicht_aus_nachbarzelle_geraten(stores):
    text = dt.docx_text(formular())
    saved, _, _, provider = antwort(stores, text, 'Personalformular Rücksendedatum und Beschäftigungsbeginn',
        'Bis wann muss ich das Formular zurücksenden?', 'Beschäftigungsbeginn:\n18.11.2026', leer=True)
    assert provider.satzanfragen
    assert saved['satzantwort']['status'] == 'nichts' and not saved['satzantwort'].get('saetze')


def test_erfundene_zuordnung_des_nachbardatums_zum_ruecksendefeld_wird_verworfen(stores):
    from tests.test_satzantwort import Skript
    provider = Skript({'status': 'antwort', 'saetze': [{'text': 'Rücksendedatum: 18.11.2026', 'belege': [1]}]})
    text = dt.docx_text(formular())
    saved, _, _, _ = antwort(stores, text, 'Personalformular Rücksendedatum und Beschäftigungsbeginn',
        'Bis wann muss ich das Formular zurücksenden?', 'Beschäftigungsbeginn:\n18.11.2026', provider=provider)
    assert saved['satzantwort']['status'] == 'zitate' and saved['satzantwort']['verworfen'] > 0


def test_mehrere_zeilen_zellen_leere_zellen_und_normale_bodyabsaetze_bleiben_getrennt():
    data = packed(p('Davor.') + '<w:tbl><w:tr>'
        '<w:tc>' + p('A') + p('B') + '</w:tc><w:tc>' + p('') + '</w:tc><w:tc>' + p('C') + '</w:tc>'
        '</w:tr><w:tr><w:tc>' + p('D') + '</w:tc><w:tc>' + p('E') + '</w:tc></w:tr></w:tbl>'
        + p('Danach.') + p('Ein weiterer Absatz.'))
    assert dt.docx_text(data) == 'Davor.\n\nA\nB\t\tC\n\nD\tE\n\nDanach.\n\nEin weiterer Absatz.'


def test_zellinterner_br_bleibt_umbruch_und_verworfene_texte_bleiben_entfernt():
    data = packed('<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A</w:t><w:br/><w:t>B</w:t></w:r>'
        '<w:del><w:r><w:t>GELÖSCHT</w:t></w:r></w:del>'
        '<w:moveFrom><w:r><w:t>VERSCHOBEN</w:t></w:r></w:moveFrom></w:p>'
        + p('C') + '</w:tc><w:tc>' + p('D') + '</w:tc></w:tr></w:tbl>')
    assert dt.docx_text(data) == 'A\nB\nC\tD'


def test_verschachtelte_tabelle_hat_eigene_zeilen_und_jeden_text_genau_einmal():
    data = packed(p('Davor.') + '<w:tbl><w:tr><w:tc>' + p('Außen davor')
        + '<w:tbl><w:tr><w:tc>' + p('Innen A') + '</w:tc><w:tc>' + p('Innen B')
        + '</w:tc></w:tr></w:tbl>' + p('Außen danach')
        + '</w:tc><w:tc>' + p('Andere Zelle') + '</w:tc></w:tr></w:tbl>' + p('Danach.'))
    text = dt.docx_text(data)
    assert [text[a:b] for a, b in _blocks(text)] == [
        'Davor.', 'Außen davor', 'Innen A\tInnen B', 'Außen danach\tAndere Zelle', 'Danach.']
    assert all(text.count(wort) == 1 for wort in ('Außen davor', 'Innen A', 'Innen B', 'Außen danach', 'Andere Zelle'))


def test_zellabsaetze_trennen_keinen_regelnachsatz_ab():
    from icarus_memory import satzantwort as sa
    from tests.test_original_sentence_selection import Selector, NOW

    text = dt.docx_text(packed('<w:tbl><w:tr><w:tc>'
        + p('Die Klappe darf geöffnet werden.') + p('Dies gilt ausschließlich während der Prüfung.')
        + '</w:tc></w:tr></w:tbl>'))
    assert len(_blocks(text)) == 1
    beleg = sa.AntwortBeleg(1, {}, 'Quelle', 'synthetic', 'Klappe', '', text, None)
    provider = Selector({'status': 'antwort', 'saetze': [{'text': 'Die Klappe darf geöffnet werden.', 'belege': [1]}]})
    assert sa.formulieren('Was gilt?', [beleg], provider, jetzt=NOW).status == 'zitate'


def test_wenn_dann_ueber_zwei_tabellenzeilen_bleibt_zusammen():
    text = dt.docx_text(packed('<w:tbl><w:tr><w:tc>' + p('Wenn die Prüfung abgeschlossen ist,')
        + '</w:tc></w:tr><w:tr><w:tc>' + p('dann darf die Klappe geöffnet werden.') + '</w:tc></w:tr></w:tbl>'))
    assert text == 'Wenn die Prüfung abgeschlossen ist,\n\ndann darf die Klappe geöffnet werden.'
    assert len(_blocks(text)) == 1


@pytest.mark.parametrize('budget,erlaubt', [(5, False), (6, True)])
def test_textbudget_zaehlt_utf8_und_zellseparatoren(monkeypatch, budget, erlaubt):
    data = packed('<w:tbl><w:tr><w:tc>' + p('Ä') + p('B') + '</w:tc><w:tc>' + p('C') + '</w:tc></w:tr></w:tbl>')
    monkeypatch.setattr(dt, 'MAX_TEXT', budget)
    if erlaubt:
        assert dt.docx_text(data) == 'Ä\nB\tC'  # sechs UTF-8-Bytes, einschließlich LF und Tab
    else:
        with pytest.raises(ValueError, match='512 KiB'):
            dt.docx_text(data)


@pytest.mark.parametrize('gate', ['MAX_FILE', 'MAX_XML'])
def test_paket_und_xmlbudget_bleiben_vor_dem_tabellenlesen_aktiv(monkeypatch, gate):
    data = packed('<w:tbl><w:tr><w:tc>' + p('Kleiner Inhalt') + '</w:tc></w:tr></w:tbl>')
    monkeypatch.setattr(dt, gate, 10)
    with pytest.raises(ValueError):
        dt.docx_text(data)


def test_leere_tabelle_und_extreme_xmlverschachtelung_bleiben_abgelehnt():
    with pytest.raises(ValueError):
        dt.docx_text(packed('<w:tbl><w:tr><w:tc>' + p('') + '</w:tc></w:tr></w:tbl>'))
    with pytest.raises(ValueError, match='verschachtelt'):
        dt.docx_text(packed('<w:tbl><w:tr><w:tc>' + '<w:sdt>' * 2000 + p('Text')
                           + '</w:sdt>' * 2000 + '</w:tc></w:tr></w:tbl>'))
