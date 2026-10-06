"""Zweites Tor der Satzprüfung, das Modul für sich: Adapter je Modellfamilie, strenges Lesen, fail closed, Zeitbudget."""
import json
import time
from types import SimpleNamespace

import pytest

from icarus_memory import satzpruefung_modell as spm, zeitmessung
from icarus_memory.providers import Reply, ToolCall


class Pruefer:
    """Lokales Prüfmodell mit festen Antworten je Satz; merkt sich jede Anfrage."""

    is_local = True

    def __init__(self, antworten=None, model='pruef-1', warte=0.0, standard='{"urteil":"ja"}'):
        self.model = model
        self.antworten = antworten or {}
        self.warte = warte
        self.standard = standard
        self.anfragen: list[list[dict]] = []

    def _antwort(self, messages):
        self.anfragen.append(messages)
        if self.warte:
            time.sleep(self.warte)
        satz = spm.satz_der_anfrage(messages)
        antwort = next((a for k, a in self.antworten.items() if k in (satz or '')), self.standard)
        if isinstance(antwort, Exception):
            raise antwort
        return antwort if isinstance(antwort, Reply) else Reply(text=antwort, model=self.model)

    def complete_json(self, messages, *, max_tokens=256, schema=None):
        assert schema == spm.SCHEMA and max_tokens <= 64
        return self._antwort(messages)

    def complete(self, messages, tools):
        assert tools == []
        return self._antwort(messages)


def beleg(nummer=1, text='Die Geschäftsführung hat zugestimmt.', pruef_text='', kopf='Rückmeldung; 29.09.2026'):
    return SimpleNamespace(nummer=nummer, text=text, pruef_text=pruef_text, kopf=kopf, ref={'start': 0, 'end': 10})


def tor_mit(pruefer):
    return spm.tor('an', pruefer)


# -- Tor ------------------------------------------------------------------------------------------


def test_das_tor_ist_nur_mit_einstellung_an_und_lokalem_modell_aktiv():
    assert spm.tor('an', Pruefer()).aktiv and spm.tor('an', Pruefer()).zustand == spm.AN
    assert spm.tor('aus', Pruefer()).zustand == spm.AUS and not spm.tor('aus', Pruefer()).aktiv
    assert spm.tor('an', None).zustand == spm.KEIN_MODELL
    cloud = Pruefer()
    cloud.is_local = False
    assert spm.tor('an', cloud).zustand == spm.KEIN_MODELL, 'ein Anbieter, der nicht lokal ist, zählt nie'
    assert spm.urteilen([('Satz.', [beleg()])], spm.tor('aus', Pruefer())) == []


# -- Adapter je Modellfamilie ------------------------------------------------------------------------


@pytest.mark.parametrize('modell, familie', [
    ('bespoke-minicheck:7b', 'klassifikation'), ('hf.co/bespoke/bespoke-minicheck:7b', 'klassifikation'),
    ('tev1:4b', 'entscheidung'), ('tev1:0.8b', 'entscheidung'), ('qwen3.5:4b', 'json'), ('', 'json')])
def test_jede_modellfamilie_hat_genau_einen_adapter(modell, familie):
    assert spm.adapter_fuer(modell).familie == familie


def test_klassifikationsmodell_bekommt_dokument_und_behauptung_und_antwortet_yes_no():
    pruefer = Pruefer({'Betriebsrat': 'No', 'Geschäftsführung': 'Yes.'}, model='bespoke-minicheck:7b')
    urteile = spm.urteilen([('Die Geschäftsführung hat zugestimmt.', [beleg()]),
                            ('Der Betriebsrat hat zugestimmt.', [beleg()])], tor_mit(pruefer))
    assert [u.wert for u in urteile] == ['ja', 'nein']
    nachricht = pruefer.anfragen[0]
    assert len(nachricht) == 1 and nachricht[0]['role'] == 'user'
    assert nachricht[0]['content'].startswith('Document: [1] Rückmeldung; 29.09.2026\nDie Geschäftsführung hat zugestimmt.')
    assert nachricht[0]['content'].endswith('\nClaim: Die Geschäftsführung hat zugestimmt.')


@pytest.mark.parametrize('ausgabe', ['Yes, the claim is supported.', 'maybe', '', 'Ja'])
def test_klassifikation_liest_nur_genau_yes_oder_no(ausgabe):
    pruefer = Pruefer(standard=ausgabe, model='bespoke-minicheck:7b')
    [urteil] = spm.urteilen([('Satz.', [beleg()])], tor_mit(pruefer))
    assert urteil.wert == 'unklar' and urteil.grund == 'Prüfmodell: Antwort nicht lesbar'


def test_json_modell_bekommt_die_frage_mit_schema_und_nur_satz_und_belege():
    pruefer = Pruefer(model='qwen3.5:4b')
    spm.urteilen([('Die Geschäftsführung hat zugestimmt.', [beleg(pruef_text='Volltext der Quelle.', text='Auszug')])],
                 tor_mit(pruefer))
    system, nutzer = pruefer.anfragen[0]
    assert system['content'].startswith(spm.PRAEFIX) and spm.FRAGE in system['content']
    assert json.loads(nutzer['content']) == {'satz': 'Die Geschäftsführung hat zugestimmt.',
                                             'belege': '[1] Rückmeldung; 29.09.2026\nVolltext der Quelle.'}


