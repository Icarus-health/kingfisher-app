"""Native Feldzeile: echte MIME-Provenienz statt Header oder langer Satzkette."""
import json
import copy
from dataclasses import replace

import pytest

from icarus_memory import absatzauswahl, docx_native_rows as native, satzantwort as sa, satzpruefung_modell as spm, working_memory_answers as wma
from icarus_memory.akten_kontext import Kontext
from icarus_memory.mail_ingestion import remember
from icarus_memory.working_memory_analysis import _blocks
from icarus_memory.working_memory_store import WorkingMemoryStore
from tests.test_answer_source_boundaries import Auswahl, REGEL, stores  # noqa: F401
from tests.test_docx_table_context import p, packed
from tests.test_mail_docx_attachments import fetch, DOCX_MIME
from tests.test_satzpruefung_modell import Pruefer

LABEL = 'beginn der tätigkeit:'
ROW = LABEL + '\n18.11.2026\tfrist der rücksendung:'


def form(label=LABEL, value='18.11.2026', extra='', row_extra=''):
    return packed(p(REGEL) + extra + '<w:tbl><w:tr><w:tc>' + p(label) + p(value)
        + '</w:tc><w:tc>' + p('frist der rücksendung:') + row_extra + '</w:tc></w:tr></w:tbl>'
        + ''.join(p(f'Kontaktfeld {i}: Verwaltung Musterwerk Nord Musterweg Musterstadt') for i in range(7))
        + p('Abschließende Formularinformation.'))


def capture(stores, monkeypatch, data=None, *, logo=False, transform=None):
    episodes, claims = stores
    files = [('Personalformular.docx', data or form(), DOCX_MIME)]
    if logo:
        files.append(('Logo.png', b'synthetic-unsupported-logo', 'image/png'))
    message = fetch(monkeypatch, *files)
    if logo:
        assert message.anhang_bericht['vollstaendig'] is False
        assert message.anhang_bericht['nicht_unterstuetzt'] == 1
        assert len(message.anhaenge) == 1 and message.anhaenge[0].art == 'docx'
    if transform:
        message = transform(message)
    result = remember(episodes, message, claims=claims)
    child, = result['anhaenge']
    episode = episodes.get(child)
    store = WorkingMemoryStore(episodes)
    assert store.commit(episodes.support_snapshot(child),
        [{'start': a, 'end': b, 'kind': 'fact'} for a, b in _blocks(episode.body)], model='synthetic')
    return episode, result['episode']['id']


def prepare(stores, *, leer=False, judge=None, question='Wann ist der beginn der tätigkeit?', needle=LABEL + '\n18.11.2026', provider=None):
    provider = provider or Auswahl(needle, leer=leer)
    saved = wma.prepare(question, *stores, provider, saetze=True, semantic_search=None,
                        pruefung=spm.tor('an', judge) if judge else None)
    belege, _ = sa.belege_sammeln(saved['refs'], Kontext.aus_dict(saved.get('akten')) or Kontext(), *stores,
                                 woerter=absatzauswahl.Suchwoerter.aus(question))
    rendered, _, _ = wma.render(saved, *stores)
    return saved, belege, rendered, provider


def test_echte_mime_native_zeile_aus_langer_originalkette_mit_header_ist_roher_quellenbericht(stores, monkeypatch):
    source, _ = capture(stores, monkeypatch)
    judge = Pruefer()
    saved, belege, rendered, provider = prepare(stores, judge=judge)
    assert saved['satzantwort']['status'] == 'saetze'
    assert saved['satzantwort']['saetze'][0]['roh'] == ROW
    assert 'Quelle berichtet: „' + ROW + '“' in rendered and len(rendered) < 600
    assert provider.satzanfragen and judge.anfragen
    assert all(source.body in json.loads(request[-1]['content'])['belege'] for request in judge.anfragen)
    assert all((b.pruef_text or b.text) == source.body for b in belege)
    assert stores[0].get(source.id).body == source.body


@pytest.mark.parametrize('label,value', [('Prüfdatum', '18.11.2026'), ('Bearbeitungsnummer', '12345')])
def test_einwortlabels_ohne_doppelpunkt_sind_nur_literale_zeilen(stores, monkeypatch, label, value):
    source, _ = capture(stores, monkeypatch, form(label=label, value=value))
    saved, _, rendered, _ = prepare(stores, judge=Pruefer(), needle=label + '\n' + value,
                                    question='Welchen Feld-Datensatz nennt das Personalformular?')
    row = label + '\n' + value + '\tfrist der rücksendung:'
    assert saved['satzantwort']['status'] == 'saetze'
    assert saved['satzantwort']['saetze'][0]['roh'] == row
    assert 'Quelle berichtet: „' + row + '“' in rendered and source.body not in rendered


