"""Lint über alle Akten (M2): Befunde je Art, Fehlalarme, Ablage, Zählung, nur Vorschläge."""
from datetime import timedelta

import pytest

from icarus_memory import lint as lint_modul
from icarus_memory.claims import ClaimStore, KnowledgeService
from icarus_memory.lage import Lagen
from icarus_memory.lint import Befund, Befunde, Beleg, Entwurf, Pruefer, vorschlagen, werte, zusammenfassung
from icarus_memory.model import Provenance, SourceType
from icarus_memory.proposals import Evidence, ProposalKind, ProposalState, ProposalStore
from tests.test_akten import akten, mail  # noqa: F401 - Fixture und Hilfen
from tests.test_bezuege import JETZT, quelle, welt  # noqa: F401 - Fixture und Hilfen
from tests.test_lage import LageModell, satz

KOLBE = 'Bernd Kolbe <b.kolbe@kuechenforum.example>'
NEUMANN = 'Carla Neumann <c.neumann@pflegeverband.example>'
BRUECKNER = 'Timo Brückner <t.brueckner@genussmanufaktur.example>'
WELLER = 'Anja Weller <a.weller@druckerei-weller.example>'
FRIST_ALT = 'Bitte schicken Sie mir die Anmeldeliste bis zum 20. Oktober 2026.'
FRIST_NEU = 'Die Anmeldeliste verschiebt sich auf den 6. November 2026.'


@pytest.fixture
def wissen(tmp_path, welt):
    episodes = welt[0]
    vorschlaege = ProposalStore(tmp_path / 'proposals.sqlite3')
    claims = ClaimStore(tmp_path / 'knowledge.sqlite3')
    yield claims, vorschlaege, KnowledgeService(proposals=vorschlaege, claims=claims, episodes=episodes)
    vorschlaege.close()
    claims.close()


def projekt(welt, name='Schulungsreihe Pflegeküche'):
    return welt[1].add_project(name, Provenance(SourceType.USER_STATED))


def pruefen(akten, *, claims=None, lagen=None, jetzt=JETZT):
    akten.bezuege.aktualisieren()
    if claims is not None:
        akten.claims = claims
    return Pruefer(akten.episodes, akten.bezuege, akten, claims=claims, workspace=akten.bezuege.workspace,
                   lagen=lagen, jetzt=jetzt).pruefen().befunde


def arten(befunde):
    return sorted((b.art, b.unterart if b.art != 'aussage_gegen_quelle' else '') for b in befunde)


# -- Werte ----------------------------------------------------------------------------------------


def test_werte_erkennen_anschrift_plz_mail_betrag_und_datum():
    text = 'Neue Anschrift: Mühlweg 8, 64823 Groß-Umstadt, rechnung@druck.example, 1.250,00 Euro bis 12.11.2026.'
    gefunden = werte(text, JETZT)
    assert set(gefunden['anschrift']) == {'mühlweg 8'} and set(gefunden['plz']) == {'64823'}
    assert set(gefunden['mail']) == {'rechnung@druck.example'} and set(gefunden['betrag']) == {'1250.00'}
    assert set(gefunden['datum']) == {'2026-11-12'}
    # Ohne Bezugstag zählt nur ein Datum mit Jahr.
    assert 'datum' not in werte('bis zum 12.11.', None) and werte('am 12.11.2026', None)['datum']


def test_widerspruch_nur_bei_gleicher_sorte_ohne_gemeinsamen_wert():
    alt, neu = werte('Klinikstraße 5, 65307 Bad Schwalbach'), werte('Lindenallee 22, 34117 Kassel')
    assert lint_modul.widerspruechliche_sorten(alt, neu) == ['anschrift', 'plz']
    assert lint_modul.widerspruechliche_sorten(alt, werte('Klinikstraße 5, 65307 Bad Schwalbach, 2. Stock')) == []
    assert lint_modul.widerspruechliche_sorten(alt, werte('Wir sind telefonisch erreichbar.')) == []


