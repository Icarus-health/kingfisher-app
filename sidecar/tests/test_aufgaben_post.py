"""Aufgaben folgen der Post: Zuordnung, Bestätigung und Rückgängig mit echten Stores.

Eigene Mails und Anhänge schlagen eine Erledigung nur vor; Bestätigung nennt
keinen erfundenen Versand. Automatisches Zurückholen setzt bekannte exakte
Adresse und Bezug voraus. Die bisherigen Automatiktests bestätigen jetzt
explizit: Wortüberschneidung allein beweist keine erfüllte Aufgabe.
Nur synthetische Daten (Lena Probe, Anna Berg, Jonas Keller).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from icarus_memory import EpisodeKind, Provenance, SourceType, logbuch, tagesbriefing
from icarus_memory import aufgaben_post
from icarus_memory.aufgaben_post import Lauf, tragende_woerter
from icarus_memory.episodes import EpisodeStore
from icarus_memory.kontakte import fuer_mail
from icarus_memory.logbuch import Logbuch, zusammenfassen
from icarus_memory.proposals import ProposalError, ProposalKind, ProposalState, ProposalStore
from icarus_memory.tasks import TaskStatus, TaskStore

ICH = 'lena.probe@example.org'
LENA = f'Lena Probe <{ICH}>'
ANNA = 'Anna Berg <anna.berg@example.org>'
JONAS = 'Jonas Keller <jonas.keller@example.org>'
JETZT = datetime(2026, 10, 21, 9, 0, tzinfo=timezone.utc)
BITTE = 'Könnten Sie mir die Druckdaten für den Flyer bis Freitag schicken?'


@pytest.fixture
def welt(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    buch = Logbuch(tmp_path / 'logbuch.sqlite3', uhr=lambda: JETZT.timestamp())
    logbuch.verbinde(buch)
    lauf = Lauf(tasks, episodes, proposals, eigene=lambda: [ICH], jetzt=lambda: JETZT)
    lauf.schritt()  # der Bestand von vor dem Umbau wird nicht neu gedeutet; ab hier zählt neue Post
    yield episodes, tasks, proposals, lauf, buch
    logbuch.verbinde(None)
    for store in (episodes, tasks, proposals, buch):
        store.close()


def mail(episodes, titel, text, *, von, an=(), cc=(), tage=0, stunden=0, kennung=None, antwort_auf=(), source_key=""):
    """Eine Mail, wie die Aufnahme sie ablegt: Beteiligte mit Rolle, genaue Kopfzeilenbezüge."""
    empfaenger = [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'an'} for a in an]
    empfaenger += [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'cc'} for a in cc]
    kontakte = fuer_mail(von, empfaenger, eigene=[ICH])
    tags = ([f'mail:message:{kennung}'] if kennung else []) + [f'mail:reply:{k}' for k in antwort_auf]
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text, Provenance(SourceType.EMAIL, source_ref=f'test:{titel}:{tage}:{stunden}'),
                                 participants=[von, *an, *cc], contacts=kontakte, tags=tags,
                                 occurred_at=JETZT - timedelta(days=tage, hours=stunden), source_key=source_key)
    if source_key:
        episodes.advance_source_head(source_key, None, episode.id)
    return episode


def anhang(episodes, mail_episode, dateiname):
    episode, _ = episodes.record(EpisodeKind.DOCUMENT, f'{dateiname} (Anhang zu „{mail_episode.title}“)', f'Anhang „{dateiname}“.',
                                 Provenance(SourceType.EMAIL, source_ref=f'test:{mail_episode.id}#anhang:{dateiname}'),
                                 occurred_at=mail_episode.occurred_at, tags=['anhang', f'mail-parent:{mail_episode.id}'])
    return episode


def aufgabe(tasks, titel, *, quelle=None, wartet_auf=None, faellig_vor_tagen=None, tage=5):
    herkunft = Provenance(SourceType.USER_STATED, source_ref=f'episode:{quelle.id}' if quelle else None, captured_at=JETZT)
    task = tasks.add(titel, herkunft, at=JETZT - timedelta(days=tage),
                     due=JETZT - timedelta(days=faellig_vor_tagen) if faellig_vor_tagen is not None else None)
    if wartet_auf:
        task = tasks.warten_auf(task.id, wartet_auf, at=JETZT - timedelta(days=tage))
    return task


def bitte_von_anna(episodes, tage=3, kennung='a1'):
    return mail(episodes, 'Druckdaten für den Flyer', BITTE, von=ANNA, an=[LENA], tage=tage, kennung=kennung)


def vorschlaege(proposals, kind=None):
    return [p for p in proposals.pending(limit=-1) if kind is None or p.kind is kind]


# -- Tragende Wörter ----------------------------------------------------------


def test_tragende_woerter_lassen_fuellwoerter_namen_und_handlungswoerter_weg():
    assert tragende_woerter('Druckdaten an Anna schicken', namen=['Anna Berg']) == ['Druckdaten']
    assert tragende_woerter('Rechnung 4711 prüfen und bezahlen') == ['Rechnung', '4711']
    assert tragende_woerter('Anrufen') == []
    # Umschrift: „Vertraege“ im Titel findet „Verträge“ in der Mail.
    assert aufgaben_post.woerter_in(['Vertraege'], ['Anbei die Verträge.']) == ['Vertraege']
    assert aufgaben_post.woerter_in(['Rechnung'], ['Die Rechnungen kommen morgen.']) == ['Rechnung']
    assert aufgaben_post.woerter_in(['Druckdaten'], ['Danke für die Nachricht.']) == []


# -- Erledigt durch eigene Mail ----------------------------------------------


def test_eigene_antwort_im_verlauf_wird_nach_bestaetigung_erledigt_mit_grund_und_logbuch(welt):
    episodes, tasks, proposals, lauf, buch = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    antwort = mail(episodes, 'AW: Druckdaten für den Flyer', 'Hallo Anna, anbei die Druckdaten. Viele Grüße, Lena',
                   von=LENA, an=[ANNA], tage=0, kennung='l1', antwort_auf=['a1'])
    bericht = lauf.schritt()
    assert bericht == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 1}  # Bitte und Antwort
    assert tasks.get(task.id).status is TaskStatus.OPEN
    [vorschlag] = vorschlaege(proposals)
    lauf.vorschlag_annehmen(vorschlag.id)
    fertig = tasks.get(task.id)
    assert fertig.status is TaskStatus.DONE and fertig.done_at == antwort.occurred_at
    grund = fertig.erledigt_grund
    assert grund['satz'] == 'Erledigt nach deiner Bestätigung zur Mail an Anna Berg vom 21. Oktober.'
    assert grund['episode_id'] == antwort.id and grund['verlauf'] is True and grund['woerter'] == ['Druckdaten']
    assert fertig.geaendert_grund is None and fertig.to_dict()['erledigt_grund']['satz'] == grund['satz']
    assert [e['kind'] for e in tasks.history(task.id)][0] == 'post_completed'
    assert vorschlaege(proposals) == []
    ereignisse = [e for e in buch.ereignisse(JETZT - timedelta(days=1)) if e.art == 'aufgabe_post']
    assert len(ereignisse) == 1 and ereignisse[0].daten == {'sorte': 'erledigt', 'aufgabe': task.id, 'mail': antwort.id, 'wie': 'vorschlag'}
    # Ohne Rohtext im Logbuch: weder Betreff noch Titel.
    assert 'Druckdaten' not in str(ereignisse[0].daten)


def test_eigene_mail_an_die_person_mit_wort_braucht_bestaetigung_ohne_verlauf(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    mail(episodes, 'Flyer', 'Hallo Anna, die Druckdaten sind fertig, siehe Anhang.', von=LENA, an=[ANNA], kennung='l2')
    assert lauf.schritt()['vorschlaege'] == 1
    assert tasks.get(task.id).status is TaskStatus.OPEN
    [vorschlag] = vorschlaege(proposals)
    lauf.vorschlag_annehmen(vorschlag.id)
    fertig = tasks.get(task.id)
    assert fertig.status is TaskStatus.DONE and fertig.erledigt_grund['verlauf'] is False
    assert fertig.erledigt_grund['wer'] == 'Anna Berg'


def test_anhang_mit_dem_wort_im_namen_belegt_nur_den_bezug(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    eigene = mail(episodes, 'AW: Druckdaten für den Flyer', 'Hallo Anna, anbei wie besprochen. Viele Grüße', von=LENA, an=[ANNA],
                  kennung='l3', antwort_auf=['a1'])
    anhang(episodes, eigene, 'Druckdaten_Flyer_final.pdf')
    assert lauf.schritt()['vorschlaege'] == 1
    assert tasks.get(task.id).status is TaskStatus.OPEN
    [vorschlag] = vorschlaege(proposals)
    lauf.vorschlag_annehmen(vorschlag.id)
    assert tasks.get(task.id).status is TaskStatus.DONE


def test_eigene_mail_an_jemand_anderen_oder_ohne_quelle_aendert_nichts(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    ohne = aufgabe(tasks, 'Druckdaten prüfen')
    mail(episodes, 'Druckdaten', 'Hallo Jonas, hier die Druckdaten.', von=LENA, an=[JONAS], kennung='l4')
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
    assert tasks.get(task.id).status is TaskStatus.OPEN and tasks.get(ohne.id).status is TaskStatus.OPEN


def test_eigene_mail_vor_der_bitte_zaehlt_nicht(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes, tage=3)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    mail(episodes, 'Druckdaten', 'Hallo Anna, hier die Druckdaten.', von=LENA, an=[ANNA], tage=4, kennung='l5')
    assert lauf.schritt()['erledigt'] == 0 and tasks.get(task.id).status is TaskStatus.OPEN


# -- Nur Vorschlag ------------------------------------------------------------


def test_ohne_tragendes_wort_nur_vorschlag_und_annehmen_erledigt(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    antwort = mail(episodes, 'AW: Flyer', 'Hallo Anna, danke für die Nachricht, ich melde mich.', von=LENA, an=[ANNA],
                   kennung='l6', antwort_auf=['a1'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 1}
    assert tasks.get(task.id).status is TaskStatus.OPEN
    [vorschlag] = vorschlaege(proposals, ProposalKind.TASK_DONE)
    assert vorschlag.statement == 'Erledigt? „Druckdaten an Anna schicken“'
    assert vorschlag.target_ref == f'task:{task.id}' and vorschlag.evidence[0].episode_id == antwort.id
    assert vorschlag.proposed_by == aufgaben_post.PROPOSED_BY
    liste = lauf.vorschlaege()
    assert [v['id'] for v in liste] == [vorschlag.id] and liste[0]['aufgabe']['id'] == task.id
    assert liste[0]['art'] == 'erledigt' and liste[0]['mail']['episode_id'] == antwort.id
    assert liste[0]['satz'] == 'Du hast am 21. Oktober an Anna Berg geschrieben („AW: Flyer“). Ist die Aufgabe damit erledigt?'
    fertig = lauf.vorschlag_annehmen(vorschlag.id)
    assert fertig.status is TaskStatus.DONE
    assert fertig.erledigt_grund['satz'] == 'Erledigt nach deiner Bestätigung zur Mail an Anna Berg vom 21. Oktober.'
    assert proposals.get(vorschlag.id).state is ProposalState.ACCEPTED
    with pytest.raises(ProposalError):
        lauf.vorschlag_annehmen(vorschlag.id)


def test_rundmail_nur_vorschlag(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    viele = [ANNA, JONAS] + [f'Person {i} <p{i}@example.org>' for i in range(4)]
    mail(episodes, 'Druckdaten für alle', 'Liebe alle, anbei die Druckdaten.', von=LENA, an=viele, kennung='l7')
    assert lauf.schritt()['vorschlaege'] == 1 and tasks.get(task.id).status is TaskStatus.OPEN


def test_lange_ueberfaellige_aufgabe_nie_automatisch(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes, tage=120)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte, faellig_vor_tagen=100, tage=110)
    mail(episodes, 'Druckdaten', 'Hallo Anna, endlich die Druckdaten.', von=LENA, an=[ANNA], kennung='l8', antwort_auf=['a1'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 1}
    assert tasks.get(task.id).status is TaskStatus.OPEN


def test_zwei_aufgaben_auch_mit_verlauf_nur_vorschlag(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    a = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    b = aufgabe(tasks, 'Druckdaten freigeben', quelle=bitte)
    mail(episodes, 'AW: Druckdaten für den Flyer', 'Hallo Anna, anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l9', antwort_auf=['a1'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 2}
    assert tasks.get(a.id).status is TaskStatus.OPEN and tasks.get(b.id).status is TaskStatus.OPEN
    # Auch der stärkere Verlaufbezug belegt keine Erfüllung: beide bleiben Vorschläge.
    zweite = mail(episodes, 'Flyer Rückseite', 'Könnten Sie die Rückseite noch einmal prüfen?', von=ANNA, an=[LENA], tage=2, kennung='a2')
    c = aufgabe(tasks, 'Rückseite prüfen', quelle=zweite)
    for p in vorschlaege(proposals):
        proposals.supersede(p.id)
    tasks.drop(b.id)
    mail(episodes, 'AW: Flyer Rückseite', 'Hallo Anna, die Rückseite ist geprüft, die Druckdaten auch.', von=LENA, an=[ANNA],
         kennung='l10', antwort_auf=['a2'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 2}
    assert tasks.get(c.id).status is TaskStatus.OPEN and tasks.get(a.id).status is TaskStatus.OPEN


# -- Warten aufgelöst durch fremde Mail -----------------------------------------


def test_wartet_auf_anna_und_antwort_von_anna_im_verlauf_geht_zurueck_zu_dir(welt):
    episodes, tasks, proposals, lauf, buch = welt
    eigene = mail(episodes, 'Freigabe Flyer', 'Hallo Anna, bitte gib den Flyer frei.', von=LENA, an=[ANNA], tage=4, kennung='l11')
    task = aufgabe(tasks, 'Freigabe Flyer von Anna', quelle=eigene, wartet_auf='Anna')
    antwort = mail(episodes, 'AW: Freigabe Flyer', 'Hallo Lena, passt so, danke.', von=ANNA, an=[LENA], kennung='a3', antwort_auf=['l11'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 1, 'vorschlaege': 0}
    zurueck = tasks.get(task.id)
    assert zurueck.status is TaskStatus.OPEN and zurueck.wartet_auf is None and zurueck.wartet_seit is None
    assert zurueck.geaendert_grund['satz'] == 'Wieder bei dir, weil Anna Berg am 21. Oktober geantwortet hat.'
    assert zurueck.geaendert_grund['episode_id'] == antwort.id and zurueck.erledigt_grund is None
    assert [e['kind'] for e in tasks.history(task.id)][0] == 'post_returned'
    ereignisse = [e for e in buch.ereignisse(JETZT - timedelta(days=1)) if e.art == 'aufgabe_post']
    assert ereignisse[0].daten['sorte'] == 'zurueck'


def test_wartet_auf_ohne_verlauf_und_wort_nur_vorschlag_verwerfen_trennt(welt):
    episodes, tasks, proposals, lauf, _ = welt
    task = aufgabe(tasks, 'Freigabe Flyer von Anna', wartet_auf='Anna Berg')
    andere = mail(episodes, 'Sommerfest', 'Hallo Lena, kommst du zum Sommerfest?', von=ANNA, an=[LENA], kennung='a4')
    assert lauf.schritt() == {'geprueft': 1, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 1}
    assert tasks.get(task.id).wartet_auf == 'Anna Berg'
    [vorschlag] = vorschlaege(proposals, ProposalKind.TASK_WAITING_RESOLVED)
    assert vorschlag.statement == 'Wieder bei dir? „Freigabe Flyer von Anna“'
    lauf.vorschlag_verwerfen(vorschlag.id)
    assert proposals.get(vorschlag.id).state is ProposalState.REJECTED
    assert tasks.post_getrennt(task.id, andere.id) is True
    assert tasks.get(task.id).wartet_auf == 'Anna Berg'
    # Ohne bekannte Adresse bleibt auch ein Worttreffer ein Bestätigungsvorschlag.
    mail(episodes, 'Flyer', 'Hallo Lena, die Freigabe für den Flyer ist erteilt.', von=ANNA, an=[LENA], kennung='a5')
    assert lauf.schritt()['vorschlaege'] == 1 and tasks.get(task.id).wartet_auf == 'Anna Berg'


def test_fremde_mail_erledigt_nie_eine_aufgabe_die_bei_dir_liegt(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    mail(episodes, 'AW: Druckdaten für den Flyer', 'Haben Sie die Druckdaten schon?', von=ANNA, an=[LENA], kennung='a6', antwort_auf=['a1'])
    assert lauf.schritt() == {'geprueft': 2, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
    assert tasks.get(task.id).status is TaskStatus.OPEN


# -- Rückgängig und Merkliste ----------------------------------------------------


def test_rueckgaengig_stellt_her_und_verhindert_wiederholung(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    antwort = mail(episodes, 'AW: Druckdaten für den Flyer', 'Anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l12', antwort_auf=['a1'])
    assert lauf.schritt()['vorschlaege'] == 1
    assert tasks.get(task.id).status is TaskStatus.OPEN
    [vorschlag] = vorschlaege(proposals)
    lauf.vorschlag_annehmen(vorschlag.id)
    wieder = lauf.rueckgaengig(task.id)
    assert wieder.status is TaskStatus.OPEN and wieder.done_at is None and wieder.erledigt_grund is None
    assert [e['kind'] for e in tasks.history(task.id)][0] == 'post_undone'
    assert tasks.post_getrennt(task.id, antwort.id) is True
    with pytest.raises(LookupError):
        lauf.rueckgaengig(task.id)   # nichts mehr zurückzunehmen
    with pytest.raises(KeyError):
        lauf.rueckgaengig('t-gibt-es-nicht')
    # Dieselbe Mail noch einmal: getrennt heißt getrennt, weder automatisch noch als Vorschlag.
    assert lauf.verarbeiten(episodes.get(antwort.id)) == {'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
    assert tasks.get(task.id).status is TaskStatus.OPEN and vorschlaege(proposals) == []
    # Rückgängig bei „wieder bei dir“ stellt das Warten samt Datum wieder her.
    eigene = mail(episodes, 'Bitte Freigabe', 'Jonas, bitte die Freigabe schicken.', von=LENA, an=[JONAS], tage=10, kennung='l-jonas')
    wartend = aufgabe(tasks, 'Freigabe von Jonas', quelle=eigene, wartet_auf='Jonas Keller', tage=9)
    mail(episodes, 'Freigabe', 'Die Freigabe ist da.', von=JONAS, an=[LENA], kennung='j1')
    assert lauf.schritt()['zurueck'] == 1
    her = lauf.rueckgaengig(wartend.id)
    assert her.wartet_auf == 'Jonas Keller' and her.wartet_seit == JETZT - timedelta(days=9) and her.geaendert_grund is None


def test_mail_wird_nur_einmal_verarbeitet_auch_nach_neustart(welt, tmp_path):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    antwort = mail(episodes, 'AW: Druckdaten für den Flyer', 'Anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l13', antwort_auf=['a1'])
    assert lauf.schritt()['geprueft'] == 2
    assert tasks.post_mail_verarbeitet(antwort.id, antwort.digest) is True
    assert tasks.post_stand() == episodes.letzte_zeile()  # der Stand rückt vor: der nächste Takt liest nur Neues
    assert lauf.schritt() == {'geprueft': 0, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
    tasks.reopen(task.id)
    tasks.close()
    neu = TaskStore(tmp_path / 'tasks.sqlite3')
    try:
        zweiter = Lauf(neu, episodes, proposals, eigene=lambda: [ICH], jetzt=lambda: JETZT)
        assert zweiter.schritt() == {'geprueft': 0, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
        assert neu.get(task.id).status is TaskStatus.OPEN
    finally:
        neu.close()


def test_bestand_von_vor_dem_umbau_wird_nicht_neu_gedeutet(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    try:
        bitte = bitte_von_anna(episodes)
        task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
        mail(episodes, 'AW: Druckdaten für den Flyer', 'Anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l14', antwort_auf=['a1'])
        lauf = Lauf(tasks, episodes, proposals, eigene=lambda: [ICH], jetzt=lambda: JETZT)
        assert lauf.schritt() == {'geprueft': 0, 'erledigt': 0, 'zurueck': 0, 'vorschlaege': 0}
        assert tasks.get(task.id).status is TaskStatus.OPEN
        mail(episodes, 'AW: AW: Druckdaten für den Flyer', 'Und hier die Druckdaten noch einmal.', von=LENA, an=[ANNA], kennung='l15', antwort_auf=['a1'])
        assert lauf.schritt()['vorschlaege'] == 1
        assert tasks.get(task.id).status is TaskStatus.OPEN
    finally:
        for store in (episodes, tasks, proposals):
            store.close()


def test_migration_legt_merkliste_und_trennung_an(tmp_path):
    import sqlite3
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    tasks.close()
    conn = sqlite3.connect(tmp_path / 'tasks.sqlite3')
    assert conn.execute('PRAGMA user_version').fetchone()[0] == 5  # 5: Aufgaben von selbst (test_aufgaben_von_selbst.py)
    tabellen = {z[0] for z in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'aufgaben_post_mails', 'aufgaben_post_getrennt', 'aufgaben_post_stand'} <= tabellen
    conn.close()


# -- Briefing und Logbuch ---------------------------------------------------------


def test_briefing_zeile_hoechstens_einmal(welt):
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    a = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    assert aufgaben_post.heute(tasks, JETZT) == []
    mail(episodes, 'AW: Druckdaten für den Flyer', 'Anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l16', antwort_auf=['a1'])
    zweite = mail(episodes, 'Rückseite', 'Bitte die Rückseite prüfen.', von=JONAS, an=[LENA], tage=1, kennung='j2')
    b = aufgabe(tasks, 'Rückseite für Jonas prüfen', quelle=zweite)
    mail(episodes, 'AW: Rückseite', 'Hallo Jonas, die Rückseite ist geprüft.', von=LENA, an=[JONAS], kennung='l17', antwort_auf=['j2'])
    assert lauf.schritt()['vorschlaege'] == 2
    for vorschlag in vorschlaege(proposals):
        lauf.vorschlag_annehmen(vorschlag.id)
    heute = aufgaben_post.heute(tasks, JETZT)
    assert [h['id'] for h in heute] == [b.id, a.id] or [h['id'] for h in heute] == [a.id, b.id]
    assert all(h['satz'].startswith('Erledigt nach deiner Bestätigung') for h in heute)
    lage = tagesbriefing.erstellen([], [], None, jetzt=JETZT, aufgaben_post=heute)
    zeilen = [z for z in lage.zeilen if z.art == 'aufgaben_post']
    assert len(zeilen) == 1
    assert zeilen[0].text.startswith('Erledigt durch deine Mail an ') and 'Eine weitere Aufgabe ebenso.' in zeilen[0].text
    assert [a.art for a in zeilen[0].aktionen] == ['aufgabe'] and zeilen[0].aktionen[0].ref in (a.id, b.id)
    # Gestern Erledigtes steht morgen nicht mehr da; was zurückgenommen wurde, auch nicht.
    assert aufgaben_post.heute(tasks, JETZT + timedelta(days=1)) == []
    lauf.rueckgaengig(a.id)
    assert [h['id'] for h in aufgaben_post.heute(tasks, JETZT)] == [b.id]
    assert tagesbriefing.erstellen([], [], None, jetzt=JETZT, aufgaben_post=[]).zeilen == []


def test_logbuch_zaehlt_aufgaben_nach_der_post():
    from icarus_memory.logbuch import Ereignis, drei_zeilen
    seit = JETZT - timedelta(hours=12)
    ereignisse = [Ereignis(1, JETZT - timedelta(hours=1), 'aufgabe_post', {'sorte': 'erledigt', 'aufgabe': 't-1', 'mail': 'e-1'}),
                  Ereignis(2, JETZT - timedelta(hours=1), 'aufgabe_post', {'sorte': 'zurueck', 'aufgabe': 't-2', 'mail': 'e-2'})]
    z = zusammenfassen(ereignisse, seit, JETZT)
    assert z.aufgaben_post == {'erledigt': 1, 'zurueck': 1} and not z.leer
    assert z.to_dict()['aufgaben_post'] == {'erledigt': 1, 'zurueck': 1}
    assert drei_zeilen(z) == ['Seit gestern Abend: 1 Aufgabe nach deiner Post erledigt, 1 Aufgabe wieder bei dir.']


# -- Akte: Braucht dich -----------------------------------------------------------


def test_akte_zeigt_die_aenderung_unter_braucht_dich(welt):
    from icarus_memory.akten import Akten
    from icarus_memory.bezuege import Bezuege
    from tests.test_akten import einordnen
    episodes, tasks, proposals, lauf, _ = welt
    bitte = bitte_von_anna(episodes)
    einordnen(episodes, bitte, [(BITTE, 'request')])
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    mail(episodes, 'AW: Druckdaten für den Flyer', 'Anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l18', antwort_auf=['a1'])
    assert lauf.schritt()['vorschlaege'] == 1
    assert tasks.get(task.id).status is TaskStatus.OPEN
    [vorschlag] = vorschlaege(proposals)
    lauf.vorschlag_annehmen(vorschlag.id)
    bezuege = Bezuege(episodes, workspace=None, eigene=lambda: [ICH])
    akten = Akten(episodes, bezuege, claims=None, aufgaben=lambda sache, ids: tasks.all_tasks())
    bezuege.aktualisieren()
    akte = akten.akte('person:a:anna.berg@example.org', jetzt=JETZT, ansicht=True)
    punkte = [p for p in akte['braucht_dich']['eintraege'] if p['art'] == 'aufgabe_post']
    assert len(punkte) == 1
    assert punkte[0]['aufgabe'] == {'id': task.id, 'title': 'Druckdaten an Anna schicken'} and punkte[0]['wahl'] == []
    assert punkte[0]['satz'] == 'Erledigt nach deiner Bestätigung zur Mail an Anna Berg vom 21. Oktober.'
    assert punkte[0]['ziel'] == f'p:{task.id}'
    # Die offene Bitte gilt in der Akte als erledigt (durch die Aufgabe), nicht mehr als offen.
    assert akte['offen']['eintraege'] == [] and akte['offen']['erledigt']['gesamt'] == 1
    lauf.rueckgaengig(task.id)
    akte = akten.akte('person:a:anna.berg@example.org', jetzt=JETZT, ansicht=True)
    assert [p for p in akte['braucht_dich']['eintraege'] if p['art'] == 'aufgabe_post'] == []


# -- Routen -------------------------------------------------------------------------


@pytest.fixture
def api(tmp_path, monkeypatch):
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.config import MailAccountSettings
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'))
    app.state.settings.mail_accounts.append(MailAccountSettings(id='k1', label='Probe', imap_host='127.0.0.1', user=ICH, sender=ICH))
    with TestClient(app) as client:
        yield app, client
        app.state.scheduler.stop()


def test_routen_rueckgaengig_und_vorschlaege(api):
    app, client = api
    episodes, tasks, proposals = app.state.episodes, app.state.tasks, app.state.proposals
    lauf = aufgaben_post.lauf_fuer(app)
    lauf.schritt()
    bitte = bitte_von_anna(episodes)
    task = aufgabe(tasks, 'Druckdaten an Anna schicken', quelle=bitte)
    assert client.post(f'/api/v1/tasks/{task.id}/rueckgaengig').status_code == 409
    assert client.post('/api/v1/tasks/t-fehlt/rueckgaengig').status_code == 404
    antwort = mail(episodes, 'AW: Druckdaten für den Flyer', 'Anbei die Druckdaten.', von=LENA, an=[ANNA], kennung='l19', antwort_auf=['a1'])
    assert aufgaben_post.schritt_fuer(app)['vorschlaege'] == 1
    [vorschlag] = client.get('/api/v1/aufgaben-post/vorschlaege').json()['items']
    assert client.post(f'/api/v1/aufgaben-post/vorschlaege/{vorschlag["id"]}/annehmen').status_code == 200
    gelesen = client.get(f'/api/v1/tasks/{task.id}').json()
    assert gelesen['status'] == 'done' and gelesen['erledigt_grund']['satz'].startswith('Erledigt nach deiner Bestätigung')
    seite = client.get('/api/v1/tasks', params={'view': 'done'}).json()
    assert seite['tasks'][0]['erledigt_grund']['episode_id'] == antwort.id
    zurueck = client.post(f'/api/v1/tasks/{task.id}/rueckgaengig')
    assert zurueck.status_code == 200 and zurueck.json()['status'] == 'open' and zurueck.json()['erledigt_grund'] is None
    assert client.post(f'/api/v1/tasks/{task.id}/rueckgaengig').status_code == 409
    # Vorschläge: Liste, annehmen, verwerfen; 404 für Unbekanntes, 409 für Entschiedenes.
    assert client.get('/api/v1/aufgaben-post/vorschlaege').json() == {'items': []}
    mail(episodes, 'AW: Flyer', 'Hallo Anna, ich melde mich.', von=LENA, an=[ANNA], kennung='l20', antwort_auf=['a1'])
    assert aufgaben_post.schritt_fuer(app)['vorschlaege'] == 1
    liste = client.get('/api/v1/aufgaben-post/vorschlaege').json()['items']
    assert len(liste) == 1 and liste[0]['aufgabe']['id'] == task.id and liste[0]['art'] == 'erledigt'
    assert client.post('/api/v1/aufgaben-post/vorschlaege/v-fehlt/annehmen').status_code == 404
    angenommen = client.post(f'/api/v1/aufgaben-post/vorschlaege/{liste[0]["id"]}/annehmen')
    assert angenommen.status_code == 200 and angenommen.json()['status'] == 'done'
    assert client.post(f'/api/v1/aufgaben-post/vorschlaege/{liste[0]["id"]}/annehmen').status_code == 409
    assert client.post(f'/api/v1/aufgaben-post/vorschlaege/{liste[0]["id"]}/verwerfen').status_code == 409
    assert client.get('/api/v1/aufgaben-post/vorschlaege').json() == {'items': []}
    # Das Tagesbriefing nennt die Erledigung einmal.
    lage = client.get('/api/v1/tag/briefing').json()['tageslage']
    assert [z['art'] for z in lage['zeilen']].count('aufgaben_post') == 1


def test_mailaufnahme_stoesst_den_lauf_an(api, monkeypatch):
    """Der Takt der Mailaufnahme prüft danach die Post gegen die Aufgaben, auch ohne Modell (nur neue Post)."""
    app, client = api
    aufrufe = []
    monkeypatch.setattr(aufgaben_post, 'schritt_fuer', lambda a: aufrufe.append(a) or {})
    app.state.scheduler.stop()
    app.state.scheduler._run_mail_intake(nur_neue_post=True)
    app.state.scheduler._run_mail_intake()
    assert aufrufe == [app, app]