def test_native_zeile_mit_mehreren_feldern_leerem_feld_und_layoutspaces_bleibt_woertlich(stores, monkeypatch):
    row = 'Prüfdatum\n18.11.2026\tErstprüfung\n18.11.2026       \tPrüfstelle'
    data = packed(p(REGEL) + '<w:tbl><w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026')
        + '</w:tc><w:tc>' + p('Erstprüfung') + p('18.11.2026       ') + '</w:tc><w:tc>'
        + p('Prüfstelle') + '</w:tc></w:tr></w:tbl>')
    capture(stores, monkeypatch, data)
    saved, _, rendered, _ = prepare(stores, judge=Pruefer(), needle='Prüfdatum\n18.11.2026',
                                    question='Welchen Feld-Datensatz nennt das Personalformular?')
    assert saved['satzantwort']['status'] == 'saetze' and saved['satzantwort']['saetze'][0]['roh'] == row
    assert 'Quelle berichtet: „' + row + '“' in rendered


def test_anna_ist_hoechstens_opaque_label_im_quellenbericht(stores, monkeypatch):
    assert stores[1].all_claims() == []
    capture(stores, monkeypatch, form(label='Anna'))
    saved, _, rendered, _ = prepare(stores, judge=Pruefer(), needle='Anna\n18.11.2026',
                                    question='Welchen Feld-Datensatz nennt das Personalformular?')
    assert saved['satzantwort']['status'] == 'saetze'
    assert 'Quelle berichtet: „Anna\n18.11.2026\tfrist der rücksendung:“' in rendered
    assert 'Anna beginnt' not in rendered and 'Anna ist' not in rendered
    assert stores[1].all_claims() == []


@pytest.mark.parametrize('verdict', ['nein', 'unklar'])
def test_leere_ruecksendefrist_darf_nicht_aus_anderem_felddatum_beantwortet_werden(stores, monkeypatch, verdict):
    source, _ = capture(stores, monkeypatch, form(label='Prüfdatum'))
    judge = Pruefer(standard=json.dumps({'urteil': verdict}))
    question = 'Bis wann muss ich das Personalformular zurücksenden?'
    saved, _, _, _ = prepare(stores, judge=judge, question=question, needle='Prüfdatum\n18.11.2026')
    assert saved['satzantwort']['status'] == 'zitate'
    data = json.loads(judge.anfragen[0][-1]['content'])
    assert data['frage'] == question and data['satz'].startswith('Prüfdatum\n18.11.2026')
    assert source.body in data['belege'] and question not in data['belege']


def test_native_teilmenge_belegt_niemals_globale_abwesenheit(stores, monkeypatch):
    capture(stores, monkeypatch)
    saved, _, _, provider = prepare(stores, judge=Pruefer(), leer=True)
    assert saved['satzantwort']['status'] == 'zitate' and len(provider.satzanfragen) == 1


@pytest.mark.parametrize('model', [None, 'bespoke-minicheck:7b', 'tev1:4b'])
def test_inaktives_oder_nicht_unterstuetztes_tor_erteilt_keinen_native_status(stores, monkeypatch, model):
    capture(stores, monkeypatch)
    judge = Pruefer(model=model) if model else None
    saved, _, _, provider = prepare(stores, judge=judge)
    assert saved['satzantwort']['status'] == 'zitate'
    assert not judge or not judge.anfragen


def test_docx_neben_ungelesenem_logo_behaelt_nur_eigenen_vollstaendigen_proof(stores, monkeypatch):
    source, _ = capture(stores, monkeypatch, logo=True)
    assert any(t.startswith(native.TAG) for t in source.tags)
    saved, _, _, _ = prepare(stores, judge=Pruefer())
    assert saved['satzantwort']['status'] == 'saetze'