@pytest.mark.parametrize('ausgabe, wert', [
    ('{"urteil":"ja"}', 'ja'), ('{"urteil":"nein"}', 'nein'), ('{"urteil":"unklar"}', 'unklar'),
    ('nein', 'nein'), (' Ja. ', 'ja'),
    ('{"urteil":"ja","grund":"passt"}', 'unklar'), ('{"urteil":"vielleicht"}', 'unklar'), ('ja, weil', 'unklar'),
    ('[]', 'unklar'), ('{', 'unklar')])
def test_json_wird_streng_gelesen(ausgabe, wert):
    [urteil] = spm.urteilen([('Satz.', [beleg()])], tor_mit(Pruefer(standard=ausgabe)))
    assert urteil.wert == wert


# -- Fail closed ---------------------------------------------------------------------------------------


def test_fehler_und_werkzeugaufrufe_des_modells_sind_unklar():
    werkzeug = Reply(text='', tool_calls=[ToolCall(id='1', name='x', arguments={})])
    pruefer = Pruefer({'A': RuntimeError('kaputt'), 'B': werkzeug})
    urteile = spm.urteilen([('A.', [beleg()]), ('B.', [beleg()])], tor_mit(pruefer))
    assert [(u.wert, u.grund) for u in urteile] == [('unklar', 'Prüfmodell: Fehler'),
                                                    ('unklar', 'Prüfmodell: Antwort nicht lesbar')]
    assert spm.Urteil('nein').grund == 'Prüfmodell: nicht gestützt' and spm.Urteil('ja').grund == ''


# -- Zeitbudget ----------------------------------------------------------------------------------------


def test_ein_langsamer_satz_gilt_nach_dem_satzbudget_als_unklar():
    pruefer = Pruefer(warte=0.5)
    start = time.monotonic()
    [urteil] = spm.urteilen([('Satz.', [beleg()])], tor_mit(pruefer), satz_budget=0.05, gesamt_budget=1.0)
    assert urteil.wert == 'unklar' and urteil.grund == 'Prüfmodell: keine Antwort im Zeitbudget'
    assert time.monotonic() - start < 0.3, 'Das Budget wird eingehalten, nicht die Antwort abgewartet'


def test_ist_das_gesamtbudget_verbraucht_wird_nicht_mehr_gefragt():
    pruefer = Pruefer(warte=0.08)
    start = time.monotonic()
    urteile = spm.urteilen([(f'Satz {i}.', [beleg()]) for i in range(5)], tor_mit(pruefer),
                           satz_budget=0.05, gesamt_budget=0.12)
    dauer = time.monotonic() - start
    assert [u.wert for u in urteile] == ['unklar'] * 5
    assert len(pruefer.anfragen) <= 3 and dauer < 0.3, (len(pruefer.anfragen), dauer)


def test_die_vorgaben_sind_zwei_sekunden_je_satz_und_sechs_gesamt():
    assert (spm.SATZ_BUDGET_S, spm.GESAMT_BUDGET_S) == (2.0, 6.0)


def test_managed_local_profile_allows_cold_start_but_respects_explicit_budget(monkeypatch):
    budgets = []
    def result(adapter, provider, sentence, sources, deadline):
        budgets.append(deadline)
        return spm.Urteil('ja')
    monkeypatch.setattr(spm, '_ein_urteil', result)
    selected = tor_mit(Pruefer(model='kingfisher-qwen3.5:9b-32k'))
    spm.urteilen([('Satz.', [beleg()])], selected, uhr=lambda: 0)
    spm.urteilen([('Satz.', [beleg()])], selected, satz_budget=.1, gesamt_budget=.2, uhr=lambda: 0)
    assert budgets == [8.0, .1]


def test_die_zeit_steht_im_abschnitt_pruefung_modell():
    zeiten = zeitmessung.Zeiten()
    spm.urteilen([('Satz.', [beleg()])], tor_mit(Pruefer()), zeiten=zeiten)
    assert 'pruefung_modell' in zeiten.als_dict()
    ohne = zeitmessung.Zeiten()
    spm.urteilen([('Satz.', [beleg()])], spm.OHNE, zeiten=ohne)
    assert 'pruefung_modell' not in ohne.als_dict(), 'Ein Abschnitt, der nicht lief, fehlt'


# -- Was das Modell sieht ------------------------------------------------------------------------------


def test_lange_quellen_gehen_als_fenster_um_die_fundstelle():
    text = 'A' * 5000 + 'Die Geschäftsführung hat zugestimmt.' + 'B' * 5000
    lang = SimpleNamespace(nummer=2, text='Auszug', pruef_text=text, kopf='Kopf', ref={'start': 5000, 'end': 5036})
    gezeigt = spm.belegtext([lang])
    assert 'Die Geschäftsführung hat zugestimmt.' in gezeigt and 'Auszug' not in gezeigt
    assert len(gezeigt) <= spm.MAX_BELEG_ZEICHEN + 20


def test_attrappen_erkennen_die_anfrage_und_den_satz():
    pruefer = Pruefer(model='bespoke-minicheck:7b')
    spm.urteilen([('Ein Satz.', [beleg()])], tor_mit(pruefer))
    assert spm.ist_pruefanfrage(pruefer.anfragen[0]) and spm.satz_der_anfrage(pruefer.anfragen[0]) == 'Ein Satz.'
    assert not spm.ist_pruefanfrage([{'role': 'system', 'content': 'Du formulierst die Antwort'}])
