# Gemeinsamer Arbeitsstand in Antwortentwürfen und Rückfragen

Automatische Antwortentwürfe dürfen bis zu zwei aktuelle, unbestätigte frühere Mails desselben Postfachs und exakt desselben Absenders verwenden. Die Auswahl nutzt den vorhandenen Gedächtnisweg. Der Betreff grenzt die Kandidatensuche ein; die vollständige begrenzte aktuelle Mail und Nutzeranweisung stehen der lokalen Auswahl zur Verfügung. Ein zu allgemeiner Betreff, unklare Identität/Zeit, Widerspruch, bestätigte konkurrierende Aussagen oder unvollständige Auswahl ergeben einen sichtbaren Hinweis statt stiller Quellenübernahme. Gesprächs- und Dokumentquellen werden in diesem Paket noch nicht automatisch an Mailentwürfe gebunden.

Der bearbeitbare Entwurf bleibt mit der geprüften Auswahl verbunden. Quellenänderungen, neue passende Korrekturen und konkurrierende bestätigte Aussagen werden vor Vorbereitung, Freigabe und tatsächlichem Versand neu geprüft. Die gespeicherte Herkunft wirkt auch auf abhängige Gesprächsantworten. Ein App-Neustart lässt offene Entwurfsbindungen ablaufen. Ablehnen bleibt bei ungültiger Grundlage möglich, ohne die alte Nachricht oder einen Modellaufruf zu benötigen. Alle Versandprüfungen verwenden ausschließlich einen synthetischen Sammelbehälter; keine echte Mail wurde versendet.

Unmittelbare Rückfragen wie „Welche Bedingung gilt dabei?“ oder „Kannst du mir das erklären?“ verwenden dieselbe ursprüngliche Suchfrage mit aktuellen Quellen. Nur die jeweils neue Rückfrage geht zusätzlich an die Auswahl; wiederholtes Nachfragen erweitert nicht laufend die Suchbegriffe. Neue Fragen und gemischte Handlungsaufträge bleiben getrennte Vorgänge.

## Lokaler Modelllauf

Die Erwartungen wurden vor dem ersten Lauf in `expected.json` festgehalten. Drei echte Aufrufe des vorhandenen lokalen `qwen3.5:4b` prüfen Einordnung, Auswahl und Antwortentwurf über die HTTP-Mailfunktion mit einem synthetischen Postfach. Der erste Lauf ist als `local-results-first-20260923.json` erhalten: Die Quelle wurde richtig ausgewählt, aber anschließend wegen der zu langen Suchanweisung verworfen. Der Ersatzentwurf erfand eine nicht belegte Formulierung zum Lieferstatus. Das ist ein fehlgeschlagener Entwicklungsnachweis.

Nach Trennung von begrenzter Betreffsuche und vollständiger Auswahlfrage wurde exakt derselbe Fall erneut durchgeführt. `local-results-retrieval-scope.json` zeigt die erwartete Originalquelle und einen Entwurf, der den 4. Oktober nur unter schriftlicher Freigabe nennt und ausdrücklich festhält, dass diese noch fehlt. Der ergänzte Gruß blieb mit der Quelle verbunden. Nach Entzug verschwand der Entwurf aus dem Gespräch und die Versandfreigabe wurde abgewiesen; keine Claims entstanden. Drei Modellaufrufe dauerten zusammen ungefähr neun Sekunden. Dies ist eine gezielte Integrationsprüfung und keine unabhängige allgemeine Erfolgsquote.

Zusätzlich dokumentiert `relative-corrections/` einen einmaligen separaten Komponentenlauf mit vier neuen synthetischen Quellen und zwei Fragen: eine datierte relative Terminänderung mit fortbestehender Bedingung sowie zwei widersprüchliche undatierte relative Termine. Die Änderung wurde ausgewählt, bei fehlender Zeitgrundlage blieben beide Quellen mit Rückfrage erhalten. Dieser Test belegt weder die allgemeine Zeitauflösung noch die gesamte HTTP-/Oberflächenkette.

## Nicht bestandene freie Formulierung

