"""Ein einfaches Footerzitat sperrt keine unabhängig unzitierte Originalaussage."""
from datetime import datetime, timezone

import pytest

from icarus_memory import satzantwort as sa, satzpruefung as sp
from tests.test_answer_source_boundaries import antwort, stores  # noqa: F401
from tests.test_original_sentence_selection import Selector

NOW = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
RATE = 'Ihre Rate wird automatisch abgebucht. Sie müssen nichts weiter tun.'
ROLE = 'Alex Kern muss die Druckdaten am 18. November 2026 senden.'


def test_unzitiert_belegte_rate_bleibt_trotz_ascii_footerzitat_kurz_beantwortbar(stores):
    body = '\n\n'.join([f'Vertragsinformation {i}: Allgemeine Nachricht zum Kundenkonto.' for i in range(18)]
                       + [RATE] + [f'Kontaktinformation {i}: Musterweg, Musterstadt.' for i in range(35)]
                       + ['Hilfe unter "Kontakt".'])
    saved, belege, rendered, provider = antwort(stores, body, 'Nächste Rate',
        'Muss ich die Rate überweisen?', 'Sie müssen nichts weiter tun.', mail=True)
    assert saved['satzantwort']['status'] == 'saetze'
    assert RATE in rendered and len(rendered) < 500 and body not in rendered
    assert provider.satzanfragen
    assert all('"Kontakt"' not in b.text and '"Kontakt"' in b.pruef_text for b in belege)
    episodes, claims = stores
    episodes.ignore(saved['refs'][0]['episode_id'])
    assert sa.wiederherstellen(saved['satzantwort'], episodes, claims) is None


def test_volltext_zitatspan_sperrt_auch_eine_rate_deren_auszug_keine_zitatzeichen_enthaelt():
    body = '\n\n'.join(['Alte Nachricht: "Dies war ein Vorschlag.']
                       + [f'Historische Nachricht {i}: Der damalige Stand wurde mitgeteilt.' for i in range(12)]
                       + [RATE]
                       + [f'Weitere Nachricht {i}: Der damalige Stand wurde mitgeteilt.' for i in range(12)]
                       + ['Dieser Vorschlag wurde verworfen."'])
    beleg = sa.AntwortBeleg(1, {}, 'Quelle', 'synthetic', 'Rate', '', RATE, None,
                            pruef_text=body, gekuerzt=True)
    provider = Selector({'status': 'antwort', 'originalstellen': [{'beleg': 1, 'satz': 1}]})
    result = sa.formulieren('Muss ich die Rate überweisen?', [beleg], provider, jetzt=NOW)
    assert provider.messages, 'Der Guard muss die wirklich gewählte Originaleinheit prüfen'
    assert result.status == 'zitate' and result.verworfen
    assert '"' not in beleg.text and '"' in beleg.pruef_text


@pytest.mark.parametrize('footer_vorn', [False, True])
def test_echte_satzpruefung_bestaetigt_unzitierte_regel_und_person_beim_selben_quellkontext(footer_vorn):
    text = RATE + '\n\n' + ROLE
    source = 'Hilfe unter "Kontakt".\n\n' + text if footer_vorn else text + '\n\nHilfe unter "Kontakt".'
    beleg = sa.AntwortBeleg(1, {}, 'Quelle', 'synthetic', 'Rate', '', source, None, personen=('Alex Kern',))
    for candidate in (RATE, ROLE):
        assert sa.pruefe_satz(sp.Satz(candidate, ('1',)), {'1': beleg}, NOW).bestanden


