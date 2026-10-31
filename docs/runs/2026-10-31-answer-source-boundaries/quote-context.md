# Enger Zitatrand für vollständige Originalaussagen

Basis dieses separaten Nachtrags: `9fd6aefa59467e53bfa65d6c7720311052b8c6ac`.
Nur synthetische Quellen, lokale Teststores und feste Modellantworten. Keine
privaten Daten, echten Modelle, Netzprovider oder persönlichen Apps benutzt.
Der Root-Worktree wurde nicht geändert.

## Reproduzierter Fehler

`originalbindung` und `rollenbindung` verwarfen sämtliche Originaleinheiten
einer Quelle, sobald irgendwo im gesamten Prüfvolltext ein Anführungszeichen
stand. So konnte ein entferntes Footerwort wie `Hilfe unter "Kontakt".` die
vollständig sichtbare, unzitierte Aussage
`Ihre Rate wird automatisch abgebucht. Sie müssen nichts weiter tun.` sperren.

Permanentes RED vor der Änderung: der echte Store-/`prepare`-/Satzprüfungs-/
`render`-Pfad blieb bei `zitate`; beide echten Satzprüfungskontrollen mit dem
Zitat vor bzw. nach der Aussage scheiterten ebenfalls. Die Quellen wurden für
die synthetische Grenzprüfung mit bestehenden `_blocks`-Offsets indexiert.
Nur die externe Modellantwort war durch die bestehende ID-Attrappe ersetzt.

## Begrenzte Änderung

Beide Bindungen verwenden dieselbe Filterung vollständiger Originaleinheiten
aus dem gesamten Quelltext. Ohne Zitatzeichen bleibt das Verhalten identisch.
Zusätzlich wird genau **ein** nicht escaptes ASCII-Doppelquote-Paar mit
eindeutigen Öffnungs-/Schließrändern unterstützt. Sein voller Rawspan bleibt
ausgeschlossen, auch über mehrere Sätze und Absätze hinweg. Eine Einheit ist
nur außerhalb dieses Spans zulässig; eine bloße Prüfung der Zeichen innerhalb
des ausgewählten Satzes findet nicht statt.

Mehrere Paare, andere Zitatzeichen, Verschachtelung, offene, escapte oder
unklare Klammern bleiben vollständig gesperrt. Das ist bewusst kein allgemeiner
Zitatparser; entsprechende Quellen können weiter konservativ im Zitatmodus
landen. Die bestehende besondere Nach-/Vor-Regelausnahme bleibt unverändert.

Die vorhandene Sichtbarkeitsprüfung vergleicht Rawwortlaut, keine projizierten
Offsets. Deshalb bleibt außerdem eine ansonsten unzitierte Einheit gesperrt,
wenn ihr voller Rawwortlaut ebenfalls innerhalb des Zitats steht. Ein dafür
ergänzter RED-Test zeigte: eine verdeckte unzitierte Stelle durfte sonst durch
eine sichtbare zitierte Kopie desselben Wortlauts als sichtbar gelten. Der
Filter schließt diesen mehrdeutigen Doppelbeleg konservativ aus.

Es ändern sich keine Originaltexte, Offsets, Quellfassungen, Klassifikationen,
Wirebudgets, Mehrsatzregeln oder Frischeprüfungen. Die Änderung betrifft nur die
Zulässigkeit vollständiger sichtbarer Originaleinheiten an den bestehenden
Regel- und Personenbindungstoren. Das Prüfmodell kann weiterhin keinen dort
verworfenen Satz freigeben.

## Nachweis

[Synthetischer Lauf](quote-context-result.json): 2.885 Zeichen Quelltext, exakt
zwei ASCII-Anführungszeichen im Footer außerhalb des Antwortauszugs. Ergebnis:
`saetze`, ein Satzaufruf, 192 Renderzeichen mit beiden Originalsätzen; der
gespeicherte Body bleibt identisch. Der positive Test prüft danach auch, dass
Widerruf die gespeicherte Antwort weiterhin ungültig macht.

`sidecar/tests/test_original_quote_context.py` enthält 21 Fälle:

- echte unzitierte Rate und benannte Person vor bzw. nach dem einfachen Zitat;
- zitierter Mittelsatz ohne eigene Anführungszeichen, auch bei einem
  Zitatspan über viele Absätze und einem zeichenfreien Antwortauszug;
- offene, verschachtelte, escapte, typografische und mehrfache Klammern;
- sichtbare zitierte Kopie eines verdeckten unzitierten Doppelvorkommens;
- Sichtbarkeit aus einer anderen Quelle, entfernter Qualifier und geänderte Person.

```sh
PYTHONPATH=sidecar:. python -m pytest -q \
  sidecar/tests/test_original_quote_context.py \
  sidecar/tests/test_original_sentence_selection.py \
  sidecar/tests/test_normative_paragraph_context.py \
  sidecar/tests/test_normative_source_binding.py \
  sidecar/tests/test_satzantwort.py sidecar/tests/test_satzpruefung.py
```

Der abschließende gezielte Lauf bestand mit **589 Tests** in 26,51 Sekunden,
mit einer vorhandenen Starlette/httpx-Deprecation-Warnung. Er umfasst außerdem
den vorausgehenden Parser-/Auszugsfix, bedingte Berichte, Prüfmodell und die
Pflichtkernprüfungen aus `CONTRIBUTING.md`. `git diff --check` ohne Befund.
Keine komplette Suite parallel zur privaten Root-Probe;
kein Push, PR oder Release. Die unabhängige Prüfung dieses Nachtrags ist ein
gesonderter Schritt nach dem lokalen Commit.