Ein zusätzlicher, vorher festgelegter Fall (`expected-date-context.json`) prüfte eine Nachricht vom 21. September mit „morgen um 11 Uhr“, einer schriftlichen Freigabebedingung und noch fehlender Freigabe. Trotz vorhandener Absender- und Datumsmetadaten machte das lokale Modell daraus im Entwurf den **23. September** und ließ die fehlende Freigabe weg. `local-results-date-context.json` bleibt unverändert als Fehlernachweis erhalten. Die bestandenen Herkunfts-/Entzugsprüfungen heben diesen semantischen Fehler nicht auf.

Deshalb wird der neue Quellenmodus auf datierte, dem Originalabsender zugeordnete **wörtliche Zitate** begrenzt. Der Antwortentwurf bleibt bearbeitbar; er behauptet keine automatische semantische Prüfung einer freien Umformulierung. Bestehende quellenlose Vorschläge bleiben als solche gekennzeichnet. Die Anleitung des Nutzers beeinflusst im Quellenmodus die Auswahl; sie wird nicht als garantiert umgesetzter Schreibauftrag ausgegeben.

Die Nachprüfung desselben fehlgeschlagenen Falls (`local-results-date-context-quoted.json`) bestand mit unveränderten Erwartungen: Originalabsender, Quellenzeit 21. September und der vollständige Wortlaut einschließlich „morgen“, Freigabebedingung und fehlender Freigabe bleiben erhalten. Es gibt keinen neu errechneten Liefertermin und keinen freien Modell-Entwurfsaufruf. Zwei echte lokale Aufrufe für Einordnung und Auswahl, zusammen rund acht Sekunden; Entzug versteckt den bearbeiteten Entwurf und blockiert die Freigabe. Das ist ein korrigierter Entwicklungsfall, keine zusätzliche unabhängige Erfolgsquote.

## Abschließende Prüfungen

- Produktcode `ea498dd9617b52fb9d5505e34457dc3591caff07`: **2314 Tests und 4 Untertests bestanden**, 182 Sekunden, zwei bekannte Starlette/httpx-Abkündigungswarnungen. Vollständiger Lauf von `sidecar/tests` und `scripts` mit vorbereiteten lokalen Testhelfern. Der erste Gesamtlauf zeigte neben fehlenden Testrechten eine echte Regression bei eingesetzten Agenten ohne Mail-Sink; die App initialisiert den Freigabekontext jetzt in jeder Konfiguration. 81 betroffene Fälle bestanden vor dem abschließenden Gesamtlauf.
- UI-Produktionsbuild, Assetvertrag (14 Dateien/17 Icons), Schema und Beispiel bestanden. Keine neuen visuellen Assets.
- [Browsernachweis](browser-verification.json): abgelaufenen Entwurf zurückhalten, datierte Zitate/Originalquelle, bearbeiten, denselben Vorschlag erneut übernehmen, gültiger Entwurf nach Neuladen, Quellenentzug beim Wiederöffnen, Vorbereitung mit richtigem Konto/Empfänger, Entzug im alten Gespräch und in der Freigabe. Keine echte Mail versendet. Zitierte Nachrichten werden im Editor nicht als eigene Schreibstilbelege angeboten.
- Im Browser erkannte doppelte Aufgabenform durch gleiche Komponentenkennungen behoben. Abschließende Browserkonsole ohne Warnungen/Fehler. Desktopansicht geprüft, keine mobile Abnahme.

## Grenzen

Die Quellenrelevanz bleibt modellabhängig; auch wörtliche Zitate benötigen die sichtbare Prüfung vor Versand. Quellenbindung beweist keine semantische Wahrheit oder allgemeine Vollständigkeit. Quellenlose Vorschläge verwenden weiterhin freie Modellformulierung. Der Fall wurde nach einer konkreten Korrektur erneut verwendet und ist deshalb kein frischer Blindtest. Allgemeine Personen-/Projektauflösung, alle Quellenarten in Antwortentwürfen, lange/unvollständige Quellen und belastbare Langzeitqualität bleiben offen. Keine vollständige CoS-V1-Abnahme.