@pytest.mark.parametrize('field', ['abruf_vollstaendig', 'zuordnung_vollstaendig'])
def test_unvollstaendige_mime_bindung_erzeugt_keinen_native_proof(stores, monkeypatch, field):
    def incomplete(msg):
        return replace(msg, anhang_bericht={**msg.anhang_bericht, field: False})
    source, _ = capture(stores, monkeypatch, transform=incomplete)
    assert not any(t.startswith(native.TAG) for t in source.tags)
    assert prepare(stores, judge=Pruefer())[0]['satzantwort']['status'] == 'zitate'


def test_ueber_budget_langer_rawbeleg_wird_nativ_nicht_gefenstert(stores, monkeypatch):
    extra = ''.join(p(f'Zusatz {i}: Eine unabhängige allgemeine Information.') for i in range(100))
    source, _ = capture(stores, monkeypatch, form(extra=extra))
    judge = Pruefer()
    saved, _, _, _ = prepare(stores, judge=judge)
    assert len(source.body) > spm.MAX_BELEG_ZEICHEN
    assert saved['satzantwort']['status'] == 'zitate' and not judge.anfragen


def reindex(stores, source):
    store = WorkingMemoryStore(stores[0])
    assert store.commit(stores[0].support_snapshot(source.id),
        [{'start': a, 'end': b, 'kind': 'fact'} for a, b in _blocks(source.body)], model='synthetic', explicit_recheck=True)


def changed_tag(stores, source, change, encode=json.dumps):
    from icarus_memory.source_versions import track_source
    ep, claims = stores
    snapshot = ep.support_snapshot(source.id)
    old_tag = next(t for t in source.tags if t.startswith(native.TAG))
    data = json.loads(old_tag[len(native.TAG):])
    change(data)
    tags = [t for t in source.tags if not t.startswith(native.TAG)] + [native.TAG + encode(data)]
    fresh, _ = ep.record(source.kind, source.title, source.body, source.provenance,
        occurred_at=source.occurred_at, participants=source.participants, contacts=source.contacts,
        tags=tags, source_key=snapshot.source_key)
    track_source(ep, claims, snapshot.source_key, fresh)
    reindex(stores, fresh)
    return fresh


@pytest.mark.parametrize('mutate', [
    lambda d: d.update(v=True), lambda d: d.update(body='0' * 64),
    lambda d: d.update(source=123), lambda d: d.update(parent='e-000000000000'),
    lambda d: d.update(data='bad'), lambda d: d['data'].__setitem__(0, True),
    lambda d: d['data'].__setitem__(2, 123), lambda d: d['data'].__setitem__(2, '0' * 64),
    lambda d: d['data'].__setitem__(0, d['data'][0] + 1),
    lambda d: d.update(rows=[*d['rows'], d['rows'][0]]),
    lambda d: d.update(rows=[[True, d['rows'][0][1]]]),
    lambda d: d.update(rows=[[d['rows'][0][0], d['rows'][0][1] - 1]]),
    lambda d: d.update(rows=[d['rows'][0], [d['rows'][0][0] + 1, d['rows'][0][1]]]),
])
def test_manipulierte_metadaten_auch_nach_frischer_indexierung_ohne_native_status(stores, monkeypatch, mutate):
    source, _ = capture(stores, monkeypatch)
    changed_tag(stores, source, mutate)
    saved, _, _, provider = prepare(stores, judge=Pruefer())
    assert saved['satzantwort']['status'] == 'zitate' and not provider.satzanfragen


@pytest.mark.parametrize('duplicate_key', [False, True])
def test_doppelte_metadaten_und_jsonschluessel_sind_kein_proof(stores, monkeypatch, duplicate_key):
    source, _ = capture(stores, monkeypatch)
    ep = stores[0]
    tag = next(t for t in source.tags if t.startswith(native.TAG))
    if duplicate_key:
        changed_tag(stores, source, lambda d: None, encode=lambda d: '{"v":1,' + json.dumps(d)[1:])
    else:
        ep.add_mail_headers(source.id, [native.TAG + ' ' + tag[len(native.TAG):]])
        reindex(stores, ep.get(source.id))
    assert prepare(stores, judge=Pruefer())[0]['satzantwort']['status'] == 'zitate'