# -- Art 1: Widersprüche zwischen Akten --------------------------------------------------------------


def fristen_welt(welt, *, neu_von=NEUMANN, neu_text=FRIST_NEU):
    p = projekt(welt)
    alt = mail(welt[0], 'Anmeldeliste', [(FRIST_ALT, 'request')], tage=100, absender=KOLBE, projekt=p.id)
    neu = mail(welt[0], 'Späterer Start', [(neu_text, 'change')], tage=40, absender=neu_von, projekt=p.id)
    return p, alt, neu


def test_person_nennt_noch_die_alte_frist_die_projektakte_kennt_die_neue(welt, akten):
    p, alt, neu = fristen_welt(welt)
    befunde = pruefen(akten)
    assert arten(befunde) == [('widerspruch', 'frist')]
    befund = befunde[0]
    assert set(befund.sachen) == {'person:a:b.kolbe@kuechenforum.example', 'organisation:kuechenforum',
                                  f'projekt:{p.id}'}
    assert [(b.episode_id, b.rolle) for b in befund.belege] == [(alt.id, 'alt'), (neu.id, 'neu')]
    assert dict(befund.werte)['alt'] == '20.10.2026' and dict(befund.werte)['neu'] == '06.11.2026'
    assert 'Bernd Kolbe' in befund.text and '20.10.2026' in befund.text and '06.11.2026' in befund.text
    assert 'Schulungsreihe Pflegeküche' in befund.text and befund.schwere == 'wichtig'
    entwuerfe = {e.wahl: e for e in befund.entwuerfe}
    assert (entwuerfe['neu'].value, entwuerfe['alt'].value) == ('06.11.2026', '20.10.2026')
    assert entwuerfe['neu'].subject_ref == f'project:{p.id}' and entwuerfe['neu'].episode_id == neu.id
    assert entwuerfe['neu'].predicate == entwuerfe['alt'].predicate == 'Frist Anmeldeliste'
    assert entwuerfe['neu'].zitat in neu.body and entwuerfe['alt'].zitat in alt.body


def test_kein_widerspruch_wenn_jede_akte_den_neuen_stand_kennt(welt, akten):
    # Dieselbe Person verschiebt selbst: Ihre Akte kennt die neue Frist, nichts widerspricht sich.
    fristen_welt(welt, neu_von=KOLBE)
    assert pruefen(akten) == []


def test_verschiedene_gegenstaende_sind_kein_widerspruch(welt, akten):
    fristen_welt(welt, neu_text='Die Raumabnahme verschiebt sich auf den 6. November 2026.')
    assert pruefen(akten) == []


def test_stand_mit_anderer_anschrift_ist_ein_widerspruch_gleiche_anschrift_nicht(welt, akten):
    p = projekt(welt)
    alt = mail(welt[0], 'Anschrift', [('Unsere Rechnungsanschrift: Klinikstraße 5, 65307 Bad Schwalbach.', 'status')],
               tage=90, absender=KOLBE, projekt=p.id)
    neu = mail(welt[0], 'Umzug', [('Die Rechnungsanschrift ist jetzt Lindenallee 22, 34117 Kassel.', 'change')],
               tage=20, absender=NEUMANN, projekt=p.id)
    befunde = pruefen(akten)
    assert arten(befunde) == [('widerspruch', 'stand')]
    assert dict(befunde[0].werte)['alt'] == 'Klinikstraße 5' and dict(befunde[0].werte)['neu'] == 'Lindenallee 22'
    assert [b.episode_id for b in befunde[0].belege] == [alt.id, neu.id]
    mail(welt[0], 'Bestätigt', [('Die Rechnungsanschrift bleibt Klinikstraße 5, 65307 Bad Schwalbach.', 'status')],
         tage=5, absender=NEUMANN, projekt=p.id)
    assert pruefen(akten) == []


# -- Art 2: angenommene Aussage gegen jüngere Quelle ----------------------------------------------------


