"""Microsoft Graph als Quelle (docs/50-microsoft-365.md): Outlook-Post über dieselbe Aufnahme, Kalender, Teams-Mitschriften.

Gegen die Graph-Attrappe auf 127.0.0.1, nur synthetische Daten; jeder andere Netzzugriff lässt den Test scheitern.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_memory import microsoft_anmeldung as ma, microsoft_graph as mg
from icarus_memory.episodes import EpisodeStore
from icarus_memory.mail_intake import Intake
from icarus_memory.microsoft_anmeldung import MicrosoftAnmeldung
from tests.graph_attrappe import ADRESSE, CLIENT_ID, MANDANT
from tests.microsoft_hilfen import Schluessel, Uhr, graph, kein_netz  # noqa: F401 - Fixtures


@pytest.fixture
def konto(graph, tmp_path):
    anm = MicrosoftAnmeldung(Schluessel())
    anm.keychain.set(ma.konto_schluessel(ADRESSE), json.dumps({
        'client_id': CLIENT_ID, 'mandant': MANDANT, 'refresh_token': 'erneuern-1',
        'scope': 'Calendars.Read Mail.Read OnlineMeetingTranscript.Read.All OnlineMeetings.Read User.Read offline_access'}))
    client = mg.GraphClient(lambda: anm.access_token(ADRESSE))
    ablage = mg.Postablage(tmp_path / 'microsoft.sqlite3')
    return anm, client, ablage


# -- Post über dieselbe Aufnahme ------------------------------------------------------------------------------------

def test_outlook_post_laeuft_durch_die_aufnahme_mit_staenden_und_reihenfolge(konto, graph, tmp_path):
    _, client, ablage = konto
    graph.seite = 1  # eine Nachricht je Seite: Die Bestandsaufnahme braucht mehrere Durchgänge
    post = mg.MicrosoftPost(ADRESSE, client, ablage)
    ep = EpisodeStore(tmp_path / 'episodes.sqlite3')
    intake = Intake(ep)
    ordner = [f['name'] for f in post.folders() if f['historical']]
    assert ordner == ['INBOX', 'SentItems']
    intake.start('ms', ordner)
    intake.step('ms', post, batch=2)
    stand = {f['folder']: f for f in intake.status('ms')['folders']}
    # Erste Seiten sind bekannt, der Rest noch nicht: der Stand zählt ehrlich, was schon gesehen ist.
    assert stand['INBOX']['total'] == 3 and not stand['INBOX']['inventory_complete']
    for _ in range(12):
        intake.step('ms', post, batch=4)
    stand = {f['folder']: f for f in intake.status('ms')['folders']}
    assert stand['INBOX']['inventory_complete'] and stand['SentItems']['inventory_complete']
    assert (stand['INBOX']['captured'], stand['SentItems']['captured']) == (7, 2)
    assert stand['INBOX']['pending'] == 0 and stand['INBOX']['total'] == 7
    # Der Verlauf von neu nach alt: Die Nummern folgen der Eingangszeit.
    with ep._lock:
        nummern = [u for (u,) in ep._conn.execute("SELECT uid FROM mail_intake_items WHERE folder='INBOX' ORDER BY uid")]
    kennungen = [ablage.kennung(ADRESSE, 'INBOX', u) for u in nummern]
    assert kennungen == [f'in-{i}' for i in range(7)]
    # Eine Quelle trägt Absender, Empfänger mit Rolle und das eigene Konto.
    with ep._lock:
        ids = [i for (i,) in ep._conn.execute("SELECT episode_id FROM mail_intake_items WHERE status='captured'")]
    quellen = [ep.get(i) for i in ids]
    assert len(quellen) == 9
    assert all(any('anna.keller@hochschule.example' in p for p in e.participants) for e in quellen)
    # Neue Post nach der vollständigen Bestandsaufnahme kommt über die Spur „neu“.
    graph.neue_post()
    post._zuletzt.clear()
    intake.step('ms', post, batch=4)
    with ep._lock:
        neu = ep._conn.execute("SELECT uid,status FROM mail_intake_items WHERE lane='live' AND folder='INBOX'").fetchall()
    assert len(neu) == 1 and neu[0][1] == 'captured'
    assert ablage.kennung(ADRESSE, 'INBOX', neu[0][0]) == 'neu-7'
    ep.close()


def test_einzelne_nachricht_mit_allem_was_die_aufnahme_braucht(konto, graph):
    _, client, ablage = konto
    post = mg.MicrosoftPost(ADRESSE, client, ablage)
    seite = post.inventory_page('INBOX', 0, None, 100)
    assert seite['upper_uid'] == mg.GRENZE and seite['uidvalidity'] == ablage.generation()
    nachricht = post.message_in_folder('INBOX', f"{seite['uidvalidity']}.{seite['uids'][0]}")
    assert nachricht.sender.startswith('Anna Keller <anna.keller@')
    assert {'name': 'Lena Probe', 'adresse': ADRESSE, 'rolle': 'an'} in nachricht.recipients
    assert nachricht.own_addresses == (ADRESSE,)
    assert 'synthetische Nachricht' in nachricht.body and nachricht.date is not None
    # Eine alte Generation wird abgewiesen wie ein geändertes UIDVALIDITY.
    from icarus_memory.connectors.mail import MailboxGenerationChanged
    with pytest.raises(MailboxGenerationChanged):
        post.inventory_page('INBOX', 0, None, 100, uidvalidity='1')
    # Text statt HTML und unveränderliche Kennungen werden ausdrücklich angefragt.
    abruf = [a for a in graph.anfragen if a['pfad'].startswith('/v1.0/me/messages/')][-1]
    assert 'outlook.body-content-type="text"' in abruf['prefer'] and 'ImmutableId' in abruf['prefer']
    liste = post.inbox(limit=3)
    assert len(liste) == 3 and post.message(liste[0].uid).subject == liste[0].subject


def test_nur_get_und_das_token_nur_an_graph(konto, graph):
    _, client, ablage = konto
    post = mg.MicrosoftPost(ADRESSE, client, ablage)
    for _ in range(4):
        post.inventory_page('INBOX', 0, None, 100)
    mg.MicrosoftKalender(client).events(days=7)
    assert {a['methode'] for a in graph.anfragen if a['pfad'].startswith('/v1.0/')} == {'GET'}
    assert not hasattr(mg.GraphClient, 'post') and not hasattr(mg.GraphClient, 'patch')
    gesehen = []
    fremd = mg.GraphClient(lambda: 'geheim', request=lambda *a, **k: gesehen.append(a) or (200, {}, b'{}'))
    for ziel in ('https://andere.example/v1.0/me', graph.graph + 'evil/me', 'http://127.0.0.1:1/v1.0/me'):
        with pytest.raises(mg.GraphFehler) as fehler:
            fremd.holen(ziel)
        assert fehler.value.grund == 'verboten'
    assert gesehen == [], 'das Token ging an eine fremde Adresse'


def test_drosselung_wird_respektiert(konto, graph):
    _, client, _ = konto
    graph.modus.add('drosseln')
    with pytest.raises(mg.GraphFehler) as fehler:
        client.holen('me')
    assert fehler.value.grund == 'gedrosselt' and 'von selbst weiter' in fehler.value.satz
    vorher = len(graph.anfragen)
    with pytest.raises(mg.GraphFehler):
        client.holen('me')
    assert len(graph.anfragen) == vorher, 'während der Pause geht keine Anfrage hinaus'


def test_abgemeldet_ist_ein_satz_bei_der_pruefung(konto, graph):
    anm, client, ablage = konto
    graph.modus.add('refresh_abgelaufen')
    post = mg.MicrosoftPost(ADRESSE, client, ablage)
    from icarus_memory import mail_anmeldung
    with pytest.raises(mail_anmeldung.Anmeldefehler) as fehler:
        mail_anmeldung.pruefe(post, 'graph.microsoft.com', name=ADRESSE)
    assert fehler.value.grund == 'abgemeldet' and 'Zugänge' in fehler.value.satz


# -- Kalender -------------------------------------------------------------------------------------------------------

def test_kalender_mit_seiten_teilnehmern_und_zeitzone(konto, graph):
    _, client, _ = konto
    jetzt = datetime.now(timezone.utc)
    termine = mg.MicrosoftKalender(client).events(days=7, at=jetzt - timedelta(days=2))
    assert [t.summary for t in termine] == ['Haushalt Fakultät', 'Sprechstunde']
    erster = termine[0]
    assert erster.start.tzinfo is not None and erster.end - erster.start == timedelta(hours=1)
    assert 'Anna Keller <anna.keller@hochschule.example>' in erster.attendees
    assert any(ADRESSE in t for t in erster.attendees)  # der Organisator gehört dazu
    assert erster.uid == 'ical-teams-1' and erster.location == 'Microsoft Teams-Besprechung'
    anfrage = [a for a in graph.anfragen if a['pfad'] == '/v1.0/me/calendarView'][0]
    assert 'outlook.timezone="UTC"' in anfrage['prefer']


# -- Teams-Mitschriften ---------------------------------------------------------------------------------------------

def test_mitschrift_mit_sprecher_und_uhrzeit():
    beginn = datetime(2026, 9, 30, 7, 2, tzinfo=timezone.utc)
    from tests.graph_attrappe import VTT
    t = mg.transkript_aus_vtt(VTT, 'Haushalt Fakultät', beginn, 'Teams: Haushalt.vtt')
    assert t.sprecher == ('Anna Keller', 'Lena Probe')
    zeilen = t.text.splitlines()
    assert zeilen[0].startswith('Anna Keller: [') and 'Guten Morgen' in zeilen[0]
    # Die Uhrzeit ist Beginn plus Versatz in der Zone des Nutzers (Vorgabe Europe/Berlin: 09:03 MESZ).
    assert '[09:03]' in t.text or '[07:03]' in t.text
    assert t.beginn == beginn and t.hinweise()['titel'] == 'Haushalt Fakultät'


def test_mitschriften_werden_abgeholt_und_nur_einmal(konto, graph):
    _, client, ablage = konto
    abgelegt = []

    class Ep:
        def __init__(self, n):
            self.id = f'ep-{n}'

    def ablegen(transkript, schluessel, ref):
        abgelegt.append((transkript, schluessel, ref))
        return Ep(len(abgelegt))
    lauf = mg.Mitschriften(ADRESSE, client, ablage, ablegen)
    assert lauf.durchgang() == {'besprechungen': 1, 'aufgenommen': 1, 'ohne': 0}
    transkript, schluessel, _ = abgelegt[0]
    assert schluessel == f'microsoft:teams:{ADRESSE}:mitschrift-1'
    assert 'Lena Probe: [' in transkript.text and transkript.titel == 'Haushalt Fakultät'
    inhalt = [a for a in graph.anfragen if a['pfad'].endswith('/content')]
    assert len(inhalt) == 1
    assert lauf.durchgang()['besprechungen'] == 0, 'eine aufgenommene Besprechung wird nicht erneut geholt'
    assert ablage.mitschriften(ADRESSE)[0]['stand'] == 'aufgenommen'


def test_ohne_freigabe_ein_ehrlicher_satz_und_kein_fehler(konto, graph):
    _, client, ablage = konto
    graph.modus.add('mitschriften_verboten')
    lauf = mg.Mitschriften(ADRESSE, client, ablage, lambda *a: pytest.fail('nichts ablegen'))
    assert lauf.durchgang() == {'besprechungen': 1, 'aufgenommen': 0, 'ohne': 1}
    zeile = ablage.mitschriften(ADRESSE)[0]
    assert zeile['stand'] == 'nicht_erlaubt' and 'IT' in zeile['satz']
    assert lauf.durchgang()['besprechungen'] == 0  # erst morgen wieder


def test_ablage_verliert_sich_und_beginnt_neu(tmp_path):
    a = mg.Postablage(tmp_path / 'm.sqlite3')
    g = a.generation()
    a.zuordnen('k', 'INBOX', [('x', datetime(2026, 1, 1, tzinfo=timezone.utc)), ('y', datetime(2026, 1, 1, tzinfo=timezone.utc))], neu=False)
    assert [u for _, u in a.seite('k', 'INBOX', 0, mg.GRENZE, 10)] == [1767225600, 1767225599]
    assert mg.Postablage(tmp_path / 'm.sqlite3').generation() == g