@pytest.mark.parametrize('mutation', ['withdraw', 'source_change', 'question', 'review', 'row', 'inactive'])
def test_gespeicherter_native_bericht_bindet_proof_parent_frage_und_pruefung_erneut(stores, monkeypatch, mutation):
    source, parent = capture(stores, monkeypatch)
    saved = prepare(stores, judge=Pruefer())[0]['satzantwort']
    assert sa.wiederherstellen(saved, *stores) is not None
    altered = copy.deepcopy(saved)
    if mutation == 'withdraw':
        stores[0].ignore(parent)
    elif mutation == 'source_change':
        capture(stores, monkeypatch, form(value='19.11.2026'))
    elif mutation == 'question':
        altered['native_frage'] = 'Bis wann muss ich es zurücksenden?'
    elif mutation == 'review':
        altered['saetze'][0]['native_review'] = '0' * 64
    elif mutation == 'row':
        altered['saetze'][0]['roh'] = altered['saetze'][0]['text'] = '18.11.2026'
    else:
        altered['pruefung']['zustand'] = 'aus'
    assert sa.wiederherstellen(altered, *stores) is None


def test_meta_proof_im_notiz_oder_korrekturtyp_ist_keine_native_autorisierung(stores, monkeypatch):
    from icarus_memory.episodes import EpisodeKind
    from icarus_memory.model import Provenance, SourceType
    source, _ = capture(stores, monkeypatch)
    for kind, provenance in [(EpisodeKind.MESSAGE, Provenance(SourceType.EMAIL)),
                              (EpisodeKind.DOCUMENT, Provenance(SourceType.DOCUMENT)),
                              (EpisodeKind.DOCUMENT, Provenance(SourceType.MANUAL_CORRECTION))]:
        snapshot = stores[0].support_snapshot(source.id)
        fake = replace(snapshot, episode=replace(source, kind=kind, provenance=provenance))
        from icarus_memory.working_memory_store import source_fingerprint
        assert native.read(fake, source_fingerprint(fake), source.body) is None


def test_mehr_als64_zeilen_liefern_text_aber_keinen_native_proof():
    from icarus_memory.document_text import docx_struktur
    data = packed('<w:tbl>' + ''.join('<w:tr><w:tc>' + p(f'Feld{n}') + p(str(n))
                                     + '</w:tc></w:tr>' for n in range(65)) + '</w:tbl>')
    text, rows = docx_struktur(data)
    assert 'Feld64\n64' in text and rows == ()


def test_erneutes_laden_schafft_normale_neue_quellenversion_ohne_alten_body_zu_aendern(stores, monkeypatch):
    def legacy(msg):
        return replace(msg, anhaenge=tuple(replace(a, native_rows=()) for a in msg.anhaenge))
    old, _ = capture(stores, monkeypatch, transform=legacy)
    fresh, _ = capture(stores, monkeypatch)
    assert old.id != fresh.id and old.body == fresh.body
    assert not stores[0].support_snapshot(old.id).current() and stores[0].support_snapshot(fresh.id).current()
    assert stores[0].get(old.id).body == old.body and not any(t.startswith(native.TAG) for t in old.tags)


def test_eigener_abgeschnittener_docx_erhaelt_keinen_proof(stores, monkeypatch):
    message = fetch(monkeypatch, ('Personalformular.docx', form(extra=p('x' * 60000)), DOCX_MIME))
    assert not message.anhaenge[0].vollstaendig
    child, = remember(stores[0], message, claims=stores[1])['anhaenge']
    source = stores[0].get(child)
    assert 'source:truncated' in source.tags and not any(t.startswith(native.TAG) for t in source.tags)


@pytest.mark.parametrize('fragment', [
    '<w:hyperlink><w:r><w:t>Prüfdatum</w:t></w:r></w:hyperlink>',
    '<w:r><w:fldChar w:fldCharType="begin"/><w:t>Prüfdatum</w:t></w:r>',
    '<w:r><w:t>Prüfdatum</w:t></w:r>NICHTUNTERSTÜTZTER TEXT',
])
def test_nicht_unterstuetzte_tabellenkonstrukte_werden_keine_native_einheiten(fragment):
    from icarus_memory.document_text import docx_struktur
    text, rows = docx_struktur(packed('<w:tbl><w:tr><w:tc><w:p>' + fragment + '</w:p>' + p('18.11.2026')
                                    + '</w:tc></w:tr></w:tbl>'))
    assert 'Prüfdatum' in text and rows == ()


def test_nackter_skalar_ohne_label_ist_kein_native_datensatz(stores, monkeypatch):
    capture(stores, monkeypatch, form(label=''))
    assert prepare(stores, judge=Pruefer(), question='Welche Angaben nennt das Personalformular?', needle='18.11.2026')[0]['satzantwort']['status'] == 'zitate'


