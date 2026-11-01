"""Nur native Kingfisher-Defaults erweitern; keine echten Wartezeiten/Modelle."""
from types import SimpleNamespace

import pytest

from icarus_memory import providers, satzpruefung_modell as spm
from tests.test_satzpruefung_modell import Pruefer, beleg

PROFILE = 'kingfisher-qwen:9b-32k'
QUESTION = 'Welches Prüfdatum nennt das Formular?'
ROW = 'Prüfdatum\n18.11.2026'


def run(monkeypatch, *, native=(QUESTION, QUESTION), model=PROFILE, durations=(9.2, 9.2),
        per=None, total=None, outer=None, gap=0., verdicts=('ja', 'ja'), texts=None):
    elapsed, budgets, separated = [0.], [], [False]
    def clock():
        if len(budgets) == 1 and not separated[0]:
            elapsed[0] += gap
            separated[0] = True
        return elapsed[0]
    def judge(adapter, provider, sentence, sources, deadline):
        index = len(budgets)
        budgets.append(deadline)
        elapsed[0] += min(durations[index], deadline)
        return spm.Urteil(verdicts[index]) if durations[index] <= deadline and verdicts[index] else spm.Urteil('unklar', 'zeit')
    monkeypatch.setattr(spm, '_ein_urteil', judge)
    monkeypatch.setattr(providers, 'time', SimpleNamespace(monotonic=lambda: elapsed[0]))
    count = len(native) if native is not None else len(durations)
    jobs = [(ROW, [beleg(i + 1, text=texts[i] if texts else ROW)]) for i in range(count)]
    arguments = dict(native_fragen=list(native) if native is not None else None,
                     satz_budget=per, gesamt_budget=total, uhr=clock)
    if outer is None:
        result = spm.urteilen(jobs, spm.tor('an', Pruefer(model=model)), **arguments)
    else:
        with providers.json_request_deadline(outer):
            result = spm.urteilen(jobs, spm.tor('an', Pruefer(model=model)), **arguments)
    return [r.wert for r in result], budgets, elapsed[0]


@pytest.mark.parametrize('count', [1, 2])
def test_native_standard_erlaubt_9_2_sekunden_ohne_echte_wartezeit(monkeypatch, count):
    result, budgets, elapsed = run(monkeypatch, native=[QUESTION] * count, durations=[9.2] * count)
    assert result == ['ja'] * count and budgets == [12.] * count
    assert elapsed == pytest.approx(9.2 * count)


@pytest.mark.parametrize('native,model,per,total,expected', [
    (None, PROFILE, None, None, [8., 4.]),
    ([QUESTION, None], PROFILE, None, None, [8., 4.]),
    ([QUESTION] * 3, PROFILE, None, None, [8., 4.]),
    ([QUESTION, QUESTION], 'qwen:9b', None, None, [2., 2.]),
    ([QUESTION, ''], PROFILE, None, None, [8.]),
    ([QUESTION, ' '], PROFILE, None, None, [8., 8.]),
    ([QUESTION, 'x' * 2001], PROFILE, None, None, [8.]),
    ([QUESTION, True], PROFILE, None, None, [8.]),
    ([QUESTION, QUESTION], PROFILE, 8., None, [8., 8.]),
    ([QUESTION, QUESTION], PROFILE, 12., None, [12., 6.8]),
    ([QUESTION, QUESTION], PROFILE, None, 24., [8., 8.]),
    ([QUESTION, QUESTION], PROFILE, None, 12., [8., 4.]),
    ([QUESTION, QUESTION], PROFILE, 5., 8., [5., 3.]),
    ([QUESTION, QUESTION], PROFILE, .1, None, [.1, .1]),
])
def test_alle_ausnahmen_behalten_ihre_bisherigen_budgets(monkeypatch, native, model, per, total, expected):
    _, budgets, _ = run(monkeypatch, native=native, model=model, per=per, total=total,
                        durations=[9.2] * (len(native) if native is not None else 2))
    assert budgets == pytest.approx(expected)


@pytest.mark.parametrize('texts,expected', [(('',), [8.]), ((ROW, 'x' * 4001), [8.])])
def test_unvollstaendige_rawbelege_bekommen_keinen_erweiterten_standard(monkeypatch, texts, expected):
    _, budgets, _ = run(monkeypatch, native=[QUESTION] * len(texts), texts=texts, durations=[9.2] * len(texts))
    assert budgets == expected


@pytest.mark.parametrize('durations,gap,expected,elapsed', [
    ([12.1], 0., [12.], 12.),
    ([9.2, 12.1], 0., [12., 12.], 21.2),
    ([9.2, 11.5], 4., [12., 10.8], 24.),
])
def test_einzel_und_gesamtgrenze_bleiben_hart(monkeypatch, durations, gap, expected, elapsed):
    result, budgets, actual = run(monkeypatch, native=[QUESTION] * len(durations), durations=durations, gap=gap)
    assert result[-1] == 'unklar' and budgets == pytest.approx(expected) and actual == pytest.approx(elapsed)


@pytest.mark.parametrize('count,outer,expected', [(1, 9., [9.]), (2, 9., [9.]), (2, 15., [12., 5.8]),
                                               (1, -1., []), (2, -1., [])])
def test_aeussere_frist_hat_auch_bei_einem_einzelauftrag_vorrang(monkeypatch, count, outer, expected):
    result, budgets, _ = run(monkeypatch, native=[QUESTION] * count, durations=[9.2] * count, outer=outer)
    assert budgets == pytest.approx(expected) and result[-1] == 'unklar'


@pytest.mark.parametrize('negative', ['nein', 'unklar', None])
def test_negative_unklare_und_ausbleibende_urteile_bleiben_geschlossen(monkeypatch, negative):
    result, _, _ = run(monkeypatch, verdicts=['ja', negative], durations=[9.2, 12. if negative is None else 9.2])
    assert result == ['ja', negative or 'unklar']


def test_erste_quelle_ja_zweite_nach_zwoelf_sekunden_ohne_ergebnis_laesst_keinen_teilrest(stores, monkeypatch):
    from tests.test_docx_native_selection import Auswahl, answer, intake
    from icarus_memory import working_memory_answers as wma
    intake(stores, monkeypatch, 2)
    elapsed, budgets = [0.], []
    original = spm.urteilen
    def fake(adapter, provider, sentence, sources, deadline):
        budgets.append(deadline)
        elapsed[0] += 9.2 if len(budgets) == 1 else deadline
        return spm.Urteil('ja') if len(budgets) == 1 else spm.Urteil('unklar', 'zeit')
    monkeypatch.setattr(spm, '_ein_urteil', fake)
    monkeypatch.setattr(spm, 'urteilen', lambda *args, **kwargs: original(*args, **kwargs, uhr=lambda: elapsed[0]))
    saved, _, _, _ = answer(stores, Auswahl(empty=10), Pruefer(model=PROFILE))
    assert budgets == [12., 12.] and saved['satzantwort']['status'] == 'zitate'
    assert wma.satz_struktur(saved, *stores) is None and stores[1].all_claims() == []


from tests.test_docx_native_rows import stores  # noqa: E402,F401