def aussage_annehmen(welt, service, *, tage=150):
    notiz = quelle(welt[0], 'Telefonat Druckerei', 'Die Rechnungsanschrift der Druckerei ist Gutenbergring 3, 64807 Dieburg.',
                   tage=tage)
    vorschlag, _ = service.propose(subject_ref='organisation:druckereiweller', predicate='Rechnungsanschrift',
                                   value='Gutenbergring 3, 64807 Dieburg',
                                   statement='Die Rechnungsanschrift der Druckerei Weller ist Gutenbergring 3, 64807 Dieburg.',
                                   rationale='Telefonat', evidence=[Evidence(notiz.id, notiz.body, notiz.digest)])
    return service.accept(vorschlag.id, supersedes=[])


def test_angenommene_aussage_gegen_juengere_mail_wird_ein_vorschlag_nie_ein_fakt(welt, akten, wissen, tmp_path):
    claims, vorschlaege, service = wissen
    aussage = aussage_annehmen(welt, service)
    neu = mail(welt[0], 'Umzug', [('Unsere Rechnungsanschrift hat sich geändert: Mühlweg 8, 64823 Groß-Umstadt.', 'change')],
               tage=10, absender=WELLER)
    befunde = pruefen(akten, claims=claims)
    assert arten(befunde) == [('aussage_gegen_quelle', '')]
    befund = befunde[0]
    assert befund.unterart == aussage.id and befund.sachen == ('organisation:druckereiweller',)
    assert [b.rolle for b in befund.belege] == ['aussage', 'neu'] and befund.belege[1].episode_id == neu.id
    assert 'Gutenbergring 3' in befund.text and 'Mühlweg 8' in befund.text
    entwurf = befund.entwuerfe[0]
    assert (entwurf.wahl, entwurf.value, entwurf.ersetzt) == ('neu', 'Mühlweg 8', (aussage.id,))
    assert entwurf.statement == 'Die Rechnungsanschrift der Druckerei Weller ist Mühlweg 8.'
    # Ablage und Vorschläge: Der Lauf legt einen offenen Vorschlag an, der Wissensbestand bleibt, wie er war.
    ablage = Befunde(tmp_path / 'lint.sqlite3')
    vorher = [(c.id, c.status.value) for c in claims.all_claims()]
    ablage.abgleichen(befunde)
    assert vorschlagen(ablage, service, welt[0]) == 1
    assert [(c.id, c.status.value) for c in claims.all_claims()] == vorher
    offen = vorschlaege.pending(ProposalKind.KNOWLEDGE)
    assert [(p.value, p.proposed_by, p.evidence[0].episode_id) for p in offen] == [('Mühlweg 8', 'lint', neu.id)]
    # Ein zweiter Lauf legt nichts doppelt an.
    assert vorschlagen(ablage, service, welt[0]) == 0
    ablage.close()


def test_aussage_ohne_widerspruch_bleibt_ohne_befund(welt, akten, wissen):
    claims, _, service = wissen
    aussage_annehmen(welt, service)
    # Jünger, gleicher Wert: kein Widerspruch. Älter mit anderem Wert: überholt schon, kein Widerspruch.
    mail(welt[0], 'Bestätigung', [('Die Rechnungsanschrift bleibt Gutenbergring 3, 64807 Dieburg.', 'status')],
         tage=10, absender=WELLER)
    mail(welt[0], 'Alt', [('Unsere Rechnungsanschrift hat sich geändert: Bahnhofstraße 1, 64807 Dieburg.', 'change')],
         tage=300, absender=WELLER)
    assert pruefen(akten, claims=claims) == []


def test_aeltere_quelle_mit_anderem_wert_widerspricht_der_aussage_nicht(welt, akten, wissen):
    # Die Mail ist älter als die Grundlage der Aussage: Lea hat danach etwas anderes angenommen. Kein Befund.
    claims, _, service = wissen
    aussage_annehmen(welt, service)
    mail(welt[0], 'Alt', [('Unsere Rechnungsanschrift hat sich geändert: Bahnhofstraße 1, 64807 Dieburg.', 'change')],
         tage=300, absender=WELLER)
    assert pruefen(akten, claims=claims) == []


