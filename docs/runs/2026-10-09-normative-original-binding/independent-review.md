# Unabhängiges Review: normative Originalbindung

Basis `8394ff5169e28e0cc70bd48e818db123e2efb7f7`; abschließend geprüfter Produktstand einschließlich der unten dokumentierten Ergänzung: `ce39f71046581567d9915d1b06a73e991072f1f3`. Nur lesend; keine Modelle oder privaten Daten.

**Kein verbleibender Blocker im begrenzten Reviewumfang.** Der unten dokumentierte Bindungsfehler wurde unabhängig reproduziert, im Produkt korrigiert und erneut geprüft. Abschließend bestehen die **30 erforderlichen unabhängigen eingefrorenen Kontrollen** und die zwei gezielt ausgeführten Testdateien mit **88 Tests**. Das ist keine Freigabeaussage über Vollsuite, echtes Modellverhalten oder Gesamtprodukt.

## Behobener P1: Sichtbarkeit und zulässiger Quellenrahmen aus verschiedenen Belegen

Im zuerst geprüften Arbeitsdiff vereinigte `satzantwort.py`, `pruefe_satz` (damals Zeilen 394–400), die Menge sichtbarer Originalstellen über alle zitierten Belege. Separat vereinigte `satzpruefung.py`, `originalbindung` (damals Zeilen 732–736), die Stellen aus Quellen ohne Zitatzeichen. Der gleiche Beleg musste dadurch nicht beide Voraussetzungen erfüllen.

Reproduktion durch das unveränderte `formulieren`, mit einem synthetischen Legacy-Provider:

```python
candidate = 'Die Klappe darf nach der Kontrolle geöffnet werden.'
visible = 'Der Bericht liegt im Tresor.'
A = AntwortBeleg(1, {}, 'fact', 'A', 'A', '', visible, None,
    pruef_text=candidate + ' ' + visible, gekuerzt=True)
B = AntwortBeleg(2, {}, 'fact', 'B', 'B', '',
    'Alte Anweisung: „Zunächst wird das Datum notiert. ' + candidate
    + ' Diese Anweisung wurde verworfen.“', None)
# Provider liefert {'status':'antwort','saetze':[{'text':candidate,'belege':cites}]}
```

| cites | Beobachteter Status | Grund |
|---|---|---|
| `[1]` | `zitate` | Originalstelle nicht sichtbar |
| `[2]` | `zitate` | Quelle mit Zitatrahmen darf die Regel nicht begründen |
| `[1, 2]` | **`saetze`** | Keine Verwerfung; beide unzureichenden Voraussetzungen werden kombiniert |

Der Legacy-Adapter findet den Wortlaut in der angebotenen inneren Stelle von B, behält aber beide Belegnummern. Sichtbarkeit stammt dann aus B, Zulässigkeit aus dem versteckten Volltext von A. Das ist kein neuer Wahrheitsanspruch: Es umgeht den gerade eingeführten sichtbaren, zulässigen Originalvertrag. Die vorherige Baseline war bereits weiter permissiv; dieser Befund ist eine verbleibende Lücke der neuen Schutzwirkung, keine Behauptung einer gegenüber der Baseline neu entstandenen Fehlfreigabe.

Die Korrektur verwendet einen gemeinsamen Zeugen pro Antwortabschnitt: `originalbindung(..., sichtbar=...)` verlangt jetzt, dass eine tatsächlich zitierte vollständige Stelle in **derselben** zulässigen Quelle sichtbar ist. `pruefe_satz` verwendet diesen gemeinsamen Helfer auch für wiederhergestellte Antworten. Unabhängige Wiederholung ergibt nun für `[1]`, `[2]` und `[1, 2]` jeweils `zitate`. Ein zusätzlicher positiver Gegenversuch macht A tatsächlich sichtbar; derselbe Kandidat mit `[1, 2]` ergibt dann weiterhin `saetze`. Ein permanenter Regressionstest wurde vom Implementierer ergänzt. Die eingefrorenen Goldwerte wurden nicht geändert.

## Weitere Ergebnisse und Grenzen

- N01–N08 werden jetzt wie eingefroren erwartet abgelehnt; positive Originale und der gewöhnliche Faktenpfad bleiben in den gezielten Kontrollen nutzbar.
- Abkürzungen, innere Zeilenumbrüche, Semikolon/Colon, Fragezeichencluster, direkte/mehrsätzige Zitate, versteckter Volltext mit nur einem Beleg und erneutes Öffnen/Entziehen sind in den ausgeführten Tests abgedeckt.
- Die breitere `_quelle_fehlt`-Reaktion ist ausdrücklich implementiert und getestet, nicht als unbeabsichtigte Regression bewertet.
- N19 (`erforderlich`) bleibt optionale Erkennungsbreite. L01/L02 bleiben bekannte Mehrsatz-/Dokumentstatusgrenzen und sind keine Blocker dieses Inkrements.
- Keine Vollsuite, echten Modellläufe oder UI-Prüfung durchgeführt.