@pytest.mark.parametrize('candidate', [RATE, ROLE])
def test_zitierter_mittelsatz_ohne_eigene_zitatzeichen_bleibt_gesperrt(candidate):
    source = 'Alte Nachricht: "Dies war der damalige Vorschlag. ' + candidate + ' Er wurde verworfen."'
    assert '"' not in candidate
    assert not sp.originalbindung(candidate, [source])
    assert not sp.rollenbindung(candidate, [source], sichtbar=[source], personen=('Alex Kern',))
    beleg = sa.AntwortBeleg(1, {}, 'Quelle', 'synthetic', 'Alt', '', source, None, personen=('Alex Kern',))
    provider = Selector({'status': 'antwort', 'saetze': [{'text': candidate, 'belege': [1]}]})
    result = sa.formulieren('Was gilt?', [beleg], provider, jetzt=NOW)
    assert result.status == 'zitate'


@pytest.mark.parametrize('source', [
    'Alte Nachricht: "Beginn.\n\n' + RATE + '\n\nEnde."',
    'Alte Nachricht: "Beginn. ' + ROLE + ' Ende."',
    'Alte Nachricht: "Beginn. ' + RATE + ' Ende.',
    'Verworfene Aussage. ' + RATE + ' Ende."',
    'Vorher "ein Wort".\n\n' + RATE + '\n\nNachher "ein zweites Wort".',
    'Alte Nachricht: "Beginn. \'Innen. ' + RATE + ' Ende.\' Schluss."',
    'Alte Nachricht: "Beginn. "Innen. ' + RATE + ' Ende." Schluss."',
    'Alte Nachricht: „Beginn. ' + RATE + ' Ende.“',
    'Alte Nachricht: «Beginn. ' + RATE + ' Ende.»',
    'Alte Nachricht: `Beginn. ' + RATE + ' Ende.`',
    'Alte Nachricht: \\"Beginn. ' + RATE + ' Ende.\\"',
    'Unklar geschlossen."\n\n' + RATE + '\n\n"Unklar geöffnet.',
])
def test_mehrsatz_offene_verschachtelte_und_nicht_unterstuetzte_klammern_bleiben_konservativ(source):
    # Mehrere Paare und andere Schreibweisen werden bewusst nicht interpretiert.
    for candidate in (RATE, ROLE):
        assert not sp.originalbindung(candidate, [source])
        assert not sp.rollenbindung(candidate, [source], sichtbar=[source], personen=('Alex Kern',))


def test_sichtbarkeit_und_unzitierter_nachweis_muessen_aus_derselben_quelle_stammen():
    visible = 'Alte Nachricht: "Beginn. ' + RATE + ' Ende."'
    hidden = RATE + '\n\nHilfe unter "Kontakt".'
    assert not sp.originalbindung(RATE, [hidden, visible], sichtbar=['Anderer sichtbarer Absatz.', visible])
    assert not sp.rollenbindung(RATE, [hidden, visible], sichtbar=['Anderer sichtbarer Absatz.', visible])


def test_gleicher_wortlaut_im_verdeckten_unzitierten_und_sichtbaren_zitierten_teil_ist_kein_sichtbarkeitsbeleg():
    visible = 'Alte Nachricht: "Beginn. ' + RATE + ' Ende."'
    source = RATE + '\n\nAnderer Absatz.\n\n' + visible
    assert not sp.originalbindung(RATE, [source], sichtbar=[visible])
    assert not sp.rollenbindung(RATE, [source], sichtbar=[visible])
    beleg = sa.AntwortBeleg(1, {}, 'Quelle', 'synthetic', 'Rate', '', visible, None,
                            pruef_text=source, gekuerzt=True)
    provider = Selector({'status': 'antwort', 'saetze': [{'text': RATE, 'belege': [1]}]})
    assert sa.formulieren('Was gilt?', [beleg], provider, jetzt=NOW).status == 'zitate'


def test_weder_qualifier_noch_person_darf_mit_einem_footerzitat_wegfallen():
    source = 'Sie müssen die Unterlagen senden, wenn die Prüfung abgeschlossen ist.\n\nHilfe unter "Kontakt".'
    assert not sp.originalbindung('Sie müssen die Unterlagen senden.', [source])
    assert not sp.rollenbindung('Wir müssen die Unterlagen senden, wenn die Prüfung abgeschlossen ist.',
                               [source], sichtbar=[source])