# -- Art 3: veraltete Sätze der Lage ------------------------------------------------------------------------


def test_lage_mit_saetzen_auf_aelteren_belegen_als_eine_neue_aenderung_ist_ein_hinweis(welt, akten):
    lagen = Lagen(welt[0], akten, mindestabstand_s=0)
    mail(welt[0], 'Ausschreibung', [('Die Einreichfrist ist der 15. Oktober 2026.', 'fact')], tage=30)
    mail(welt[0], 'Verlängerung', [('Die neue Einreichfrist ist der 12. November 2026.', 'change')], tage=10)
    akten.bezuege.aktualisieren()
    sache = 'person:a:foerderung@stiftung.example'
    lagen.erzeugen(sache, LageModell({'saetze': [satz('Die Einreichfrist ist der 12.11.2026.', 1)]}), jetzt=JETZT)
    assert pruefen(akten, lagen=lagen) == []
    neu = mail(welt[0], 'Zweite Verlängerung', [('Die Einreichfrist wurde auf den 30. November 2026 verschoben.', 'change')],
               tage=1)
    befunde = pruefen(akten, lagen=lagen)
    assert [(b.art, b.sachen, b.schwere) for b in befunde] == [('veralteter_satz', (sache,), 'hinweis')]
    assert neu.id in [b.episode_id for b in befunde[0].belege if b.rolle == 'neu']
    lagen.erzeugen(sache, LageModell({'saetze': [satz('Die Einreichfrist ist der 30.11.2026.', 1)]}), jetzt=JETZT)
    assert pruefen(akten, lagen=lagen) == []


# -- Art 4: Waisen ----------------------------------------------------------------------------------------


def albers_welt(welt, gespraeche=3):
    quelle(welt[0], 'Raumplan', 'Anbei der Raumplan.', ['Jonas Albers <j.albers@kuechenforum.example>'], tage=200)
    quelle(welt[0], 'Ablesung', 'Wir lesen den Zähler ab.', ['Jonas Albers <jonas.albers@stadtwerke.example>'], tage=190)
    return [quelle(welt[0], f'Abstimmung {n}', f'Abstimmung {n} zur Lehrküche.', ['Jonas Albers'], tage=100 - n)
            for n in range(gespraeche)]


def test_name_zweier_personen_in_drei_quellen_ist_eine_waise(welt, akten):
    gespraeche = albers_welt(welt)
    befunde = pruefen(akten)
    assert [(b.art, b.unterart) for b in befunde] == [('waise', 'ohne_akte')]
    assert {b.episode_id for b in befunde[0].belege} == {e.id for e in gespraeche}
    assert '„Jonas Albers“ steht in 3 Quellen' in befunde[0].text
    # Sagt der Nutzer bei einer Quelle, wer gemeint ist, bleiben zwei: kein Befund mehr.
    akten.bezuege.nutzer_setzen(gespraeche[0].id, 'person:a:j.albers@kuechenforum.example', 'zu')
    assert pruefen(akten) == []


def test_zwei_quellen_mit_offenem_namen_sind_noch_keine_waise(welt, akten):
    albers_welt(welt, gespraeche=2)
    assert pruefen(akten) == []


def test_akte_ohne_quelle_seit_einem_jahr_ist_ein_hinweis_nur_mit_mehreren_quellen(welt, akten):
    for n in range(3):
        mail(welt[0], f'Demo {n}', [(f'Angabe {n} zur Software.', 'fact')], tage=500 + n,
             absender='Holger Weidner <h.weidner@diaetplan.example>')
    befunde = pruefen(akten)
    assert [(b.art, b.unterart, b.schwere) for b in befunde] == [('waise', 'ruhend', 'hinweis')]
    assert set(befunde[0].sachen) == {'person:a:h.weidner@diaetplan.example', 'organisation:diaetplan'}
    assert 'nichts Neues (3 Quellen)' in befunde[0].text and len(befunde[0].belege) == 3
    assert not befunde[0].entwuerfe  # nur zur Kenntnis, nie ein Vorschlag zum Löschen
    mail(welt[0], 'Neu', [('Wieder da.', 'fact')], tage=10, absender='Holger Weidner <h.weidner@diaetplan.example>')
    assert pruefen(akten) == []