def test_normaler_pruefvertrag_bleibt_ohne_nutzerfrage():
    from tests.test_satzpruefung_modell import beleg
    judge = Pruefer()
    assert spm.urteilen([('Die Geschäftsführung hat zugestimmt.', [beleg()])], spm.tor('an', judge))[0].wert == 'ja'
    assert set(json.loads(judge.anfragen[0][-1]['content'])) == {'satz', 'belege'}


def test_native_zeitueberschreitung_liefert_keine_antwort(stores, monkeypatch):
    capture(stores, monkeypatch)
    judge = Pruefer(warte=0.05)
    monkeypatch.setattr(spm, 'SATZ_BUDGET_S', 0.01)
    assert prepare(stores, judge=judge)[0]['satzantwort']['status'] == 'zitate'


def test_native_pruefer_erhaelt_raw_leerabsaetze_unveraendert(stores, monkeypatch):
    source, _ = capture(stores, monkeypatch, form(extra=p('') + p('Unabhängige Einleitung.')))
    assert '\n\n\n\n' in source.body
    judge = Pruefer()
    saved, _, _, _ = prepare(stores, judge=judge)
    assert saved['satzantwort']['status'] == 'saetze'
    assert source.body in json.loads(judge.anfragen[0][-1]['content'])['belege']


@pytest.mark.parametrize('scalar', [True, False])
def test_normale_literalprosa_bleibt_mit_und_ohne_geeignete_native_row_im_alten_pfad(stores, monkeypatch, scalar):
    from tests.test_satzantwort import Skript
    normal = 'Der Bericht liegt im Tresor.'
    data = packed(p('Einleitung.') + p(normal) + '<w:tbl><w:tr><w:tc>'
        + p('Prüfdatum' if scalar else 'Kommentar') + p('18.11.2026' if scalar else 'freier Wert')
        + '</w:tc></w:tr></w:tbl>')
    source, _ = capture(stores, monkeypatch, data)
    provider = Skript({'status': 'antwort', 'saetze': [{'text': normal, 'belege': [1]}]})
    saved, belege, rendered, _ = prepare(stores, provider=provider, question='Wo liegt der Bericht?')
    assert saved['satzantwort']['status'] == 'saetze' and normal in rendered
    assert not any(b.native_ungueltig for b in belege)
    assert bool(belege[0].native_rows) is scalar
    assert 'native_frage' not in saved['satzantwort'] and 'native_review' not in saved['satzantwort']['saetze'][0]
    assert stores[0].get(source.id).body == source.body