Eingefrorene Kontrollen: `/private/tmp/kingfisher-normative-source-holdouts-20261009.json`, SHA256 `a53217e6a52aa5a6c55728cc5ccc6d12ba21317a53538a391adbda970db4a361`. Eigene deterministische Ergebnisse: `/private/tmp/kingfisher-normative-independent-results-20261009.json`.

Abschließend vor und nach den Gegenproben bestätigte SHA256:

- `sidecar/icarus_memory/satzpruefung.py`: `cfa335f26376f52ba1d5d8164bdd6bbaf7f55423a9f798f5d85d9b760903b611`
- `sidecar/icarus_memory/satzantwort.py`: `80c32b29838c716f25668520d427ec9a5869984fab80c8b228734023fd32ba5f`

Ausgeführte gezielte Tests: `test_normative_source_binding.py` und `test_original_sentence_selection.py`, **87 bestanden in 0,88 Sekunden**. Keine Produktdatei durch den Reviewer geändert.

## Abschließende begrenzte Ergänzung: normativer Kandidat aus beschreibender Quelle

Commit `ce39f71046581567d9915d1b06a73e991072f1f3` erweitert ausschließlich den Auslöser der Originalbindung: Auch ein normatives Signal im Kandidaten selbst aktiviert die Bindung. Unabhängig gegen die gespeicherten Commitfassungen geprüft:

- Quelle: „Nach der Kontrolle wird die Klappe geöffnet.“
- Unbelegter Kandidat: „Nach der Kontrolle darf die Klappe geöffnet werden.“
- `8394ff5`: akzeptiert; `95a9129`: akzeptiert; `ce39f710`: abgelehnt.
- Im tatsächlichen `formulieren` ergibt der unbelegte Kandidat `zitate`; die unveränderte beschreibende Aussage bleibt `saetze`.
- Nach echtem EpisodeStore-Schließen/Wiederöffnen wird die alte erfundene Erlaubnis abgewiesen; dieselbe gespeicherte Hülle mit unverändertem Quellwortlaut wird weiterhin dargestellt.

Abschließende erneute Ausführung der beiden gezielten Testdateien: **88 bestanden in 0,85 Sekunden**. Endgültige, vor und nach der Prüfung bestätigte Fingerabdrücke:

- `sidecar/icarus_memory/satzpruefung.py`: `70d6d086165d59946431c6d14de67c8c2a8df0763fe81c2ba0db744eac3009b8`
- `sidecar/icarus_memory/satzantwort.py`: `80c32b29838c716f25668520d427ec9a5869984fab80c8b228734023fd32ba5f`

Keine zusätzliche Grammatikausweitung geprüft oder gefordert. L01/L02 bleiben die beschriebenen Grenzen.

## Nachprüfung der drei alten Erwartungen in `test_permission_applicability.py`

Die laufende Vollsuite meldete drei Fehler in dieser Datei. Auf unverändertem `ce39f710` unabhängig mit den konkreten Kandidaten geprüft: Alle drei folgen aus dem bewusst strengeren Originalvertrag, nicht aus einer unbeabsichtigten Freigabe oder dem Verlust vollständiger Originale.

1. `test_exact_and_supported_qualified_permission_wordings_pass`: `R508_RULE` besteht weiterhin. `QUALIFIED_TOWELS` ist gegenüber R508 eine Paraphrase und wird ausschließlich wegen fehlender Originalbindung abgelehnt; dieselbe Formulierung als eigene vollständige Quelle besteht. Den Test passend umbenennen, die übergreifende Paraphrase negativ prüfen und beide Wortlaute jeweils mit ihrer eigenen Originalquelle positiv prüfen.
2. `test_reordered_qualified_permission_matches_noun_after_modal_verb`: Die Umstellung wird gegenüber dem anders angeordneten Quellsatz abgelehnt. Beide Satzstellungen sind als jeweils unveränderte Originale zulässig. Negativ ergänzen/erhalten: „Die Abdeckung darf nicht entfernt werden.“ gegen das Original mit „vor der Abnahme“ scheitert weiterhin auch an der zeitlichen Anwendbarkeit.
3. `test_an_always_yes_model_gate_cannot_rescue_a_broadened_permission`: Erwartung jetzt `zitate` und keine ausgegebene Teilantwort. Die bestehenden starken Prüfungen bleiben: exakt `UNSCOPED_TOWELS` verworfen; ausschließlich `SOLVENT_BAN` erreicht den Ja-Prüfer. Die vollständige Quelle fehlt in der Teilantwort, daher greift der ausdrücklich erweiterte Vollständigkeitsschutz. Positive Ergänzung: IDs beider Originalstellen auswählen; Ergebnis `saetze`, exakt `[R508_RULE, SOLVENT_BAN]`, keine Verwerfung und beide Sätze vom Prüfmodell geprüft.

Alle genannten Gegenproben wurden ausgeführt; keine Produktlockerung oder Testdateiänderung vorgenommen. Die frühere Angabe „88 gezielte Tests“ bezog sich ausschließlich auf die zwei dort genannten Dateien, nicht auf die noch laufende Vollsuite.