def test_zwei_alte_quellen_sind_keine_ruhende_akte(welt, akten):
    for n in range(2):
        mail(welt[0], f'Demo {n}', [(f'Angabe {n}.', 'fact')], tage=500 + n,
             absender='Holger Weidner <h.weidner@diaetplan.example>')
    assert pruefen(akten) == []


def test_zuordnung_zu_einem_projekt_das_es_nicht_mehr_gibt_ist_ein_verwaister_bezug(welt, akten):
    e = mail(welt[0], 'Notiz', [('Kurz notiert.', 'fact')], tage=5)
    akten.bezuege.aktualisieren()
    akten.bezuege.nutzer_setzen(e.id, 'projekt:p-geloescht', 'zu')
    befunde = pruefen(akten)
    assert [(b.art, b.unterart, b.sachen) for b in befunde] == [('waise', 'verwaister_bezug', ('projekt:p-geloescht',))]
    p = projekt(welt, 'Vorhanden')
    akten.bezuege.nutzer_entfernen(e.id, 'projekt:p-geloescht')
    akten.bezuege.nutzer_setzen(e.id, f'projekt:{p.id}', 'zu')
    assert pruefen(akten) == []


# -- Art 5: fehlende Querverweise ---------------------------------------------------------------------------


def brueckner_welt(welt, *, zugeordnet=False):
    p = projekt(welt)
    mail(welt[0], 'Raum', [('Der Raum für die Schulungsreihe Pflegeküche ist reserviert.', 'fact')], tage=120,
         absender=KOLBE, projekt=p.id)
    for n in range(3):
        mail(welt[0], f'Verpflegung {n}', [(f'Für die Schulungsreihe Pflegeküche liefern wir Menü {n}.', 'fact')],
             tage=60 - n, absender=BRUECKNER)
    if zugeordnet:
        # Eine weitere Mail von ihm gehört zum Projekt: Seine Akte und die des Projekts kennen sich.
        mail(welt[0], 'Rechnung Probeessen', [('Anbei die Rechnung für das Probeessen.', 'fact')], tage=20,
             absender=BRUECKNER, projekt=p.id)
    return p


def test_person_schreibt_oft_ueber_ein_projekt_ohne_bezug(welt, akten):
    p = brueckner_welt(welt)
    befunde = pruefen(akten)
    assert [(b.art, b.sachen) for b in befunde] == [
        ('querverweis', ('person:a:t.brueckner@genussmanufaktur.example', f'projekt:{p.id}'))]
    assert len(befunde[0].belege) == 3 and 'Timo Brückner' in befunde[0].text


def test_kennen_sich_die_akten_gibt_es_keinen_querverweis(welt, akten):
    brueckner_welt(welt, zugeordnet=True)
    assert pruefen(akten) == []


# -- Befund, Ablage, Zählung ---------------------------------------------------------------------------------


def befund(art='waise', text='Etwas.', beleg='e-1', unterart='ruhend', **kw):
    return Befund(art, ('person:a:x@y.example',), (Beleg(beleg),), text, 'hinweis', unterart, **kw)


def test_befund_prueft_art_und_nur_widersprueche_tragen_entwuerfe():
    with pytest.raises(ValueError):
        Befund('unfug', (), (), 'x', 'hinweis')
    entwurf = Entwurf('neu', 's', 'p', 'v', 'a', 'r', 'e', 'z')
    with pytest.raises(ValueError):
        befund(entwuerfe=(entwurf,))
    # Der Schlüssel hängt an Art, Sachen und Belegen, nicht am Text: derselbe Befund bleibt derselbe.
    assert befund(text='A').schluessel == befund(text='B').schluessel != befund(beleg='e-2').schluessel


