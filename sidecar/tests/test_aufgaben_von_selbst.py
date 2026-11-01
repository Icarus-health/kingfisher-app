"""Aufgaben von selbst (Paket A, 26.10.2026): eindeutige Bitten und Zusagen aus neuer Post werden Aufgaben.

Zusicherungen:
1. Eine geprüfte Bitte von Anna an Lena allein (neu, unter „An“) wird ohne Klick eine Aufgabe: Herkunft „automatisch“
   mit Satz und Grundsatz, Person Anna, Vorschlag angenommen, Logbuch. Eine eigene Zusage ebenso, Person ist der
   Empfänger, „bis Freitag“ wird die Frist.
2. Was unsicher ist, bleibt Vorschlag, je mit Grund: Altbestand (älter als vorgestern, oder nur aus der
   Bestandsaufnahme), Rundmail (mehr als drei Empfänger, Newsletter), automatischer Absender, nur in Kopie, ungeprüfter
   Auftrag, schon vorhandene Aufgabe, eine Antwort im Verlauf.
3. Schalter aus: nichts entsteht (auch nichts gemerkt); wieder an: dann schon.
4. Höchstens zehn je Durchlauf; der Rest bleibt Vorschlag, auch im nächsten Durchlauf.
5. Rückgängig entfernt die Aufgabe, verwirft den Vorschlag und merkt es sich: Dieselbe Bitte kommt nicht wieder, auch
   nicht als neuer Vorschlag aus derselben Mail. Wiederherstellen bringt sie unverändert zurück.
6. Das Projekt kommt aus der Quelle oder aus der Absenderregel; Heute fasst zusammen („2 Aufgaben aus der Post angelegt.“);
   das Logbuch sagt es in einem Satz.
7. Über die Routen: Schalter, Heute, Rückgängig (404/409), „Alle übernehmen“ mit Projekt und Person und Rückgängig für die
   ganze Gruppe; die Übernahme von Heute nimmt den Projekthinweis mit statt keines.
Nur synthetische Daten (Lena Probe, Anna Berg, Jonas Keller).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import EpisodeKind, Provenance, SourceType, logbuch
from icarus_memory.aufgaben_von_selbst import JE_DURCHLAUF, Durchlauf, frist_aus, pruefen, schluessel
from icarus_memory.episodes import EpisodeStore
from icarus_memory.kontakte import fuer_mail
from icarus_memory.logbuch import Logbuch, drei_zeilen
from icarus_memory.proposals import ProposalKind, ProposalState, ProposalStore
from icarus_memory.task_review import current_task_context
from icarus_memory.tasks import TaskStore
from icarus_memory.workspace import WorkspaceStore

ICH = 'lena.probe@example.org'
LENA = f'Lena Probe <{ICH}>'
ANNA = 'Anna Berg <anna.berg@example.org>'
JONAS = 'Jonas Keller <jonas.keller@example.org>'
JETZT = datetime.now(timezone.utc).replace(microsecond=0)
BITTE = 'Kannst du mir bitte die Druckdaten für den Flyer schicken?'
ZUSAGE = 'Ich schicke dir die Unterlagen bis Freitag.'


@pytest.fixture
def welt(tmp_path):
    episodes = EpisodeStore(tmp_path / 'episodes.sqlite3')
    tasks = TaskStore(tmp_path / 'tasks.sqlite3')
    proposals = ProposalStore(tmp_path / 'proposals.sqlite3')
    workspace = WorkspaceStore(tmp_path / 'workspace.sqlite3')
    buch = Logbuch(tmp_path / 'logbuch.sqlite3', uhr=lambda: JETZT.timestamp())
    logbuch.verbinde(buch)
    lauf = Durchlauf(tasks, episodes, proposals, workspace=workspace, eigene=lambda: [ICH], jetzt=lambda: JETZT)
    yield episodes, tasks, proposals, workspace, lauf, buch
    logbuch.verbinde(None)
    for store in (episodes, tasks, proposals, workspace, buch):
        store.close()


_ZAEHLER = [0]


def mail(episodes, titel, text, *, von, an=(), cc=(), stunden=2, tage=0, ref=None):
    _ZAEHLER[0] += 1
    empfaenger = [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'an'} for a in an]
    empfaenger += [{'adresse': a.split('<')[-1].rstrip('>').strip(), 'name': a.split('<')[0].strip(), 'rolle': 'cc'} for a in cc]
    episode, _ = episodes.record(EpisodeKind.MESSAGE, titel, text,
                                 Provenance(SourceType.EMAIL, source_ref=ref or f'konto:{titel}:{_ZAEHLER[0]}'),
                                 participants=[von, *an, *cc], contacts=fuer_mail(von, empfaenger, eigene=[ICH]),
                                 occurred_at=JETZT - timedelta(days=tage, hours=stunden))
    return episode


def vorschlag(proposals, episodes, episode, titel, zitat, *, geprueft=True):
    """Wie die Aufgabenerkennung ablegt: Beleg, Kontextbindung und (geprüft) die Marke der Prüfung der ganzen Mail."""
    with proposals.transaction():
        proposals._record_task_candidates(  # noqa: SLF001
            episode.id, episode.digest, [{'title': titel, 'quote': zitat}],
            proposed_by='test/local' + ('/task-review-v1' if geprueft else ''),
            task_context=current_task_context(episodes, episode.id) if geprueft else None)
    return next(p for p in proposals.pending(ProposalKind.TASK, limit=-1)
                if p.evidence[0].episode_id == episode.id and p.statement == titel)


def bitte(episodes, proposals, *, titel='Druckdaten an Anna schicken', text=BITTE, **kw):
    kw.setdefault('von', ANNA)
    kw.setdefault('an', [LENA])
    episode = mail(episodes, 'Druckdaten', f'Hallo Lena,\n\n{text}\n\nAnna', **kw)
    return episode, vorschlag(proposals, episodes, episode, titel, text)


# -- 1. Eindeutig: angelegt -----------------------------------------------------------


def test_eindeutige_bitte_wird_ohne_klick_aufgabe_mit_herkunft_person_und_logbuch(welt):
    episodes, tasks, proposals, _, lauf, buch = welt
    episode, p = bitte(episodes, proposals)
    assert lauf.schritt() == {'geprueft': 1, 'angelegt': 1, 'vorschlaege': 0}
    task = tasks.get(f't-suggestion-{p.id}')
    assert task is not None and task.title == 'Druckdaten an Anna schicken'
    assert task.person == {'adresse': 'anna.berg@example.org', 'name': 'Anna Berg'}
    a = task.angelegt
    assert a['art'] == 'automatisch' and a['richtung'] == 'bitte' and a['episode_id'] == episode.id
    assert a['satz'].startswith('Von Kingfisher angelegt, weil Anna Berg dich am ') and a['satz'].endswith('darum gebeten hat.')
    assert a['grundsatz'] == 'Eine Bitte von Anna Berg direkt an dich, aus einer neuen Mail.'
    assert task.provenance.source_type is SourceType.INFERENCE and task.provenance.source_ref == f'episode:{episode.id}'
    assert task.provenance.verbatim == BITTE
    assert proposals.get(p.id).state is ProposalState.ACCEPTED and proposals.get(p.id).produced == task.id
    assert task.to_dict()['angelegt']['satz'] == a['satz'] and task.to_dict()['person']['name'] == 'Anna Berg'
    eintraege = [e for e in buch.ereignisse(JETZT - timedelta(days=1)) if e.art == 'aufgabe_post']
    assert [e.daten for e in eintraege] == [{'sorte': 'angelegt', 'aufgabe': task.id, 'mail': episode.id, 'wie': 'bitte'}]
    # Jeder Vorschlag einmal: der nächste Durchlauf prüft nichts erneut.
    assert lauf.schritt() == {'geprueft': 0, 'angelegt': 0, 'vorschlaege': 0}


def test_eigene_zusage_wird_aufgabe_fuer_den_empfaenger_mit_frist(welt):
    episodes, tasks, proposals, _, lauf, _ = welt
    # „Bis Freitag“ wäre an einem Freitag absichtlich mehrdeutig. Hier wird
    # die Aufgabenübernahme geprüft; die Wochentagsauflösung hat feste Fälle unten.
    datum = (JETZT + timedelta(days=7)).date()
    zusage = f'Ich schicke dir die Unterlagen bis zum {datum:%d.%m.%Y}.'
    episode = mail(episodes, 'Unterlagen', f'Hallo Anna,\n\n{zusage}\n\nLena', von=LENA, an=[ANNA])
    p = vorschlag(proposals, episodes, episode, 'Unterlagen an Anna schicken', zusage)
    assert lauf.schritt()['angelegt'] == 1
    task = tasks.get(f't-suggestion-{p.id}')
    assert task.person == {'adresse': 'anna.berg@example.org', 'name': 'Anna Berg'}
    assert task.angelegt['richtung'] == 'zusage' and 'weil du Anna Berg am ' in task.angelegt['satz']
    from icarus_memory.model import user_timezone
    assert task.due is not None
    lokal = task.due.astimezone(user_timezone())
    assert lokal.date() == datum and (lokal.hour, lokal.minute) == (23, 59)


def test_frist_nur_bei_genau_einer_eindeutigen_angabe():
    bezug = datetime(2026, 9, 28, 10, 0, tzinfo=timezone.utc)  # ein Montag
    assert frist_aus('Bitte bis Freitag schicken.', bezug).date().isoformat() == '2026-10-02'
    assert frist_aus('Bitte schick mir das.', bezug) is None
    assert frist_aus('Bis Freitag oder bis zum 9.10.2026.', bezug) is None  # zwei Angaben: keine
    assert frist_aus('Bitte bis nächste Woche.', bezug) is None  # uneindeutig


# -- 2. Unsicher: bleibt Vorschlag ----------------------------------------------------------


@pytest.mark.parametrize('art,erwartet', [
    ('alt', 'nicht_neu'), ('rundmail', 'rundmail'), ('newsletter', 'rundmail'), ('noreply', 'absender'),
    ('kopie', 'kopie'), ('ungeprueft', 'ungeprueft'), ('dublette', 'dublette')])
def test_unsicheres_bleibt_vorschlag_mit_grund(welt, art, erwartet):
    episodes, tasks, proposals, _, lauf, _ = welt
    if art == 'alt':
        episode, p = bitte(episodes, proposals, tage=10)
    elif art == 'rundmail':
        episode, p = bitte(episodes, proposals, an=[LENA, JONAS, 'Mia Sommer <mia@example.org>', 'Ole Wind <ole@example.org>'])
    elif art == 'newsletter':
        episode, p = bitte(episodes, proposals, text=BITTE + ' Newsletter abbestellen: hier.')
    elif art == 'noreply':
        episode, p = bitte(episodes, proposals, von='Druckerei <noreply@druckerei.example>')
    elif art == 'kopie':
        episode, p = bitte(episodes, proposals, an=[JONAS], cc=[LENA])
    elif art == 'ungeprueft':
        episode = mail(episodes, 'Druckdaten', f'Hallo Lena,\n\n{BITTE}', von=ANNA, an=[LENA])
        p = vorschlag(proposals, episodes, episode, 'Druckdaten an Anna schicken', BITTE, geprueft=False)
    else:
        tasks.add('Druckdaten an Anna schicken', Provenance(SourceType.USER_STATED))
        episode, p = bitte(episodes, proposals)
    assert lauf.schritt() == {'geprueft': 1, 'angelegt': 0, 'vorschlaege': 1}
    assert tasks.get(f't-suggestion-{p.id}') is None
    assert proposals.get(p.id).state is ProposalState.PENDING  # bleibt Vorschlag
    assert tasks.auto_ergebnis(p.id) == erwartet


def test_altbestand_aus_der_bestandsaufnahme_erzeugt_keine_aufgabe_auch_wenn_die_mail_von_gestern_ist(welt):
    episodes, tasks, proposals, _, lauf, _ = welt
    episode, p = bitte(episodes, proposals, stunden=20)
    with episodes._lock:  # noqa: SLF001 - wie die Bestandsaufnahme eines Postfachs
        episodes._conn.execute("INSERT INTO mail_intake_items (account, folder, generation, uid, lane, status, episode_id) "  # noqa: SLF001
                               "VALUES ('konto', 'INBOX', '1', 7, 'history', 'done', ?)", (episode.id,))
        episodes._conn.commit()  # noqa: SLF001
    assert lauf.schritt()['angelegt'] == 0
    assert tasks.auto_ergebnis(p.id) == 'bestand'


def test_viele_altbestandsvorschlaege_beim_ersten_einlesen_ergeben_keine_aufgabe(welt):
    episodes, tasks, proposals, _, lauf, _ = welt
    for i in range(30):
        bitte(episodes, proposals, titel=f'Rechnung {100 + i} prüfen', text=f'Bitte prüfe die Rechnung {100 + i}.', tage=40 + i)
    bericht = lauf.schritt()
    assert bericht['angelegt'] == 0 and bericht['vorschlaege'] == 30
    assert tasks.open_tasks() == []


def test_antwort_im_verlauf_haelt_es_beim_vorschlag():
    from types import SimpleNamespace
    episode = SimpleNamespace(kind=EpisodeKind.MESSAGE, provenance=SimpleNamespace(source_type=SourceType.EMAIL), occurred_at=JETZT, recorded_at=JETZT,
                              contacts=[], participants=[ANNA, LENA], body=BITTE)
    proposal = SimpleNamespace(statement='Druckdaten schicken', evidence=[SimpleNamespace(quote=BITTE)],
                               task_context='k', proposed_by='x/task-review-v1')
    urteil = pruefen(proposal, episode, eigene=[ICH], jetzt=JETZT, zeitstatus='followup', aus_bestand=False,
                     dublette=False, zurueckgenommen=False)
    assert not urteil.eindeutig and urteil.kuerzel == 'verlauf' and urteil.satz


# -- 3. Schalter -----------------------------------------------------------------------------


def test_schalter_aus_legt_nichts_an_und_merkt_nichts(welt):
    episodes, tasks, proposals, _, lauf, _ = welt
    assert tasks.auto_an() is True  # Vorgabe an
    tasks.auto_setzen(False)
    _, p = bitte(episodes, proposals)
    assert lauf.schritt() == {'geprueft': 0, 'angelegt': 0, 'vorschlaege': 0}
    assert tasks.get(f't-suggestion-{p.id}') is None and tasks.auto_ergebnis(p.id) is None
    tasks.auto_setzen(True)
    assert lauf.schritt()['angelegt'] == 1


# -- 4. Obergrenze -----------------------------------------------------------------------------


def test_hoechstens_zehn_je_durchlauf_der_rest_bleibt_vorschlag(welt):
    episodes, tasks, proposals, _, lauf, _ = welt
    for i in range(JE_DURCHLAUF + 2):
        bitte(episodes, proposals, titel=f'Rechnung {200 + i} prüfen', text=f'Bitte prüfe die Rechnung {200 + i}.')
    assert lauf.schritt() == {'geprueft': JE_DURCHLAUF + 2, 'angelegt': JE_DURCHLAUF, 'vorschlaege': 2}
    assert lauf.schritt()['angelegt'] == 0
    assert len(proposals.pending(ProposalKind.TASK, limit=-1)) == 2


# -- 5. Rückgängig ---------------------------------------------------------------------------


def test_rueckgaengig_entfernt_merkt_und_dieselbe_bitte_kommt_nicht_wieder(welt):
    episodes, tasks, proposals, _, lauf, buch = welt
    episode, p = bitte(episodes, proposals)
    lauf.schritt()
    task_id = f't-suggestion-{p.id}'
    lauf.zuruecknehmen(task_id)
    assert tasks.get(task_id) is None
    assert proposals.get(p.id).state is ProposalState.REJECTED
    assert [e['kind'] for e in tasks.history(task_id)][0] == 'auto_removed'
    # Dieselbe Mail ergibt erneut einen Vorschlag (etwa nach neuer Prüfung, mit leicht anderem Zitat): nicht wieder.
    zweiter = vorschlag(proposals, episodes, episode, 'Druckdaten an Anna schicken', 'die Druckdaten für den Flyer')
    assert zweiter.id != p.id
    lauf.schritt()
    assert tasks.get(f't-suggestion-{zweiter.id}') is None
    assert tasks.auto_ergebnis(zweiter.id) == 'zurueckgenommen'
    assert proposals.get(zweiter.id).state is ProposalState.REJECTED  # auch als Vorschlag kommt sie nicht wieder
    # Wiederherstellen: dieselbe Aufgabe wie vorher.
    wieder = lauf.wiederherstellen(task_id)
    assert wieder.id == task_id and wieder.angelegt['art'] == 'automatisch' and wieder.person['name'] == 'Anna Berg'
    assert proposals.get(p.id).state is ProposalState.ACCEPTED
    sorten = [e.daten['sorte'] for e in buch.ereignisse(JETZT - timedelta(days=1)) if e.art == 'aufgabe_post']
    assert sorten == ['angelegt', 'zurueckgenommen', 'wiederhergestellt']
    with pytest.raises(KeyError):
        lauf.wiederherstellen(task_id)


def test_rueckgaengig_nur_fuer_selbst_angelegte(welt):
    _, tasks, _, _, lauf, _ = welt
    eigene = tasks.add('Selbst notiert', Provenance(SourceType.USER_STATED))
    with pytest.raises(LookupError):
        lauf.zuruecknehmen(eigene.id)
    assert tasks.get(eigene.id) is not None
    with pytest.raises(KeyError):
        lauf.zuruecknehmen('t-gibt-es-nicht')


# -- 6. Projekt, Heute, Logbuch -------------------------------------------------------------


def test_projekt_aus_der_absenderregel_und_aus_der_quelle(welt):
    episodes, tasks, proposals, workspace, lauf, _ = welt
    projekt = workspace.add_project('Flyer Herbstfest', Provenance(SourceType.USER_STATED))
    for i in range(2):  # zwei frühere Mails von Anna im Projekt: die Absenderregel greift
        frueher = mail(episodes, f'Flyer {i}', f'Erste Entwürfe, Fassung {i}.', von=ANNA, an=[LENA], tage=20 + i, ref=f'konto:alt{i}')
        episodes.link_project(frueher.id, projekt.id)
    _, p = bitte(episodes, proposals, ref='konto:neu')
    lauf.schritt()
    task = tasks.get(f't-suggestion-{p.id}')
    assert task.project_id == projekt.id and task.angelegt['projekt_herkunft'] == 'sender_rule'
    zweite = mail(episodes, 'Plakat', 'Kannst du bitte das Plakat freigeben?', von=JONAS, an=[LENA])
    episodes.link_project(zweite.id, projekt.id)
    zweite = episodes.get(zweite.id)
    q = vorschlag(proposals, episodes, zweite, 'Plakat freigeben', 'Kannst du bitte das Plakat freigeben?')
    lauf.schritt()
    assert tasks.get(f't-suggestion-{q.id}').project_id == projekt.id


def test_heute_fasst_zusammen_und_logbuch_sagt_es_in_einem_satz(welt):
    episodes, tasks, proposals, _, lauf, buch = welt
    assert lauf.heute() == {'anzahl': 0, 'satz': '', 'aufgaben': []}
    bitte(episodes, proposals)
    bitte(episodes, proposals, titel='Rechnung 4711 prüfen', text='Bitte prüfe die Rechnung 4711.')
    lauf.schritt()
    heute = lauf.heute()
    assert heute['anzahl'] == 2 and heute['satz'] == '2 Aufgaben aus der Post angelegt.'
    assert all(a['satz'].startswith('Von Kingfisher angelegt') for a in heute['aufgaben'])
    zeilen = drei_zeilen(buch.seit(JETZT - timedelta(hours=1), JETZT + timedelta(minutes=1)))
    assert '2 Aufgaben aus der Post angelegt' in ' '.join(zeilen)


def test_schluessel_gleicht_schreibweisen_an():
    assert schluessel('Verträge prüfen!') == schluessel('vertraege   pruefen')


def test_migration_5_legt_die_merklisten_an_und_behaelt_aufgaben_aus_fassung_4(tmp_path):
    import sqlite3
    from icarus_memory import tasks as tasks_modul
    pfad = tmp_path / 'tasks.sqlite3'
    conn = sqlite3.connect(pfad)
    # Eine Datei der Fassung 4, mit einer Aufgabe darin.
    from icarus_memory.migrations import run_migrations
    run_migrations(conn, store='tasks', path=pfad, migrations=tasks_modul._MIGRATIONS[:4])  # noqa: SLF001
    conn.close()
    alt = TaskStore(pfad)
    alt.close()
    store = TaskStore(pfad)
    aufgabe = store.add('Steuerbescheid ablegen', Provenance(SourceType.USER_STATED))
    assert store.get(aufgabe.id).person is None and store.get(aufgabe.id).angelegt is None
    store.close()
    conn = sqlite3.connect(pfad)
    assert conn.execute('PRAGMA user_version').fetchone()[0] == 5
    tabellen = {z[0] for z in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {'aufgaben_auto_geprueft', 'aufgaben_auto_zurueck', 'aufgaben_auto_einstellung'} <= tabellen
    conn.close()


# -- 7. Über die Routen ------------------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from icarus_memory import MemoryBackend, SelfModelStore
    from icarus_memory.audit import AuditLog
    from icarus_memory.server import create_app
    monkeypatch.setenv('ICARUS_DATA_DIR', str(tmp_path))
    app = create_app(SelfModelStore(MemoryBackend(), subject_id='test'), audit=AuditLog(tmp_path / 'audit.sqlite3'),
                     tasks=TaskStore(tmp_path / 'tasks.sqlite3'), workspace=WorkspaceStore(tmp_path / 'workspace.sqlite3'),
                     episodes=EpisodeStore(tmp_path / 'episodes.sqlite3'))
    with TestClient(app) as c:
        app.state.scheduler.stop()
        yield c


def test_routen_schalter_durchlauf_heute_rueckgaengig_und_wiederherstellen(client):
    app = client.app
    assert client.get('/api/v1/aufgaben-von-selbst/einstellung').json() == {'an': True}
    assert client.put('/api/v1/aufgaben-von-selbst/einstellung', json={'an': False}).json() == {'an': False}
    episode, p = bitte(app.state.episodes, app.state.proposals)
    assert client.post('/api/v1/aufgaben-von-selbst/durchlauf').json()['angelegt'] == 0
    assert client.put('/api/v1/aufgaben-von-selbst/einstellung', json={'an': True}).json() == {'an': True}
    assert client.post('/api/v1/aufgaben-von-selbst/durchlauf').json()['angelegt'] == 1
    heute = client.get('/api/v1/aufgaben-von-selbst/heute').json()
    assert heute['anzahl'] == 1 and heute['satz'] == '1 Aufgabe aus der Post angelegt.'
    task_id = heute['aufgaben'][0]['id']
    aufgabe = client.get(f'/api/v1/tasks/{task_id}').json()
    assert aufgabe['angelegt']['art'] == 'automatisch' and aufgabe['person']['adresse'] == 'anna.berg@example.org'
    zurueck = client.post('/api/v1/aufgaben-von-selbst/rueckgaengig', json={'task_ids': [task_id]})
    assert zurueck.status_code == 200 and zurueck.json()['satz'] == '1 Aufgabe zurückgenommen.'
    assert client.get(f'/api/v1/tasks/{task_id}').status_code == 404
    assert client.get('/api/v1/aufgaben-von-selbst/heute').json()['anzahl'] == 0
    assert client.post(f'/api/v1/aufgaben-von-selbst/{task_id}/rueckgaengig').status_code == 404
    assert client.post(f'/api/v1/aufgaben-von-selbst/{task_id}/wiederherstellen').status_code == 200
    assert client.get(f'/api/v1/tasks/{task_id}').status_code == 200
    assert client.post(f'/api/v1/aufgaben-von-selbst/{task_id}/wiederherstellen').status_code == 404
    hand = client.post('/api/v1/tasks', json={'title': 'Von Hand'}).json()
    assert client.post(f'/api/v1/aufgaben-von-selbst/{hand["id"]}/rueckgaengig').status_code == 409


def test_alle_uebernehmen_mit_projekt_und_person_und_rueckgaengig_fuer_die_gruppe(client):
    app = client.app
    episodes, proposals = app.state.episodes, app.state.proposals
    projekt = app.state.workspace.add_project('Flyer Herbstfest', Provenance(SourceType.USER_STATED))
    for i in range(2):
        frueher = mail(episodes, f'Flyer {i}', f'Entwurf {i}.', von=ANNA, an=[LENA], tage=20 + i, ref=f'konto:alt{i}')
        episodes.link_project(frueher.id, projekt.id)
    # Beide unsicher (nur in Kopie): sie bleiben Vorschläge, „Alle übernehmen“ nimmt sie in einem Klick.
    _, p1 = bitte(episodes, proposals, an=[JONAS], cc=[LENA], ref='konto:n1')
    datum = (JETZT + timedelta(days=7)).date()
    _, p2 = bitte(episodes, proposals, an=[JONAS], cc=[LENA], titel='Rechnung 4711 prüfen',
                  text=f'Bitte prüfe die Rechnung 4711 bis zum {datum:%d.%m.%Y}.', ref='konto:n2')
    assert client.post('/api/v1/aufgaben-von-selbst/durchlauf').json()['angelegt'] == 0
    seite = client.get('/api/v1/task-candidates/page').json()
    zeilen = {z['id']: z for z in seite['items']}
    assert zeilen[p1.id]['person_vorschlag'] == {'adresse': 'anna.berg@example.org', 'name': 'Anna Berg'}
    assert zeilen[p2.id]['frist_vorschlag'] is not None and zeilen[p1.id]['frist_vorschlag'] is None
    assert zeilen[p1.id]['project_suggestion']['project_id'] == projekt.id
    antwort = client.post('/api/v1/task-candidates/alle-uebernehmen', json={'ids': [p1.id, p2.id]}).json()
    assert antwort['fehler'] == [] and len(antwort['aufgaben']) == 2
    assert all(a['project_id'] == projekt.id and a['person']['name'] == 'Anna Berg' for a in antwort['aufgaben'])
    assert all(a['angelegt']['art'] == 'alle_uebernehmen' for a in antwort['aufgaben'])
    assert client.get('/api/v1/task-candidates/page').json()['total'] == 0
    zurueck = client.post(f'/api/v1/task-candidates/gruppe/{antwort["gruppe"]}/rueckgaengig').json()
    assert zurueck == {'zurueckgenommen': 2, 'geblieben': 0}
    assert client.get('/api/v1/task-candidates/page').json()['total'] == 2  # wieder offen, nicht verworfen
    assert app.state.tasks.open_tasks() == []
    assert client.post('/api/v1/task-candidates/gruppe/g-unbekannt/rueckgaengig').status_code == 404


def test_uebernahme_von_heute_nimmt_den_projekthinweis_mit(client):
    app = client.app
    episodes, proposals = app.state.episodes, app.state.proposals
    projekt = app.state.workspace.add_project('Flyer Herbstfest', Provenance(SourceType.USER_STATED))
    for i in range(2):
        frueher = mail(episodes, f'Flyer {i}', f'Entwurf {i}.', von=ANNA, an=[LENA], tage=20 + i, ref=f'konto:alt{i}')
        episodes.link_project(frueher.id, projekt.id)
    _, p = bitte(episodes, proposals, an=[JONAS], cc=[LENA], ref='konto:n1')
    ohne = client.post(f'/api/v1/task-candidates/{p.id}/accept', json={'title': p.statement, 'project_id': None,
                                                                      'zuordnung_aus_vorschlag': True}).json()
    assert ohne['project_id'] == projekt.id and ohne['person']['name'] == 'Anna Berg'
    _, q = bitte(episodes, proposals, an=[JONAS], cc=[LENA], titel='Rechnung 4711 prüfen', text='Bitte prüfe die Rechnung 4711.', ref='konto:n2')
    ausdruecklich = client.post(f'/api/v1/task-candidates/{q.id}/accept', json={'title': q.statement, 'project_id': None}).json()
    assert ausdruecklich['project_id'] is None  # „Ohne Projekt“ gewählt bleibt ohne Projekt