def test_erneute_verbindung_und_conversation_get_pruefen_proof_und_entzug(stores, monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from icarus_memory.conversations import ConversationStore
    from icarus_memory.server import create_app
    source, parent = capture(stores, monkeypatch)
    answer = prepare(stores, judge=Pruefer())[0]
    episodes, claims = type(stores[0])(stores[0]._path), type(stores[1])(stores[1]._path)
    conversations = ConversationStore(tmp_path / 'conversation-native.sqlite3')
    try:
        assert wma.satz_struktur(answer, episodes, claims)['saetze'][0]['text'] == 'Quelle berichtet: „' + ROW + '“'
        conversation = conversations.create('Native Quelle')
        conversations.add_message(conversation.id, 'user', 'Wann ist der beginn der tätigkeit?')
        conversations.add_message(conversation.id, 'assistant', 'wird neu gelesen', metadata={
            'context': {'answer_mode': 'memory_evidence', 'working_answer': answer}})
        app = create_app(episodes=episodes, knowledge=claims, conversations=conversations)
        client = TestClient(app)
        before = client.get('/api/v1/conversations/' + conversation.id)
        assert before.status_code == 200 and 'Quelle berichtet:' in before.text and '18.11.2026' in before.text
        episodes.ignore(parent)
        after = client.get('/api/v1/conversations/' + conversation.id)
        assert after.status_code == 200
        message = after.json()['messages'][-1]
        assert '18.11.2026' not in message['content']
        assert message['metadata']['context']['answer_contract']['status'] == 'working_unavailable'
        assert 'satzantwort' not in message['metadata']['context']
        assert wma.satz_struktur(answer, episodes, claims) is None
        assert episodes.get(source.id).body == source.body
    finally:
        conversations.close()
        claims.close()
        episodes.close()


@pytest.mark.parametrize('extra,row_extra,value', [
    (p('Entwurf'), '', '18.11.2026'),
    (p('Vorläufige Angaben.'), '', '18.11.2026'),
    (p('Die Angabe ist "unbestätigt".'), '', '18.11.2026'),
    ('', p('Dies gilt nur, wenn die Prüfung abgeschlossen ist.'), '18.11.2026'),
    ('', '', 'Anna Beispiel'),
    ('', '', '1' * 401),
])
def test_native_unterstuetzt_keine_quotes_drafts_normen_freien_werte_oder_ueberlaenge(stores, monkeypatch, extra, row_extra, value):
    capture(stores, monkeypatch, form(extra=extra, row_extra=row_extra, value=value))
    saved, _, _, _ = prepare(stores, judge=Pruefer())
    assert saved['satzantwort']['status'] == 'zitate'


@pytest.mark.parametrize('label', ['Sie müssen antworten', 'Datum des Absenders', 'Anna ist eingestellt'])
def test_native_kann_keine_norm_role_oder_personenaussage_liefern(stores, monkeypatch, label):
    capture(stores, monkeypatch, form(label=label))
    saved, _, _, _ = prepare(stores, judge=Pruefer(), needle=label + '\n18.11.2026',
                             question='Welche Angaben nennt das Personalformular?')
    assert saved['satzantwort']['status'] == 'zitate'


def test_native_laesst_weder_teilstueck_noch_paraphrase_durch(stores, monkeypatch):
    from tests.test_satzantwort import Skript
    capture(stores, monkeypatch)
    provider = Skript({'status': 'antwort', 'saetze': [{'text': 'Die Tätigkeit beginnt am 18.11.2026.', 'belege': [1]}]})
    saved, _, _, _ = prepare(stores, judge=Pruefer(), provider=provider)
    assert saved['satzantwort']['status'] == 'zitate'


@pytest.mark.parametrize('following', [
    'Üben Sie weitere Tätigkeiten aus?',
    'Wenn Sie weitere Tätigkeiten ausüben, gilt diese Angabe nicht.',
])
def test_native_feld_und_fremde_formularfrage_sind_keine_gemeinsame_rollenaussage(stores, monkeypatch, following):
    # Bestehende freie Originalketten reichen über die echten Absatzgrenzen
    # bis zum Frage-/Satzzeichen; nur normative Kontexte bleiben atomar.
    data = packed(p(REGEL) + '<w:tbl><w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026')
        + '</w:tc><w:tc>' + p('Prüfstelle') + '</w:tc></w:tr></w:tbl>'
        + p('Weiteres Formularfeld') + p(following))
    capture(stores, monkeypatch, data)
    judge = Pruefer()
    saved, _, rendered, _ = prepare(stores, judge=judge, needle='Prüfdatum\n18.11.2026',
                                    question='Welches Prüfdatum nennt das Formular?')
    if following.startswith('Wenn'):
        assert saved['satzantwort']['status'] == 'zitate'
    else:
        assert saved['satzantwort']['status'] == 'saetze'
        assert 'Quelle berichtet: „Prüfdatum\n18.11.2026\tPrüfstelle“' in rendered


def test_native_fragepruefung_erhaelt_einzelnen_terminvorbehalt_und_lehnt_unbedingte_row_ab(stores, monkeypatch):
    condition = 'Die folgenden Termine gelten nur nach schriftlicher Freigabe.'
    data = packed(p(condition) + '<w:tbl><w:tr><w:tc>' + p('Prüfdatum') + p('18.11.2026')
        + '</w:tc><w:tc>' + p('Prüfstelle') + '</w:tc></w:tr></w:tbl>')
    source, _ = capture(stores, monkeypatch, data)
    judge = Pruefer(standard=json.dumps({'urteil': 'nein'}))
    saved, _, _, _ = prepare(stores, judge=judge, needle='Prüfdatum\n18.11.2026',
                            question='Welches Prüfdatum gilt für die Erstprüfung?')
    assert saved['satzantwort']['status'] == 'zitate' and len(judge.anfragen) == 1
    request = judge.anfragen[0]
    assert 'Vorbehalt' in request[0]['content'] and 'außerhalb der Row' in request[0]['content']
    assert condition in json.loads(request[-1]['content'])['belege']
    assert json.loads(request[-1]['content'])['belege'].endswith('\n' + source.body)