def test_ablage_behaelt_entscheidungen_und_laesst_entfallenes_gehen(tmp_path):
    ablage = Befunde(tmp_path / 'lint.sqlite3')
    a, b, c = befund(beleg='e-1'), befund(beleg='e-2'), befund(beleg='e-3', art='querverweis', unterart='')
    assert ablage.abgleichen([a, b, c], am=100.0)['neu'] == 3
    ablage.status_setzen(a.schluessel, 'abgewiesen')
    ablage.status_setzen(b.schluessel, 'erledigt')
    ergebnis = ablage.abgleichen([a, b], am=200.0)
    assert ergebnis == {'neu': 0, 'entfallen': 1, 'gesamt': 2}
    assert ablage.get(a.schluessel)['status'] == 'abgewiesen' and ablage.get(b.schluessel)['status'] == 'erledigt'
    assert ablage.get(c.schluessel) is None and ablage.liste(status='offen') == []
    zaehlung = zusammenfassung(ablage)
    assert zaehlung['offen'] == 0 and set(zaehlung['je_art']) == set(lint_modul.ARTEN)
    ablage.abgleichen([a, b, befund(beleg='e-4')], am=300.0)
    zaehlung = zusammenfassung(ablage)
    assert (zaehlung['offen'], zaehlung['je_art']['waise'], zaehlung['neu_seit_letztem_lauf'], zaehlung['wichtig']) == (1, 1, 1, 0)
    assert zaehlung['letzter_lauf'].startswith('1970-01-01')
    ablage.close()


def test_zusammenfassung_ohne_ablage_ist_null_und_wirft_nie(tmp_path):
    leer = {'offen': 0, 'wichtig': 0, 'je_art': {art: 0 for art in lint_modul.ARTEN}, 'neu_seit_letztem_lauf': 0,
            'letzter_lauf': None}
    assert zusammenfassung(None) == leer and zusammenfassung(object()) == leer

    class Kaputt(Befunde):
        def zaehlen(self):
            raise RuntimeError('kaputt')

    ablage = Kaputt(tmp_path / 'lint.sqlite3')
    assert zusammenfassung(ablage) == leer
    ablage.close()


def test_der_lauf_liest_nur_und_schreibt_keine_quelle_und_keine_aussage(welt, akten, wissen):
    claims, vorschlaege, service = wissen
    aussage_annehmen(welt, service)
    mail(welt[0], 'Umzug', [('Unsere Rechnungsanschrift hat sich geändert: Mühlweg 8, 64823 Groß-Umstadt.', 'change')],
         tage=10, absender=WELLER)
    fristen_welt(welt)
    akten.bezuege.aktualisieren()
    quellen_vorher = [(e.id, e.digest, e.state) for e in welt[0].all_episodes()]
    vorher = (claims.revision, vorschlaege.counts())
    befunde = pruefen(akten, claims=claims)
    assert {b.art for b in befunde} == {'widerspruch', 'aussage_gegen_quelle'}
    assert (claims.revision, vorschlaege.counts()) == vorher
    assert [(e.id, e.digest, e.state) for e in welt[0].all_episodes()] == quellen_vorher


def test_zeitraum_ruhend_haengt_am_stichtag(welt, akten):
    for n in range(3):
        mail(welt[0], f'Demo {n}', [(f'Angabe {n}.', 'fact')], tage=300 + n,
             absender='Holger Weidner <h.weidner@diaetplan.example>')
    assert pruefen(akten) == []
    assert [b.unterart for b in pruefen(akten, jetzt=JETZT + timedelta(days=100))] == ['ruhend']


def test_eine_ruhende_organisation_allein_ist_kein_befund(welt, akten):
    # Drei Rundschreiben von drei Absendern einer Domäne: Die Organisation ruht, aber keine Person hat drei Quellen.
    for n in range(3):
        mail(welt[0], f'Rundschreiben {n}', [(f'Neuigkeiten Nummer {n}.', 'fact')], tage=500 + n,
             absender=f'Team {n} <team{n}@apotheke-info.example>')
    assert pruefen(akten) == []
